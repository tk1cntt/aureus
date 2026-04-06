"""
Main entry point for aureus-trader service.

Subscribes to Redis pub/sub channels for STRATEGY_MATCH events,
validates them, builds order commands, deduplicates via Redis,
and enqueues them for dispatch to MT5.
"""
import asyncio
import json
import os
import logging

import redis.asyncio as redis

from config import load_config, SIGNALS_CHANNEL_PREFIX
from validator import validate_strategy_match
from order_builder import build_order_command
from idempotency import IdempotencyChecker
from dispatcher import OrderDispatcher

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def run_trader():
    """Main async entry point for the aureus-trader service."""
    # 1. Load configuration
    config = load_config()
    logger.info(f"Loaded config: symbols={config.symbols}, "
                f"max_queue_size={config.max_queue_size}, "
                f"max_retries={config.max_retries}")

    # 2. Initialize Redis connection
    logger.info(f"Connecting to Redis at {config.redis_host}:{config.redis_port}")
    r = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        decode_responses=True,
    )
    await r.ping()
    logger.info("Redis connected")

    # 3. Initialize components
    dedup = IdempotencyChecker(r, config.dedup_ttl)
    dispatcher = OrderDispatcher(r, config)

    # 4. Start dispatcher loop
    dispatch_task = asyncio.create_task(dispatcher.dispatch_loop())
    logger.info("Dispatcher loop started")

    # 5. Start event listener (for ACK/NACK/ORDER_OPENED/ORDER_FAILED)
    event_task = asyncio.create_task(dispatcher.event_listener())
    logger.info("Event listener started")

    # 6. Subscribe to signal channels for all configured symbols
    channels = [f"{SIGNALS_CHANNEL_PREFIX}{sym}" for sym in config.symbols]
    pubsub = r.pubsub()
    await pubsub.subscribe(*channels)
    logger.info(f"Subscribed to channels: {channels}")

    # 7. Process incoming events
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                event = json.loads(message["data"])

                # Filter: only process STRATEGY_MATCH events
                if event.get("type") != "STRATEGY_MATCH":
                    continue

                # Validate the event
                result = validate_strategy_match(event)
                if not result.valid:
                    logger.warning(f"Validation failed: {result.errors}")
                    continue

                # Build order command
                order_cmd = build_order_command(event)

                # Idempotency check
                is_new = await dedup.check_and_mark(order_cmd["cmd_id"])
                if not is_new:
                    logger.info(f"Duplicate order skipped: {order_cmd['cmd_id']}")
                    continue

                # Enqueue for dispatch
                enqueued = await dispatcher.enqueue_order(order_cmd)
                if enqueued:
                    logger.info(
                        f"Order queued: {order_cmd['cmd_id']} "
                        f"{order_cmd['symbol']} {order_cmd['direction']}"
                    )
                else:
                    logger.error(
                        f"Queue full, order rejected: {order_cmd['cmd_id']}"
                    )

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON: {e}")
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    except asyncio.CancelledError:
        logger.info("Trader loop cancelled")
    finally:
        dispatcher.stop()
        dispatch_task.cancel()
        event_task.cancel()
        await pubsub.unsubscribe()
        await r.close()
        logger.info("Trader shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(run_trader())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
