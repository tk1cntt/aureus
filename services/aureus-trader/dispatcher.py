"""
Order dispatcher — queue management, dispatch loop, and retry logic.

Publishes order commands to MT5 via Redis, handles ACK/NACK responses,
and implements selective retry with exponential backoff.
"""
import asyncio
import json
import logging
from dataclasses import dataclass

from config import TraderConfig, ORDER_QUEUE_KEY, COMMANDS_CHANNEL, EVENTS_CHANNEL, SIGNALS_CHANNEL_PREFIX

logger = logging.getLogger(__name__)

# Retryable error classifications
RETRYABLE_NACK_REASONS = {"TRADE_DISABLED"}
RETRYABLE_FAIL_REASONS = {"MARKET_CLOSED"}
RETRYABLE_FAIL_KEYWORDS = {"server", "busy"}
NON_RETRYABLE_NACK_REASONS = {"DUPLICATE", "INVALID_COMMAND", "UNKNOWN_SYMBOL"}
NON_RETRYABLE_FAIL_REASONS = {"INSUFFICIENT_MARGIN", "INVALID_STOPS"}


def is_retryable(event: dict) -> bool:
    """Check if an ACK/NACK/ORDER_FAILED response is retryable."""
    reason = event.get("reason", "")

    # Check NACK reasons
    if event.get("type") == "NACK":
        if reason in RETRYABLE_NACK_REASONS:
            return True
        if reason in NON_RETRYABLE_NACK_REASONS:
            return False

    # Check ORDER_FAILED reasons
    if event.get("type") == "ORDER_FAILED":
        if reason in RETRYABLE_FAIL_REASONS:
            return True
        if reason in NON_RETRYABLE_FAIL_REASONS:
            return False
        # Check for transient keywords in reason or message
        message = event.get("message", "").lower()
        reason_lower = reason.lower()
        for keyword in RETRYABLE_FAIL_KEYWORDS:
            if keyword in reason_lower or keyword in message:
                return True

    return False


