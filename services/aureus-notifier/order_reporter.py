"""
Order Status Reporter — listens for ORDER_CLOSED events from MT5 via Gateway
and sends individual Telegram notifications when trades close.

Event-driven: no polling, no interval. Each closed trade triggers an immediate notification.
"""
import asyncio
import json
import html
import logging
from datetime import datetime, timezone

import redis.asyncio as redis

from telegram_bot import TelegramSender

logger = logging.getLogger(__name__)


class OrderStatusReporter:
    """Listens for ORDER_CLOSED events on aureus:mt5:events and sends Telegram alerts."""

    def __init__(
        self,
        redis_client: redis.Redis,
        sender: TelegramSender,
        chat_id: str,
    ):
        self.redis = redis_client
        self.sender = sender
        self.chat_id = chat_id

    async def run(self):
        """Main loop: subscribe to mt5 events and forward ORDER_CLOSED to Telegram."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("aureus:mt5:events")
        logger.info("OrderStatusReporter started — listening for ORDER_CLOSED events")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                    if event.get("type") == "ORDER_CLOSED":
                        msg = self._format_close(event)
                        if msg:
                            success = await self.sender.send_message(self.chat_id, msg)
                            if success:
                                logger.info(
                                    f"Order close notification sent: {event.get('symbol')} "
                                    f"ticket={event.get('ticket')} profit={event.get('profit')}"
                                )
                            else:
                                logger.warning("Failed to send order close notification to Telegram")
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in mt5 event: {e}")
                except Exception as e:
                    logger.error(f"Error processing mt5 event: {e}", exc_info=True)
        except asyncio.CancelledError:
            logger.info("OrderStatusReporter cancelled")
            raise
        finally:
            await pubsub.unsubscribe("aureus:mt5:events")
            await pubsub.close()

    def _format_close(self, event: dict) -> str:
        """Format single order close notification in HTML."""
        symbol = html.escape(str(event.get("symbol", "?")))
        direction = event.get("direction", "?")
        volume = event.get("volume", 0.0)
        profit = event.get("profit", 0.0)
        commission = event.get("commission", 0.0)
        swap = event.get("swap", 0.0)
        net = profit + commission + swap
        entry = event.get("open_price", 0.0)
        exit_p = event.get("close_price", 0.0)
        ticket = event.get("ticket", 0)
        close_time_ms = event.get("t", 0)

        # Pips calculation
        digits = event.get("digits", 5)
        pips = None

        # Check for explicit pips from gateway/EA (TRADE_HISTORY includes it)
        if "pips" in event and event["pips"] is not None:
            pips = float(event["pips"])
        elif entry > 0 and exit_p > 0:
            # Calculate from price difference
            if digits >= 4:
                pips = (exit_p - entry) * 10000 if direction == "BUY" else (entry - exit_p) * 10000
            else:
                pips = (exit_p - entry) * 100 if direction == "BUY" else (entry - exit_p) * 100

        dir_emoji = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
        result_emoji = "\u2705" if net >= 0 else "\u274c"
        net_sign = "+" if net >= 0 else ""
        pips_text = f"{pips:+.1f} pips" if pips is not None else "N/A"

        # Time formatting
        if close_time_ms:
            dt = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc)
            time_str = dt.strftime("%H:%M:%S UTC")
        else:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

        parts = [
            f"{result_emoji} <b>Order Closed</b>",
            "\u2501" * 19,
            f"{dir_emoji} {symbol} {direction}",
            f"\U0001f4b0 {net_sign}{net:.2f}$ ({pips_text})",
            f"\U0001f4ca Vol: {volume:.2f} | Ticket: {ticket}",
            f"\U0001f4c8 Entry: {entry} \u2192 Exit: {exit_p}",
            "",
            f"<i>\U0001f550 {time_str}</i>",
        ]
        return "\n".join(parts)[:4095]  # Telegram limit
