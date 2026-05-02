"""
Trade Journal Manager â€” captures strategy match context and updates trade lifecycle events.

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



def _to_float_or_none(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _first_present(snapshot: dict, event: dict, keys: tuple[str, ...]):
    for key in keys:
        if isinstance(snapshot, dict) and key in snapshot and snapshot.get(key) is not None:
            return snapshot.get(key)
        if isinstance(event, dict) and key in event and event.get(key) is not None:
            return event.get(key)
    return None


def _extract_active_signal_fields(active_signals) -> dict:
    extracted = {}
    if isinstance(active_signals, str):
        try:
            active_signals = json.loads(active_signals)
        except (TypeError, ValueError):
            active_signals = []
    if not isinstance(active_signals, list):
        return extracted

    supported_keys = {
        "atr", "ema_21", "ema21", "ema_34", "ema34", "ema_55", "ema55", "ema_89", "ema89",
        "ema_100", "ema100", "ema_200", "ema200", "vol_sma_20", "volSma20", "session",
        "candle_color_d1", "candle_color_h1", "candle_color_m30", "candle_color_m15", "candle_color_m5",
        "bb_m1_up", "bb_m1_dn", "bb_m5_up", "bb_m5_dn", "bb_m15_up", "bb_m15_dn", "bb_m30_up", "bb_m30_dn", "bb_h1_up", "bb_h1_dn",
        "cisd_m5", "cisd_m15", "cisd_m30", "cisd_h1",
    }

    for item in active_signals:
        if not isinstance(item, dict):
            continue
        for key in supported_keys:
            if key in item and item.get(key) is not None and key not in extracted:
                extracted[key] = item.get(key)
    return extracted


def _build_signal_snapshot_columns(signal_snapshot: dict, event: dict) -> dict:
    snapshot = signal_snapshot if isinstance(signal_snapshot, dict) else {}
    src_event = event if isinstance(event, dict) else {}

    active_signal_fields = _extract_active_signal_fields(snapshot.get("active_signals"))
    context_filters = snapshot.get("context_filters") if isinstance(snapshot.get("context_filters"), dict) else {}

    merged_snapshot = dict(snapshot)
    for key, value in active_signal_fields.items():
        merged_snapshot.setdefault(key, value)
    if "session" not in merged_snapshot and context_filters.get("session") is not None:
        merged_snapshot["session"] = context_filters.get("session")

    columns = {
        "atr": _to_float_or_none(_first_present(merged_snapshot, src_event, ("atr", "atr_14"))),
        "ema_21": _to_float_or_none(_first_present(merged_snapshot, src_event, ("ema_21", "ema21"))),
        "ema_34": _to_float_or_none(_first_present(merged_snapshot, src_event, ("ema_34", "ema34"))),
        "ema_55": _to_float_or_none(_first_present(merged_snapshot, src_event, ("ema_55", "ema55"))),
        "ema_89": _to_float_or_none(_first_present(merged_snapshot, src_event, ("ema_89", "ema89"))),
        "ema_100": _to_float_or_none(_first_present(merged_snapshot, src_event, ("ema_100", "ema100"))),
        "ema_200": _to_float_or_none(_first_present(merged_snapshot, src_event, ("ema_200", "ema200"))),
        "vol_sma_20": _to_float_or_none(_first_present(merged_snapshot, src_event, ("vol_sma_20", "volSma20", "vol_sma20"))),
        "session": _normalize_session_code(_first_present(merged_snapshot, src_event, ("session", "market_session"))),
        "candle_color_d1": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("candle_color_d1", "candle_color_D1"))),
        "candle_color_h1": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("candle_color_h1", "candle_color_H1"))),
        "candle_color_m30": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("candle_color_m30", "candle_color_M30"))),
        "candle_color_m15": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("candle_color_m15", "candle_color_M15"))),
        "candle_color_m5": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("candle_color_m5", "candle_color_M5"))),
        "bb_m1_up": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m1_up",))),
        "bb_m1_dn": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m1_dn",))),
        "bb_m5_up": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m5_up",))),
        "bb_m5_dn": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m5_dn",))),
        "bb_m15_up": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m15_up",))),
        "bb_m15_dn": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m15_dn",))),
        "bb_m30_up": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m30_up",))),
        "bb_m30_dn": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_m30_dn",))),
        "bb_h1_up": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_h1_up",))),
        "bb_h1_dn": _to_float_or_none(_first_present(merged_snapshot, src_event, ("bb_h1_dn",))),
        "cisd_m5": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("cisd_m5", "cisd_M5"))),
        "cisd_m15": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("cisd_m15", "cisd_M15"))),
        "cisd_m30": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("cisd_m30", "cisd_M30"))),
        "cisd_h1": _normalize_polarity_code(_first_present(merged_snapshot, src_event, ("cisd_h1", "cisd_H1"))),
    }

    return columns

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
    if text in {"BULL", "BULLISH"}:
        return 1
    if text in {"BEAR", "BEARISH"}:
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

        Called before order is enqueued â€” creates TRIGGERED entry.

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
                    try:
                        reasoning_text = data.get("reasoning", data.get("rationale", match_data.get("reasoning", match_data.get("rationale"))))
                        await conn.fetchval(
                            """
                            INSERT INTO aureus_reasoning_entries (
                                trace_id, trade_journal_id, strategy_id, strategy_name, symbol,
                                direction, confidence, active_signals, context_filters,
                                reasoning_text, decision_action
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            RETURNING id
                            """,
                            trace_id,
                            result,
                            strategy_id,
                            strategy_name,
                            symbol,
                            direction,
                            score,
                            json.dumps(active_signals),
                            json.dumps(context_filters),
                            reasoning_text,
                            direction,
                        )
                    except Exception as exc:
                        logger.warning("Reasoning entry insert failed for trace_id=%s: %s", trace_id, exc)

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

    async def on_order_pending_placed(self, event: dict) -> bool:
        """Persist accepted MT5 pending order without marking journal executed."""
        try:
            trace_id = event.get("trace_id")
            pending_order_id = event.get("pending_order_id") or event.get("order")
            cmd_id = event.get("cmd_id")
            if not trace_id and not cmd_id:
                logger.warning("on_order_pending_placed: missing trace_id/cmd_id")
                return False
            if not pending_order_id:
                logger.warning("on_order_pending_placed: missing pending_order_id")
                return False

            query = """
                UPDATE aureus_trade_journal
                SET pending_order_id = $1,
                    cmd_id = COALESCE($2, cmd_id),
                    mt5_comment = COALESCE($3, mt5_comment),
                    entry_price = COALESCE($4, entry_price),
                    sl_initial = COALESCE($5, sl_initial),
                    tp_initial = COALESCE($6, tp_initial),
                    updated_at = now()
                WHERE status = 'TRIGGERED'
                  AND (($7::text IS NOT NULL AND trace_id = $7) OR ($7::text IS NULL AND cmd_id = $2))
                RETURNING id
            """
            async with self.db.acquire() as conn:
                result_id = await conn.fetchval(
                    query,
                    pending_order_id,
                    cmd_id,
                    event.get("mt5_comment", event.get("comment")),
                    event.get("price"),
                    event.get("sl"),
                    event.get("tp"),
                    trace_id,
                )
            return result_id is not None
        except Exception as e:
            logger.exception(f"Error updating journal on pending placed: {e}")
            return False

    async def on_order_filled(self, event: dict) -> bool:
        """Update journal entry when a real MT5 DEAL_ENTRY_IN fill is received."""
        if event.get("ticket") is None and event.get("position_ticket") is not None:
            event = dict(event)
            event["ticket"] = event.get("position_ticket")
        if event.get("position_id") is None and event.get("position_ticket") is not None:
            event = dict(event)
            event["position_id"] = event.get("position_ticket")
        return await self.on_order_opened(event)

    async def on_order_opened(self, event: dict) -> bool:
        """Update journal entry when ORDER_OPENED/ORDER_FILLED event is received.

        :param event: ORDER_OPENED or ORDER_FILLED event dict from Redis
        :return: True if updated, False on error
        """
        try:
            trace_id = event.get("trace_id")
            ticket = event.get("ticket")

            logger.info(
                "on_order_opened: start trace_id=%s ticket=%s event_keys=%s",
                trace_id,
                ticket,
                sorted(list(event.keys())) if isinstance(event, dict) else [],
            )

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
                    pending_order_id = COALESCE($9, pending_order_id),
                    entry_deal_ticket = COALESCE($10, entry_deal_ticket),
                    cmd_id = COALESCE($11, cmd_id),
                    mt5_comment = COALESCE($12, mt5_comment),
                    updated_at = now()
                WHERE status = 'TRIGGERED'
                  AND (
                    ($8::text IS NOT NULL AND trace_id = $8)
                    OR ($8::text IS NULL AND $9::bigint IS NOT NULL AND pending_order_id = $9)
                    OR ($8::text IS NULL AND $11::text IS NOT NULL AND cmd_id = $11)
                  )
                RETURNING id, strategy_name, symbol, active_signals, context_filters
            """

            updated = False
            async with self.db.acquire() as conn:
                async with conn.transaction():
                    journal_row = await conn.fetchrow(
                        query,
                        ticket, entry_price, entry_time, position_id,
                        volume, sl, tp, trace_id,
                        event.get("pending_order_id"), event.get("deal_ticket"),
                        event.get("cmd_id"), event.get("mt5_comment", event.get("comment"))
                    )

                    if journal_row:
                        updated = True
                        trade_journal_id = journal_row.get("id")
                        strategy_name = event.get("strategy_name", journal_row.get("strategy_name", ""))
                        symbol = event.get("symbol", journal_row.get("symbol", ""))
                        timeframe = event.get("timeframe", "")
                    else:
                        trade_journal_id = None
                        strategy_name = event.get("strategy_name", "")
                        symbol = event.get("symbol", "")
                        timeframe = event.get("timeframe", "")

                    timeframe = event.get("timeframe") or "M1"
                    if not isinstance(timeframe, str) or not timeframe.strip():
                        timeframe = "M1"

                    signal_schema_version_raw = event.get("signal_schema_version")
                    if isinstance(signal_schema_version_raw, str):
                        signal_schema_version = signal_schema_version_raw.strip() or "sig-v2.0.0"
                    elif signal_schema_version_raw:
                        signal_schema_version = str(signal_schema_version_raw)
                    else:
                        signal_schema_version = "sig-v2.0.0"

                    raw_signal_snapshot = event.get("signal_snapshot")
                    signal_snapshot = dict(raw_signal_snapshot) if isinstance(raw_signal_snapshot, dict) else {}
                    snapshot_source = "event.signal_snapshot"

                    logger.info(
                        "on_order_opened: snapshot_source trace_id=%s ticket=%s raw_signal_snapshot_type=%s",
                        trace_id,
                        ticket,
                        type(raw_signal_snapshot).__name__,
                    )

                    if not signal_snapshot and journal_row:
                        fallback_snapshot = {}
                        journal_active_signals = journal_row.get("active_signals")
                        journal_context_filters = journal_row.get("context_filters")
                        if journal_active_signals:
                            fallback_snapshot["active_signals"] = journal_active_signals
                        if journal_context_filters:
                            fallback_snapshot["context_filters"] = journal_context_filters
                        signal_snapshot = fallback_snapshot
                        snapshot_source = "journal_fallback"

                    signal_snapshot = _strip_excluded_signal_states(signal_snapshot)
                    snapshot_columns = _build_signal_snapshot_columns(signal_snapshot, event)

                    if trade_journal_id is not None:
                        snapshot_id = await conn.fetchval(
                            """
                            INSERT INTO aureus_trade_signal_snapshots (
                                trade_journal_id, trace_id, ticket, strategy_name, symbol, timeframe,
                                signal_schema_version,
                                atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200,
                                vol_sma_20, session,
                                candle_color_d1, candle_color_h1, candle_color_m30, candle_color_m15, candle_color_m5,
                                bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn,
                                bb_m30_up, bb_m30_dn, bb_h1_up, bb_h1_dn,
                                cisd_m5, cisd_m15, cisd_m30, cisd_h1,
                                created_at
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6,
                                $7,
                                $8, $9, $10, $11, $12, $13, $14,
                                $15, $16,
                                $17, $18, $19, $20, $21,
                                $22, $23, $24, $25, $26, $27,
                                $28, $29, $30, $31,
                                $32, $33, $34, $35,
                                $36
                            )
                            ON CONFLICT (trade_journal_id) DO NOTHING
                            RETURNING id
                            """,
                            trade_journal_id,
                            trace_id,
                            ticket,
                            strategy_name,
                            symbol,
                            timeframe,
                            signal_schema_version,
                            snapshot_columns["atr"],
                            snapshot_columns["ema_21"],
                            snapshot_columns["ema_34"],
                            snapshot_columns["ema_55"],
                            snapshot_columns["ema_89"],
                            snapshot_columns["ema_100"],
                            snapshot_columns["ema_200"],
                            snapshot_columns["vol_sma_20"],
                            snapshot_columns["session"],
                            snapshot_columns["candle_color_d1"],
                            snapshot_columns["candle_color_h1"],
                            snapshot_columns["candle_color_m30"],
                            snapshot_columns["candle_color_m15"],
                            snapshot_columns["candle_color_m5"],
                            snapshot_columns["bb_m1_up"],
                            snapshot_columns["bb_m1_dn"],
                            snapshot_columns["bb_m5_up"],
                            snapshot_columns["bb_m5_dn"],
                            snapshot_columns["bb_m15_up"],
                            snapshot_columns["bb_m15_dn"],
                            snapshot_columns["bb_m30_up"],
                            snapshot_columns["bb_m30_dn"],
                            snapshot_columns["bb_h1_up"],
                            snapshot_columns["bb_h1_dn"],
                            snapshot_columns["cisd_m5"],
                            snapshot_columns["cisd_m15"],
                            snapshot_columns["cisd_m30"],
                            snapshot_columns["cisd_h1"],
                            entry_time,
                        )
                        await conn.execute(
                            """
                            UPDATE aureus_reasoning_entries
                            SET trade_journal_id = $1,
                                signal_snapshot_id = COALESCE($2, signal_snapshot_id),
                                ticket = $3,
                                pending_order_id = COALESCE($4, pending_order_id),
                                entry_time = $5,
                                updated_at = now()
                            WHERE trace_id = $6
                            """,
                            trade_journal_id,
                            snapshot_id,
                            ticket,
                            event.get("pending_order_id"),
                            entry_time,
                            trace_id,
                        )
                        logger.info(
                            "on_order_opened: snapshot_insert trace_id=%s ticket=%s snapshot_id=%s",
                            trace_id,
                            ticket,
                            snapshot_id,
                        )
                    else:
                        logger.warning(
                            "on_order_opened: snapshot_insert skipped trace_id=%s ticket=%s reason=no_payload source=%s",
                            trace_id,
                            ticket,
                            snapshot_source,
                        )

            if updated:
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
                        "FROM aureus_trade_journal WHERE (ticket = $1 OR position_id = $1) AND status = 'EXECUTED'",
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
                    success = True if result == "WIN" else False if result == "LOSS" else None
                    reward = pnl_pips if pnl_pips is not None else pnl
                    await conn.execute(
                        """
                        UPDATE aureus_reasoning_entries
                        SET success = $1,
                            reward = $2,
                            pnl = $3,
                            pnl_pips = $4,
                            result = $5,
                            exit_time = $6,
                            evaluated_at = now(),
                            updated_at = now()
                        WHERE trace_id = $7
                        """,
                        success,
                        reward,
                        pnl,
                        pnl_pips,
                        result,
                        exit_time,
                        trace_id,
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
