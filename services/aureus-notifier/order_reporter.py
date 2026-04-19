"""
Order Status Reporter — listens for ORDER_OPENED and ORDER_CLOSED events from MT5
via Gateway and sends individual Telegram notifications when trades open or close.

Event-driven: no polling, no interval. Each trade lifecycle event triggers an immediate notification.

ORDER_OPENED notification includes:
- Strategy name, score, symbol, direction
- Entry price, SL, TP, volume, ticket
- Budget mode (RISK_FIXED_AMOUNT or fixed units)
"""
import asyncio
import json
import html
import logging
import os
from datetime import datetime, timezone

import redis.asyncio as redis
import asyncpg

from telegram_bot import TelegramSender

logger = logging.getLogger(__name__)

# PIP values per symbol
PIP_VALUES = {
    "XAUUSD": 0.01, "XAUEUR": 0.01, "XAUGBP": 0.01,
    "EURUSD": 0.0001, "EURGBP": 0.0001, "EURJPY": 0.01,
    "GBPUSD": 0.0001, "GBPJPY": 0.01, "USDJPY": 0.01,
    "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDCAD": 0.0001, "AUDCAD": 0.0001,
    "BTCUSD": 0.01, "ETHUSD": 0.01,
    "USTEC": 0.01, "US30": 0.01, "US500": 0.01,
    "DEFAULT": 0.0001
}