class OrderDispatcher:
    """Dispatches orders from the Redis queue to MT5 with retry logic."""

    def __init__(self, redis_client, config: TraderConfig, journal_manager=None):
        self.redis = redis_client
        self.config = config
        self._running = False
        self._pending_responses: dict[str, asyncio.Future] = {}
        self.journal = journal_manager

    async def enqueue_order(self, order_cmd: dict) -> bool:
        """Add an order to the Redis queue if not full.

        Returns True if enqueued, False if queue is full.
        """
        queue_size = await self.redis.llen(ORDER_QUEUE_KEY)
        if queue_size >= self.config.max_queue_size:
            logger.error(
                f"Order queue full ({queue_size}/{self.config.max_queue_size}), "
                f"rejecting order {order_cmd.get('cmd_id')}"
            )
            return False

        await self.redis.rpush(ORDER_QUEUE_KEY, json.dumps(order_cmd))
        return True

    async def dispatch_loop(self):
        """Main dispatch loop — pops orders from queue and dispatches them."""
        self._running = True
        logger.info("Order dispatcher loop started")

        while self._running:
            raw = await self.redis.lpop(ORDER_QUEUE_KEY)
            if raw is None:
                await asyncio.sleep(0.5)
                continue

            try:
                order = json.loads(raw)
                await self.dispatch_order(order)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid order in queue: {e}")
            except Exception as e:
                logger.error(f"Error dispatching order: {e}")

    async def dispatch_order(self, order: dict):
        """Dispatch a single order with retry logic.

        Per D-03: max retries with exponential backoff,
        selective retry for retryable errors only.
        """
        cmd_id = order["cmd_id"]
        max_retries = self.config.max_retries

        for attempt in range(max_retries + 1):
            # PUBLISH to aureus:mt5:commands
            await self.redis.publish(COMMANDS_CHANNEL, json.dumps(order))
            logger.debug(
                f"Published order {cmd_id} (attempt {attempt + 1}/{max_retries + 1})"
            )

            # Wait for ACK/NACK (5s timeout)
            ack_result = await self._wait_for_response(
                cmd_id, self.config.ack_timeout
            )

            if ack_result is None:
                # Timeout — no ACK received
                logger.warning(
                    f"ACK timeout for {cmd_id}, attempt {attempt + 1}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                else:
                    await self._handle_max_retries(order)
                    return

            if ack_result.get("type") == "NACK":
                if is_retryable(ack_result):
                    logger.warning(
                        f"NACK (retryable) for {cmd_id}: {ack_result.get('reason')}, "
                        f"retrying in {2**attempt}s"
                    )
                    await asyncio.sleep(2**attempt)
                    continue
                else:
                    await self._handle_rejection(order, ack_result)
                    return

            if ack_result.get("type") == "ACK":
                # Wait for ORDER_OPENED/ORDER_FAILED (30s timeout)
                final = await self._wait_for_response(
                    cmd_id, self.config.result_timeout
                )

                if final is None:
                    logger.warning(f"Result timeout for {cmd_id}")
                    await self._handle_max_retries(order)
                    return

                if final.get("type") == "ORDER_OPENED":
                    logger.info(
                        f"Order executed: {cmd_id} ticket={final.get('ticket')}"
                    )
                    # Journal: record execution — inject trace_id from order
                    if self.journal:
                        trace_id = order.get("trace_id", "")
                        if trace_id:
                            final["trace_id"] = trace_id
                        await self.journal.on_order_opened(final)
                    return

                if is_retryable(final):
                    logger.warning(
                        f"Result retryable for {cmd_id}: {final.get('reason')}, "
                        f"retrying in {2**attempt}s"
                    )
                    await asyncio.sleep(2**attempt)
                    continue

                # Non-retryable final result
                await self._handle_rejection(order, final)
                return

        # Exhausted all retries
        await self._handle_max_retries(order)

    async def event_listener(self):
        """Listen to aureus:mt5:events and resolve pending futures."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(EVENTS_CHANNEL)
        logger.info(f"Subscribed to events channel: {EVENTS_CHANNEL}")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    event = json.loads(message["data"])

                    # Journal: record trade closure (ORDER_CLOSED events don't have cmd_id)
                    if event.get("type") in ("ORDER_CLOSED", "ORDER_CLOSED_PARTIAL"):
                        if self.journal:
                            # Fire-and-forget: don't block event resolution
                            asyncio.create_task(self.journal.on_order_closed(event))

                    cmd_id = event.get("cmd_id")
                    if cmd_id and cmd_id in self._pending_responses:
                        future = self._pending_responses.pop(cmd_id)
                        if not future.done():
                            future.set_result(event)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid event JSON: {e}")
                except Exception as e:
                    logger.error(f"Error processing event: {e}")
        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
        finally:
            await pubsub.unsubscribe(EVENTS_CHANNEL)

    async def _wait_for_response(
        self, cmd_id: str, timeout: float
    ) -> dict | None:
        """Wait for a response event matching cmd_id with timeout."""
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[cmd_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            # Clean up if still pending
            self._pending_responses.pop(cmd_id, None)
            return None

    async def _handle_rejection(self, order: dict, event: dict):
        """Log rejection and publish ORDER_REJECTED alert."""
        cmd_id = order["cmd_id"]
        symbol = order.get("symbol", "UNKNOWN")
        reason = event.get("reason", "UNKNOWN")
        event_type = event.get("type", "UNKNOWN")

        logger.warning(
            f"Order rejected: {cmd_id} ({event_type}: {reason})"
        )

        alert = {
            "type": "ORDER_REJECTED",
            "symbol": symbol,
            "t": int(asyncio.get_event_loop().time() * 1000),
            "data": {
                "cmd_id": cmd_id,
                "reason": reason,
                "event_type": event_type,
                "message": event.get("message", ""),
            },
        }
        channel = f"{SIGNALS_CHANNEL_PREFIX}{symbol}"
        await self.redis.publish(channel, json.dumps(alert))

    async def _handle_max_retries(self, order: dict):
        """Log max retries exceeded and publish ORDER_REJECTED alert."""
        cmd_id = order["cmd_id"]
        symbol = order.get("symbol", "UNKNOWN")

        logger.error(
            f"Max retries exceeded for order {cmd_id} ({symbol})"
        )

        alert = {
            "type": "ORDER_REJECTED",
            "symbol": symbol,
            "t": int(asyncio.get_event_loop().time() * 1000),
            "data": {
                "cmd_id": cmd_id,
                "reason": "MAX_RETRIES_EXCEEDED",
                "event_type": "TIMEOUT",
                "message": f"Order {cmd_id} exceeded max retries",
            },
        }
        channel = f"{SIGNALS_CHANNEL_PREFIX}{symbol}"
        await self.redis.publish(channel, json.dumps(alert))

    def stop(self):
        """Signal the dispatch loop to stop."""
        self._running = False
