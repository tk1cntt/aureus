"""
Trade Journal Manager — captures strategy match context and updates trade lifecycle events.

Integration points:
- on_strategy_match(): Called when trader receives STRATEGY_MATCH from Redis
- on_order_opened(): Called when event_listener receives ORDER_OPENED
- on_order_closed(): Called when event_listener receives ORDER_CLOSED
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EXCLUDED_SIGNAL_STATE_TAGS = {
    "zigzag_state",
    "ob_state",
    "choch_state",
    "fvg_state",
    "trend_filter_state",
}


def _strip_excluded_signal_states(signal_snapshot: dict) -> dict:
    cleaned = dict(signal_snapshot or {})

    for key in EXCLUDED_SIGNAL_STATE_TAGS:
        cleaned.pop(key, None)

    active_signals = cleaned.get("active_signals")
    if isinstance(active_signals, list):
        filtered = []
        for item in active_signals:
            if isinstance(item, dict) and item.get("tag") in EXCLUDED_SIGNAL_STATE_TAGS:
                continue
            filtered.append(item)
        cleaned["active_signals"] = filtered

    return cleaned



def _has_signal_payload(signal_snapshot: dict) -> bool:
    return bool(signal_snapshot)


def _normalize_session_code(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        code = int(value)
        return code if code in (1, 2, 3) else None
    mapping = {"ASIAN": 1, "LONDON": 2, "NEWYORK": 3, "NEW_YORK": 3}
    return mapping.get(str(value).strip().upper())


def _normalize_polarity_code(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        code = int(value)
        return code if code in (-1, 1) else None
    text = str(value).strip().upper()
    if text == "BULL":
        return 1
    if text == "BEAR":
        return -1
    return None


VALID_EXIT_REASONS = {
    "TP_HIT", "SL_HIT", "TRAILING_STOP", "MANUAL_CLOSE", "SIGNAL_EXIT"
}

VALID_DIRECTIONS = {"BUY", "SELL"}

PIP_VALUES = {
    "XAUUSD": 0.01, "XAUEUR": 0.01, "XAUGBP": 0.01,
    "EURUSD": 0.0001, "EURGBP": 0.0001, "EURJPY": 0.01,
    "GBPUSD": 0.0001, "GBPJPY": 0.01, "USDJPY": 0.01,
    "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDCAD": 0.0001, "AUDCAD": 0.0001,
    "DEFAULT": 0.0001
}


class TradeJournalManager:
    """Manages trade journal entries for strategy analysis."""

    def __init__(self, db_pool):
        """:param db_pool: asyncpg connection pool"""
        self.db = db_pool

    async def on_strategy_match(self, event: dict) -> bool:
        """Create journal entry when strategy match is received.

        Called before order is enqueued — creates TRIGGERED entry.

        :param event: STRATEGY_MATCH event dict from Redis
        :return: True if entry created, False on error (does NOT block dispatch)
        """
        try:
            trace_id = event.get("trace_id", event.get("data", {}).get("trace_id"))
            if not trace_id:
                logger.error("on_strategy_match: missing trace_id")
                return False

            # Extract data from event structure
            data = event.get("data", event)
            match_data = data.get("match", {}) if "match" in data else data

            strategy_name = data.get("strategy_name", match_data.get("strategy_name", ""))
            if not strategy_name:
                logger.error("on_strategy_match: missing strategy_name")
                return False

            direction = data.get("direction", match_data.get("direction", ""))
            if direction not in VALID_DIRECTIONS:
                logger.error(f"on_strategy_match: invalid direction '{direction}'")
                return False

            symbol = data.get("symbol", match_data.get("symbol", event.get("symbol", "")))
            if not symbol:
                logger.error("on_strategy_match: missing symbol")
                return False

            # Optional fields
            strategy_id = data.get("strategy_id", match_data.get("strategy_id"))
            score = data.get("score", match_data.get("score"))
            if score is not None:
                try:
                    score = float(score)
                except (ValueError, TypeError):
                    logger.warning("on_strategy_match: score is not numeric, setting to NULL")
                    score = None

            # Signal context
            active_signals = data.get("active_signals", match_data.get("active_signals", []))
            if isinstance(active_signals, dict):
                normalized_signals = []
                for tag, payload in active_signals.items():
                    if isinstance(payload, dict):
                        normalized_signals.append({"tag": tag, **payload})
                    else:
                        normalized_signals.append({"tag": tag, "value": payload})
                active_signals = normalized_signals
            elif isinstance(active_signals, (tuple, set)):
                active_signals = list(active_signals)
            elif not isinstance(active_signals, list):
                logger.warning("on_strategy_match: active_signals is not a list")
                active_signals = []

            context_filters = data.get("context_filters", match_data.get("context_filters", {}))
            if not isinstance(context_filters, dict):
                logger.warning("on_strategy_match: context_filters is not a dict")
                context_filters = {}

            origin_ts = data.get("origin_timestamp", match_data.get("origin_timestamp"))
            if origin_ts and isinstance(origin_ts, (int, float)):
                origin_timestamp = datetime.fromtimestamp(origin_ts, tz=timezone.utc)
            elif isinstance(origin_ts, datetime):
                origin_timestamp = origin_ts
            else:
                origin_timestamp = None

            query = """
                INSERT INTO aureus_trade_journal (
                    trace_id, strategy_name, strategy_id, direction, symbol, score,
                    active_signals, context_filters, origin_timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT DO NOTHING
                RETURNING id
            """

            async with self.db.acquire() as conn:
                result = await conn.fetchval(
                    query,
                    trace_id, strategy_name, strategy_id, direction, symbol, score,
                    json.dumps(active_signals),
                    json.dumps(context_filters),
                    origin_timestamp
                )

            if result:
                logger.info(
                    f"Journal entry created: trace_id={trace_id} "
                    f"strategy={strategy_name} {direction} {symbol}"
                )
            else:
                logger.warning(f"Journal entry already exists for trace_id={trace_id}")

            return True

        except Exception as e:
            logger.exception(f"Error creating journal entry: {e}")
            return False

    async def on_order_opened(self, event: dict) -> bool:
        """Update journal entry when ORDER_OPENED event is received.

        :param event: ORDER_OPENED event dict from Redis
        :return: True if updated, False on error
        """
        try:
            trace_id = event.get("trace_id")
            ticket = event.get("ticket")

            if not trace_id:
                logger.warning("on_order_opened: missing trace_id in event")
                return False

            if not ticket:
                logger.warning("on_order_opened: missing ticket in event")
                return False

            entry_price = event.get("open_price", event.get("price"))
            if entry_price is None or entry_price <= 0:
                logger.warning(f"on_order_opened: invalid entry_price '{entry_price}'")
                return False

            # Extract optional fields
            sl = event.get("sl")
            tp = event.get("tp")
            volume = event.get("volume", event.get("lots"))
            position_id = event.get("position_id")
            open_time = event.get("time", event.get("open_time"))
            if open_time is None:
                logger.warning("on_order_opened: missing MT5 order time (time/open_time)")
                return False

            if isinstance(open_time, (int, float)):
                entry_time = datetime.fromtimestamp(open_time, tz=timezone.utc)
            elif isinstance(open_time, str):
                try:
                    entry_time = datetime.fromisoformat(open_time.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"on_order_opened: invalid MT5 order time '{open_time}'")
                    return False
            else:
                logger.warning(f"on_order_opened: unsupported MT5 order time type '{type(open_time).__name__}'")
                return False

            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)

            query = """
                UPDATE aureus_trade_journal
                SET status = 'EXECUTED',
                    ticket = $1,
                    entry_price = $2,
                    entry_time = $3,
                    position_id = $4,
                    lot_size = $5,
                    sl_initial = $6,
                    tp_initial = $7,
                    updated_at = now()
                WHERE trace_id = $8 AND status = 'TRIGGERED'
            """

            async with self.db.acquire() as conn:
                rows = await conn.execute(
                    query,
                    ticket, entry_price, entry_time, position_id,
                    volume, sl, tp, trace_id
                )

                if rows and "UPDATE 1" in rows:
                    journal_row = await conn.fetchrow(
                        "SELECT id, strategy_name, symbol, active_signals, context_filters "
                        "FROM aureus_trade_journal WHERE trace_id = $1",
                        trace_id,
                    )

                    if journal_row:
                        trade_journal_id = journal_row.get("id")
                        strategy_name = event.get("strategy_name", journal_row.get("strategy_name", ""))
                        symbol = event.get("symbol", journal_row.get("symbol", ""))
                        timeframe = event.get("timeframe", journal_row.get("timeframe", ""))
                    else:
                        trade_journal_id = None
                        strategy_name = event.get("strategy_name", "")
                        symbol = event.get("symbol", "")
                        timeframe = event.get("timeframe", "")

                    score_total_raw = event.get("score_total", event.get("score"))
                    score_total = None
                    if score_total_raw is not None:
                        try:
                            score_total = float(score_total_raw)
                        except (TypeError, ValueError):
                            logger.warning("on_order_opened: score_total is not numeric")

                    score_breakdown = event.get("score_breakdown")
                    weights_snapshot = event.get("weights_snapshot")
                    missing_data_policy = event.get("missing_data_policy")

                    has_scoring_core = not (
                        score_total is None
                        or score_breakdown is None
                        or weights_snapshot is None
                        or missing_data_policy is None
                    )

                    if has_scoring_core:
                        score_version = event.get("score_version") or "scor-v1.0.0"

                        await conn.execute(
                        """
                        INSERT INTO aureus_trade_evaluations (
                            trade_journal_id, trace_id, ticket, score_version, score_total,
                            score_breakdown, weights_snapshot, missing_data_policy,
                            strategy_name, symbol, timeframe
                        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10, $11)
                        ON CONFLICT (trade_journal_id, score_version) DO NOTHING
                        """,
                        trade_journal_id,
                        trace_id,
                        ticket,
                        score_version,
                        score_total,
                        json.dumps(score_breakdown),
                        json.dumps(weights_snapshot),
                        missing_data_policy,
                        strategy_name,
                        symbol,
                        timeframe,
                    )

                    raw_signal_snapshot = event.get("signal_snapshot")
                    signal_snapshot = dict(raw_signal_snapshot) if isinstance(raw_signal_snapshot, dict) else {}

                    if not signal_snapshot and journal_row:
                        fallback_snapshot = {}
                        journal_active_signals = journal_row.get("active_signals")
                        journal_context_filters = journal_row.get("context_filters")
                        if journal_active_signals:
                            fallback_snapshot["active_signals"] = journal_active_signals
                        if journal_context_filters:
                            fallback_snapshot["context_filters"] = journal_context_filters
                        signal_snapshot = fallback_snapshot

                    signal_snapshot = _strip_excluded_signal_states(signal_snapshot)
                    has_signal_payload = _has_signal_payload(signal_snapshot)

                    if has_signal_payload:
                        atr = signal_snapshot.get("atr", event.get("atr"))
                        ema_21 = signal_snapshot.get("ema_21", signal_snapshot.get("ema21", event.get("ema_21", event.get("ema21"))))
                        ema_34 = signal_snapshot.get("ema_34", event.get("ema_34"))
                        ema_55 = signal_snapshot.get("ema_55", signal_snapshot.get("ema55", event.get("ema_55", event.get("ema55"))))
                        ema_89 = signal_snapshot.get("ema_89", event.get("ema_89"))
                        ema_100 = signal_snapshot.get("ema_100", event.get("ema_100"))
                        ema_200 = signal_snapshot.get("ema_200", event.get("ema_200"))
                        vol_sma_20 = signal_snapshot.get("vol_sma_20", event.get("vol_sma_20"))

                        session = _normalize_session_code(signal_snapshot.get("session", event.get("session")))
                        candle_color_d1 = _normalize_polarity_code(signal_snapshot.get("candle_color_d1", event.get("candle_color_d1")))
                        candle_color_h1 = _normalize_polarity_code(signal_snapshot.get("candle_color_h1", event.get("candle_color_h1")))
                        candle_color_m30 = _normalize_polarity_code(signal_snapshot.get("candle_color_m30", event.get("candle_color_m30")))
                        candle_color_m15 = _normalize_polarity_code(signal_snapshot.get("candle_color_m15", event.get("candle_color_m15")))
                        candle_color_m5 = _normalize_polarity_code(signal_snapshot.get("candle_color_m5", event.get("candle_color_m5")))

                        bb_m1_up = signal_snapshot.get("bb_m1_up", event.get("bb_m1_up"))
                        bb_m1_dn = signal_snapshot.get("bb_m1_dn", event.get("bb_m1_dn"))
                        bb_m5_up = signal_snapshot.get("bb_m5_up", event.get("bb_m5_up"))
                        bb_m5_dn = signal_snapshot.get("bb_m5_dn", event.get("bb_m5_dn"))
                        bb_m15_up = signal_snapshot.get("bb_m15_up", event.get("bb_m15_up"))
                        bb_m15_dn = signal_snapshot.get("bb_m15_dn", event.get("bb_m15_dn"))
                        bb_m30_up = signal_snapshot.get("bb_m30_up", event.get("bb_m30_up"))
                        bb_m30_dn = signal_snapshot.get("bb_m30_dn", event.get("bb_m30_dn"))
                        bb_h1_up = signal_snapshot.get("bb_h1_up", event.get("bb_h1_up"))
                        bb_h1_dn = signal_snapshot.get("bb_h1_dn", event.get("bb_h1_dn"))

                        cisd_m5 = _normalize_polarity_code(signal_snapshot.get("cisd_m5", event.get("cisd_m5")))
                        cisd_m15 = _normalize_polarity_code(signal_snapshot.get("cisd_m15", event.get("cisd_m15")))
                        cisd_m30 = _normalize_polarity_code(signal_snapshot.get("cisd_m30", event.get("cisd_m30")))
                        cisd_h1 = _normalize_polarity_code(signal_snapshot.get("cisd_h1", event.get("cisd_h1")))

                        await conn.execute(
                            """
                            INSERT INTO aureus_trade_signal_snapshots (
                                trade_journal_id, trace_id, ticket, strategy_name, symbol,
                                atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200, vol_sma_20,
                                session, candle_color_d1, candle_color_h1, candle_color_m30,
                                candle_color_m15, candle_color_m5,
                                bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn,
                                bb_m30_up, bb_m30_dn, bb_h1_up, bb_h1_dn,
                                cisd_m5, cisd_m15, cisd_m30, cisd_h1
                            ) VALUES (
                                $1, $2, $3, $4, $5,
                                $6, $7, $8, $9, $10, $11, $12, $13,
                                $14, $15, $16, $17,
                                $18, $19,
                                $20, $21, $22, $23, $24, $25,
                                $26, $27, $28, $29,
                                $30, $31, $32, $33
                            )
                            ON CONFLICT (trade_journal_id) DO NOTHING
                            """,
                            trade_journal_id,
                            trace_id,
                            ticket,
                            strategy_name,
                            symbol,
                            atr,
                            ema_21,
                            ema_34,
                            ema_55,
                            ema_89,
                            ema_100,
                            ema_200,
                            vol_sma_20,
                            session,
                            candle_color_d1,
                            candle_color_h1,
                            candle_color_m30,
                            candle_color_m15,
                            candle_color_m5,
                            bb_m1_up,
                            bb_m1_dn,
                            bb_m5_up,
                            bb_m5_dn,
                            bb_m15_up,
                            bb_m15_dn,
                            bb_m30_up,
                            bb_m30_dn,
                            bb_h1_up,
                            bb_h1_dn,
                            cisd_m5,
                            cisd_m15,
                            cisd_m30,
                            cisd_h1,
                        )

                    wants_scoring_persist = any(
                        event.get(k) is not None
                        for k in (
                            "score_total", "score", "score_breakdown",
                            "weights_snapshot", "missing_data_policy", "score_version"
                        )
                    )

                    if wants_scoring_persist and not has_scoring_core:
                        logger.warning(
                            "on_order_opened: missing scoring core fields "
                            "(score_total/score_breakdown/weights_snapshot/missing_data_policy)"
                        )

                    if not has_scoring_core and not has_signal_payload:
                        logger.debug(
                            "on_order_opened: no evaluation/snapshot payload provided; journal status updated only"
                        )

            if rows and "UPDATE 1" in rows:
                logger.info(
                    f"Journal updated: trace_id={trace_id} ticket={ticket} "
                    f"entry_price={entry_price}"
                )
                return True
            else:
                logger.warning(
                    f"No journal entry found with status=TRIGGERED "
                    f"for trace_id={trace_id}"
                )
                return False

        except Exception as e:
            logger.exception(f"Error updating journal on order opened: {e}")
            return False

    async def on_order_closed(self, event: dict) -> bool:
        """Update journal entry when ORDER_CLOSED event is received.

        :param event: ORDER_CLOSED event dict from Redis
        :return: True if updated, False on error
        """
        try:
            trace_id = event.get("trace_id")
            ticket = event.get("ticket")

            if not trace_id and ticket:
                # Try lookup by ticket if trace_id not in event
                async with self.db.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT id, trace_id, entry_time, direction, symbol "
                        "FROM aureus_trade_journal WHERE ticket = $1 AND status = 'EXECUTED'",
                        ticket
                    )
                if row:
                    trace_id = row["trace_id"]
                else:
                    logger.warning(
                        f"on_order_closed: no journal entry for ticket={ticket}"
                    )
                    return False
            elif not trace_id:
                logger.warning("on_order_closed: missing trace_id and ticket")
                return False

            # Check if already closed
            async with self.db.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, entry_time, direction, symbol FROM aureus_trade_journal "
                    "WHERE trace_id = $1 AND status IN ('TRIGGERED', 'EXECUTED')",
                    trace_id
                )
            if not row:
                logger.warning(
                    f"on_order_closed: entry already closed or not found "
                    f"for trace_id={trace_id}"
                )
                return False

            # Extract exit data
            close_price = event.get("close_price", event.get("price"))
            if close_price is None:
                logger.warning("on_order_closed: missing close_price")
                return False

            pnl = event.get("profit", event.get("pnl"))
            if pnl is not None:
                try:
                    pnl = float(pnl)
                except (ValueError, TypeError):
                    logger.warning("on_order_closed: pnl is not numeric")
                    pnl = None

            commission = event.get("commission", 0) or 0
            swap = event.get("swap", 0) or 0

            close_time_raw = event.get("close_time", event.get("time"))
            if close_time_raw is None:
                logger.warning("on_order_closed: missing MT5 close time (close_time/time)")
                return False

            if isinstance(close_time_raw, (int, float)):
                exit_time = datetime.fromtimestamp(close_time_raw, tz=timezone.utc)
            elif isinstance(close_time_raw, str):
                try:
                    exit_time = datetime.fromisoformat(close_time_raw.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"on_order_closed: invalid MT5 close time '{close_time_raw}'")
                    return False
            else:
                logger.warning(f"on_order_closed: unsupported MT5 close time type '{type(close_time_raw).__name__}'")
                return False

            if exit_time.tzinfo is None:
                exit_time = exit_time.replace(tzinfo=timezone.utc)

            # Exit reason
            exit_reason = event.get("close_reason", event.get("reason", ""))
            # Normalize reason
            exit_reason = self._normalize_exit_reason(exit_reason)

            # Duration
            entry_time = row["entry_time"]
            if entry_time and exit_time:
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                duration_seconds = int((exit_time - entry_time).total_seconds())
            else:
                duration_seconds = None

            # Result
            result = None
            if pnl is not None:
                if pnl > 0.01:
                    result = "WIN"
                elif pnl < -0.01:
                    result = "LOSS"
                else:
                    result = "BE"

            # Pips calculation
            pnl_pips = None
            if close_price:
                symbol = row.get("symbol", "")
                pip_value = PIP_VALUES.get(symbol.upper(), PIP_VALUES["DEFAULT"])
                # Use ticket to look up entry_price if available
                # On-order_closed event may have entry_price from the position
                entry_price_for_pips = event.get("open_price", event.get("entry_price"))
                pnl_pips = round(abs(close_price - entry_price_for_pips) / pip_value, 1) if entry_price_for_pips else None

            # Update query
            query = """
                UPDATE aureus_trade_journal
                SET status = 'CLOSED',
                    exit_price = $1,
                    exit_time = $2,
                    exit_reason = $3,
                    duration_seconds = $4,
                    pnl = $5,
                    pnl_pips = $6,
                    commission = $7,
                    swap = $8,
                    result = $9,
                    updated_at = now()
                WHERE trace_id = $10
                RETURNING id
            """

            async with self.db.acquire() as conn:
                result_id = await conn.fetchval(
                    query,
                    close_price, exit_time, exit_reason, duration_seconds,
                    pnl, pnl_pips, commission, swap, result, trace_id
                )

            if result_id:
                logger.info(
                    f"Journal closed: trace_id={trace_id} result={result} "
                    f"pnl={pnl} duration={duration_seconds}s"
                )
                return True
            else:
                logger.warning(f"Failed to close journal entry for trace_id={trace_id}")
                return False

        except Exception as e:
            logger.exception(f"Error updating journal on order closed: {e}")
            return False

    def _normalize_exit_reason(self, reason: str) -> str:
        """Normalize exit reason to valid values."""
        if not reason:
            return "MANUAL_CLOSE"

        reason_upper = reason.upper().strip()

        if "TP" in reason_upper or "TAKE_PROFIT" in reason_upper:
            return "TP_HIT"
        if "SL" in reason_upper or "STOP_LOSS" in reason_upper:
            return "SL_HIT"
        if "TRAIL" in reason_upper:
            return "TRAILING_STOP"
        if "SIGNAL" in reason_upper or "EXIT" in reason_upper:
            return "SIGNAL_EXIT"

        # Default: if not a known reason, keep original if valid
        if reason_upper in VALID_EXIT_REASONS:
            return reason_upper

        return "MANUAL_CLOSE"