class OrderStatusReporter:
    """Listens for ORDER_OPENED/CLOSED events on aureus:mt5:events and sends Telegram alerts."""

    def __init__(
        self,
        redis_client: redis.Redis,
        sender: TelegramSender,
        chat_id: str,
    ):
        self.redis = redis_client
        self.sender = sender
        self.chat_id = chat_id
        self._db_pool = None

    async def _get_db_pool(self) -> asyncpg.Pool:
        """Lazy-init DB connection pool."""
        if self._db_pool is None:
            # Construct DSN from individual env vars (container) or use DATABASE_URL (local)
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                db_host = os.environ.get("DB_HOST", "localhost")
                db_port = os.environ.get("DB_PORT", "5432")
                db_name = os.environ.get("DB_NAME", "aureus")
                db_user = os.environ.get("DB_USER", "aureus")
                db_pass = os.environ.get("DB_PASSWORD", "aureus_password")
                dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            self._db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
        return self._db_pool

    async def _lookup_journal(self, trace_id: str) -> dict | None:
        """Lookup trade journal by trace_id to get strategy info and execution details."""
        try:
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT strategy_name, score, symbol, direction, status,
                           active_signals, entry_price, sl_initial, tp_initial, lot_size,
                           ticket, entry_time
                    FROM aureus_trade_journal
                    WHERE trace_id = $1
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    trace_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"DB lookup failed for trace_id={trace_id}: {e}")
            return None

    async def _lookup_journal_by_ticket(self, ticket: int) -> dict | None:
        """Fallback lookup by MT5 ticket when trace_id is missing/mismatched."""
        try:
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT strategy_name, score, symbol, direction, status,
                           active_signals, entry_price, sl_initial, tp_initial, lot_size,
                           ticket, entry_time
                    FROM aureus_trade_journal
                    WHERE ticket = $1
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    ticket,
                )
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"DB lookup failed for ticket={ticket}: {e}")
            return None

    def _normalize_ticket(self, ticket_raw) -> int | None:
        """Normalize ticket from int/float/string payloads."""
        if ticket_raw is None:
            return None
        try:
            if isinstance(ticket_raw, str):
                ticket_raw = ticket_raw.strip()
                if not ticket_raw:
                    return None
            return int(float(ticket_raw))
        except (TypeError, ValueError):
            return None

    async def _resolve_journal_context(self, event: dict) -> dict | None:
        """Resolve journal context by trace_id first, then ticket with short retry."""
        trace_id = event.get("trace_id") or ""
        ticket = self._normalize_ticket(event.get("ticket"))

        journal = None
        if trace_id:
            journal = await self._lookup_journal(str(trace_id))
        if journal is None and ticket is not None:
            journal = await self._lookup_journal_by_ticket(ticket)

        if journal is None:
            for _ in range(2):
                await asyncio.sleep(0.2)
                if trace_id:
                    journal = await self._lookup_journal(str(trace_id))
                if journal is None and ticket is not None:
                    journal = await self._lookup_journal_by_ticket(ticket)
                if journal is not None:
                    break

        return journal

    async def run(self):
        """Main loop: subscribe to mt5 events and forward ORDER_OPENED/CLOSED to Telegram."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("aureus:mt5:events")
        logger.info("OrderStatusReporter started — listening for ORDER_OPENED and ORDER_CLOSED events")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                    evt_type = event.get("type")

                    if evt_type == "ORDER_OPENED":
                        asyncio.create_task(self._handle_order_opened(event))
                    elif evt_type == "ORDER_CLOSED":
                        asyncio.create_task(self._handle_order_closed(event))
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
            if self._db_pool:
                await self._db_pool.close()

    async def _handle_order_opened(self, event: dict):
        """Handle ORDER_OPENED: lookup journal for strategy info and send Telegram notification."""
        try:
            journal = await self._resolve_journal_context(event)

            msg = self._format_opened(event, journal)
            if msg:
                success = await self.sender.send_message(self.chat_id, msg)
                if success:
                    logger.info(
                        f"Order opened notification sent: {event.get('symbol')} "
                        f"ticket={event.get('ticket')}"
                    )
                else:
                    logger.warning("Failed to send order opened notification to Telegram")
        except Exception as e:
            logger.error(f"Error handling ORDER_OPENED: {e}", exc_info=True)

    async def _handle_order_closed(self, event: dict):
        """Handle ORDER_CLOSED: lookup journal for strategy info and send Telegram notification."""
        try:
            journal = await self._resolve_journal_context(event)

            msg = self._format_close(event, journal)
            if msg:
                success = await self.sender.send_message(self.chat_id, msg)
                if success:
                    logger.info(
                        f"Order close notification sent: {event.get('symbol')} "
                        f"ticket={event.get('ticket')} profit={event.get('profit')}"
                    )
                else:
                    logger.warning("Failed to send order close notification to Telegram")
        except Exception as e:
            logger.error(f"Error handling ORDER_CLOSED: {e}", exc_info=True)

    def _format_opened(self, event: dict, journal: dict | None) -> str:
        """Format single order opened notification in HTML."""
        symbol = html.escape(str(event.get("symbol", journal.get("symbol") if journal else "?")))
        direction = event.get("direction", journal.get("direction") if journal else "?")
        volume = event.get("volume", journal.get("lot_size") if journal else 0.0)
        ticket = event.get("ticket", journal.get("ticket") if journal else 0)
        entry = event.get("open_price", journal.get("entry_price") if journal else 0.0)
        sl = event.get("sl", journal.get("sl_initial") if journal else None)
        tp = event.get("tp", journal.get("tp_initial") if journal else None)
        magic = event.get("magic", 0)
        open_time_ms = event.get("t", 0)

        # Strategy info: ưu tiên journal, fallback event payload
        strategy_name = (
            (journal.get("strategy_name") if journal else None)
            or event.get("strategy_name")
            or event.get("strategy")
            or "N/A"
        )
        score = journal.get("score") if journal else None

        # Active signals summary from journal
        active_signals_raw = journal.get("active_signals", "") if journal else ""
        signal_tags = []
        if active_signals_raw:
            try:
                signals_list = json.loads(active_signals_raw)
                signal_tags = [str(s.get("tag", "")) for s in signals_list if isinstance(s, dict)]
            except (json.JSONDecodeError, TypeError):
                pass

        # SL distance in pips
        sl_pips = None
        if entry and sl:
            pip = PIP_VALUES.get(symbol.upper(), PIP_VALUES["DEFAULT"])
            sl_pips = round(abs(entry - sl) / pip, 1)

        # TP distance in pips
        tp_pips = None
        if entry and tp:
            pip = PIP_VALUES.get(symbol.upper(), PIP_VALUES["DEFAULT"])
            tp_pips = round(abs(tp - entry) / pip, 1)

        # Actual RR ratio from real entry
        rr_ratio = None
        if sl_pips and sl_pips > 0 and tp_pips:
            rr_ratio = round(tp_pips / sl_pips, 2)

        dir_emoji = "\U0001f7e2" if direction == "BUY" else "\U0001f534"

        # Time formatting
        if open_time_ms:
            dt = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)
            time_str = dt.strftime("%H:%M:%S UTC")
        else:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

        parts = [
            f"🆕 <b>Order Opened</b>",
            "\u2501" * 19,
        ]

        # Strategy line (if available)
        if strategy_name:
            score_str = f" (score: {score:.1f})" if score else ""
            parts.append(f"\U0001f3af Strategy: <b>{html.escape(strategy_name)}</b>{score_str}")

        # Signal tags
        if signal_tags:
            parts.append(f"\U0001f4e1 Signals: {', '.join(html.escape(t) for t in signal_tags)}")

        # Symbol and direction
        parts.append(f"{dir_emoji} {symbol} {direction}")

        # Execution details
        parts.append(f"\U0001f4ca Vol: {volume:.2f} | Ticket: {ticket}")
        parts.append(f"\U0001f4b5 Entry: {entry}")

        # SL
        if sl:
            sl_str = f"SL: {sl}"
            if sl_pips is not None:
                sl_str += f" ({sl_pips} pips)"
            parts.append(f"\U0001f6e1\ufe0f {sl_str}")

        # TP
        if tp:
            tp_str = f"TP: {tp}"
            if tp_pips is not None:
                tp_str += f" ({tp_pips} pips)"
            parts.append(f"\U0001f3af {tp_str}")

        # Actual RR ratio
        if rr_ratio is not None:
            parts.append(f"\U0001f4c8 RR: 1:{rr_ratio}")

        # Timestamp
        parts.append("")
        parts.append(f"<i>\U0001f550 {time_str}</i>")

        return "\n".join(parts)[:4095]  # Telegram limit

    def _format_close(self, event: dict, journal: dict | None = None) -> str:
        """Format single order close notification in HTML with strategy info."""
        symbol = html.escape(str(event.get("symbol", journal.get("symbol") if journal else "?")))
        direction = event.get("direction", journal.get("direction") if journal else "?")
        volume = event.get("volume", journal.get("lot_size") if journal else 0.0)
        profit = event.get("profit", 0.0)
        commission = event.get("commission", 0.0)
        swap = event.get("swap", 0.0)
        net = profit + commission + swap
        # Use real entry price from journal (entry_price from DB) instead of event (which may be 0)
        entry = event.get("open_price", 0.0)
        if entry == 0.0 and journal:
            entry = journal.get("entry_price", 0.0)
        exit_p = event.get("close_price", 0.0)
        ticket = event.get("ticket", journal.get("ticket") if journal else 0)
        close_time_ms = event.get("t", 0)

        # Strategy info: ưu tiên journal, fallback event payload
        strategy_name = (
            (journal.get("strategy_name") if journal else None)
            or event.get("strategy_name")
            or event.get("strategy")
            or "N/A"
        )
        score = journal.get("score") if journal else None

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

        # SL/TP from journal for RR calculation
        sl = journal.get("sl_initial") if journal else None
        tp = journal.get("tp_initial") if journal else None

        # Calculate RR ratio from original SL/TP
        rr_ratio = None
        if entry > 0 and sl and sl > 0:
            pip = PIP_VALUES.get(symbol.upper(), PIP_VALUES["DEFAULT"])
            sl_pips = abs(entry - sl) / pip
            tp_pips = abs(tp - entry) / pip if tp and tp > 0 else None
            if tp_pips and sl_pips > 0:
                rr_ratio = round(tp_pips / sl_pips, 2)

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
        ]

        # Strategy line (if available)
        if strategy_name:
            score_str = f" (score: {score:.1f})" if score else ""
            parts.append(f"\U0001f3af Strategy: <b>{html.escape(strategy_name)}</b>{score_str}")

        # Symbol, direction, P/L
        parts.append(f"{dir_emoji} {symbol} {direction}")
        parts.append(f"\U0001f4b0 {net_sign}{net:.2f}$ ({pips_text})")

        # Execution details
        parts.append(f"\U0001f4ca Vol: {volume:.2f} | Ticket: {ticket}")
        if entry > 0:
            parts.append(f"\U0001f4c8 Entry: {entry} \u2192 Exit: {exit_p}")

        # RR ratio (from original SL/TP)
        if rr_ratio is not None:
            parts.append(f"\U0001f4c9 RR: 1:{rr_ratio}")

        # Timestamp
        parts.append("")
        parts.append(f"<i>\U0001f550 {time_str}</i>")

        return "\n".join(parts)[:4095]  # Telegram limit
