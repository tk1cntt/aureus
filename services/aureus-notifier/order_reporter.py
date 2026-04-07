"""
Order Status Reporter — polls MT5 positions and trade history,
sends consolidated Telegram reports every 60 seconds.

Sends two commands to EA via Gateway:
1. REQUEST_POSITIONS → receives POSITION_REPORT (open positions)
2. REQUEST_TRADE_HISTORY → receives TRADE_HISTORY (recently closed orders)

Then formats a single message and sends to Telegram.
"""
import asyncio
import json
import html
import logging
import time
from datetime import datetime, timezone

import redis.asyncio as redis

from telegram_bot import TelegramSender

logger = logging.getLogger(__name__)


class OrderStatusReporter:
    """Periodically polls MT5 order status and sends Telegram reports."""

    def __init__(
        self,
        redis_client: redis.Redis,
        sender: TelegramSender,
        chat_id: str,
        interval: int = 60,
        response_timeout: float = 10.0,
    ):
        self.redis = redis_client
        self.sender = sender
        self.chat_id = chat_id
        self.interval = interval
        self.response_timeout = response_timeout

    async def run(self):
        """Main loop: report every {interval} seconds."""
        logger.info(f"OrderStatusReporter started — interval={self.interval}s, chat={self.chat_id}")
        while True:
            try:
                await self._report_cycle()
            except Exception as e:
                logger.error(f"Report cycle error: {e}", exc_info=True)
            await asyncio.sleep(self.interval)

    async def _report_cycle(self):
        """Single report cycle: request data, format, send."""
        # Subscribe to mt5 events BEFORE sending commands
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("aureus:mt5:events")

        try:
            # 1. Request open positions
            positions = await self._request_positions(pubsub)

            # 2. Request recently closed trades (last 60 seconds)
            closed_trades = await self._request_trade_history(pubsub)

            # 3. Format message
            message = self._format_report(positions, closed_trades)

            # 4. Send to Telegram (skip if nothing to report)
            if message:
                success = await self.sender.send_message(self.chat_id, message)
                if success:
                    logger.info(f"Order report sent: {len(positions)} positions, {len(closed_trades)} closed")
                else:
                    logger.warning("Failed to send order report to Telegram")
        finally:
            await pubsub.unsubscribe("aureus:mt5:events")
            await pubsub.close()

    async def _request_positions(self, pubsub) -> list:
        """Send REQUEST_POSITIONS command and wait for POSITION_REPORT response."""
        cmd = json.dumps({"type": "REQUEST_POSITIONS", "symbol": ""})
        await self.redis.publish("aureus:mt5:commands", cmd)
        logger.debug("Sent REQUEST_POSITIONS command")

        return await self._wait_for_response(pubsub, "POSITION_REPORT", "positions")

    async def _request_trade_history(self, pubsub) -> list:
        """Send REQUEST_TRADE_HISTORY for last 60 seconds and wait for response."""
        now_ms = int(time.time() * 1000)
        from_ms = now_ms - (self.interval * 1000)

        cmd = json.dumps({
            "type": "REQUEST_TRADE_HISTORY",
            "from_time": from_ms,
            "to_time": now_ms,
            "magic_number": 0,
            "symbol": "",
        })
        await self.redis.publish("aureus:mt5:commands", cmd)
        logger.debug("Sent REQUEST_TRADE_HISTORY command")

        return await self._wait_for_response(pubsub, "TRADE_HISTORY", "trades")

    async def _wait_for_response(self, pubsub, expected_type: str, data_key: str) -> list:
        """Wait for a specific event type on pubsub, with timeout."""
        deadline = time.time() + self.response_timeout

        while time.time() < deadline:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    if event.get("type") == expected_type:
                        return event.get(data_key, [])
                except (json.JSONDecodeError, KeyError):
                    continue

        logger.warning(f"Timeout waiting for {expected_type} response")
        return []

    def _format_report(self, positions: list, closed_trades: list) -> str:
        """Format consolidated report message in HTML."""
        if not positions and not closed_trades:
            return ""

        parts = [
            "📊 <b>MT5 Order Report</b>",
            "━━━━━━━━━━━━━━━━━━━",
        ]

        # Open positions section
        if positions:
            parts.append("")
            parts.append("🟢 <b>Open Positions:</b>")

            total_profit = 0.0
            for pos in positions:
                symbol = html.escape(str(pos.get("symbol", "?")))
                profit = pos.get("profit", 0.0)
                swap = pos.get("swap", 0.0)
                net_profit = profit + swap
                pips = pos.get("pips", 0.0)
                volume = pos.get("volume", 0.0)
                direction = pos.get("direction", "?")

                total_profit += net_profit

                # Direction emoji
                dir_emoji = "🟢" if direction == "BUY" else "🔴"

                # Profit sign
                profit_sign = "+" if net_profit >= 0 else ""
                pips_sign = "+" if pips >= 0 else ""

                parts.append(
                    f"{dir_emoji} {symbol}: {profit_sign}{net_profit:.2f}$ "
                    f"({pips_sign}{pips:.1f} pips) - {volume:.2f}"
                )

            # Total P/L
            parts.append("")
            total_sign = "+" if total_profit >= 0 else ""
            total_emoji = "💰" if total_profit >= 0 else "📉"
            parts.append(f"{total_emoji} <b>Total P/L: {total_sign}{total_profit:.2f}$</b>")
        else:
            parts.append("")
            parts.append("📭 <i>No open positions</i>")

        # Recently closed section
        if closed_trades:
            parts.append("")
            parts.append("❌ <b>Closed (1m):</b>")

            for trade in closed_trades:
                symbol = html.escape(str(trade.get("symbol", "?")))
                profit = trade.get("profit", 0.0)
                commission = trade.get("commission", 0.0)
                swap = trade.get("swap", 0.0)
                net = profit + commission + swap
                volume = trade.get("volume", 0.0)
                direction = trade.get("direction", "?")

                # Calculate pips from entry/exit
                entry = trade.get("entry_price", 0.0)
                exit_p = trade.get("exit_price", 0.0)
                pips = 0.0
                
                if "pips" in trade and trade["pips"] is not None:
                    pips = trade["pips"]
                elif entry > 0 and exit_p > 0:
                    # Rough pip calc backwards compatibility
                    if entry > 50:  # JPY pairs, indices
                        pips = (exit_p - entry) * 100 if direction == "BUY" else (entry - exit_p) * 100
                    else:
                        pips = (exit_p - entry) * 10000 if direction == "BUY" else (entry - exit_p) * 10000

                net_sign = "+" if net >= 0 else ""
                pips_sign = "+" if pips >= 0 else ""
                result_emoji = "✅" if net >= 0 else "❌"

                parts.append(
                    f"{result_emoji} {symbol}: {net_sign}{net:.2f}$ "
                    f"({pips_sign}{pips:.1f} pips) - {volume:.2f}"
                )

        # Timestamp
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        parts.append("")
        parts.append(f"<i>🕐 {now_str} UTC</i>")

        message = "\n".join(parts)
        return message[:4095]  # Telegram limit
