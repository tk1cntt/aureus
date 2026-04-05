"""
Snapshot Utilities — Shared functions for building + inserting signal snapshots.
Used by: live engine (main.py), signal_computer.py, and recovery (recalculate_all_signals).
"""
import json
import logging
from engine.logging_common import get_logger
import os
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = get_logger(__name__)
SPEC_VERSION = "2026-03-20-live-trading-v1"
ENGINE_VERSION = os.getenv("AUREUS_SIGNAL_ENGINE_VERSION", "live-engine-v1")

MANDATORY_SIGNAL_KEYS = (
    "zigzag_state",
    "ob_state",
    "choch_state",
    "fvg_state",
    "trend_filter_state",
)

REQUIRED_TOP_LEVEL_TRACE_KEYS = (
    "trace_id",
    "decision_status",
    "decision_timestamp",
    "symbol",
    "timeframe",
    "strategy_id",
    "strategy_version",
    "spec_version",
    "engine_version",
    "correlation_id",
)

REQUIRED_MARKET_SNAPSHOT_KEYS = (
    "bar_timestamp",
    "bar_ohlcv",
    "spread",
    "session_label",
    "backfill_status",
    "data_window_start",
    "data_window_end",
    "data_window_hash",
)

REQUIRED_FLOW_INTEGRITY_KEYS = (
    "current_state",
    "next_state",
    "transition_allowed",
    "validator_passed",
    "validator_failures",
)

REQUIRED_ORDER_PLAN_KEYS = (
    "entry_type",
    "entry_policy",
    "sl_mode",
    "sl_value",
    "tp_mode",
    "tp_value",
    "trailing_mode",
    "trailing_value",
    "size_mode",
    "size_value",
    "expiry_policy",
)

VALID_ENTRY_TYPES = ("MARKET", "LIMIT", "STOP")
VALID_SIZE_MODES = ("FIXED_UNITS", "FIXED_LOT", "RISK_PERCENT")


class DecisionTraceValidationError(ValueError):
    """Raised when a decision trace payload does not match required schema."""


def build_decision_trace(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build a decision-trace payload with required top-level blocks for Phase 9."""
    trace = {
        "trace_id": context.get("trace_id"),
        "decision_status": context.get("decision_status"),
        "decision_timestamp": context.get("decision_timestamp"),
        "symbol": context.get("symbol"),
        "timeframe": context.get("timeframe"),
        "strategy_id": context.get("strategy_id"),
        "strategy_version": context.get("strategy_version"),
        "spec_version": context.get("spec_version", SPEC_VERSION),
        "engine_version": context.get("engine_version", ENGINE_VERSION),
        "correlation_id": context.get("correlation_id"),
        "market_snapshot": context.get("market_snapshot", {}),
        "signals": context.get("signals", {}),
        "evaluated_rules": context.get("evaluated_rules", []),
        "flow_integrity": context.get("flow_integrity", {}),
    }

    order_plan_snapshot = context.get("order_plan_snapshot", context.get("order_plan"))
    if order_plan_snapshot is not None:
        trace["order_plan_snapshot"] = order_plan_snapshot

    return trace


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _require_keys(payload: Dict[str, Any], keys: tuple[str, ...], scope: str) -> None:
    for key in keys:
        if _is_missing(payload.get(key)):
            raise DecisionTraceValidationError(f"Missing required key `{scope}.{key}`")


def validate_decision_trace(trace: Dict[str, Any]) -> bool:
    """Validate trace payload according to `SPEC_DECISION_TRACE_SCHEMA` quality gates."""
    _require_keys(trace, REQUIRED_TOP_LEVEL_TRACE_KEYS, "trace")

    status = str(trace.get("decision_status")).upper()
    if status not in {"ACCEPTED", "REJECTED"}:
        raise DecisionTraceValidationError("`decision_status` must be ACCEPTED or REJECTED")

    market_snapshot = trace.get("market_snapshot")
    if not isinstance(market_snapshot, dict):
        raise DecisionTraceValidationError("`market_snapshot` must be an object")
    _require_keys(market_snapshot, REQUIRED_MARKET_SNAPSHOT_KEYS, "market_snapshot")

    signals = trace.get("signals")
    if not isinstance(signals, dict):
        raise DecisionTraceValidationError("`signals` must be an object")
    _require_keys(signals, MANDATORY_SIGNAL_KEYS, "signals")

    evaluated_rules = trace.get("evaluated_rules")
    if not isinstance(evaluated_rules, list) or not evaluated_rules:
        raise DecisionTraceValidationError("`evaluated_rules` must be a non-empty list")

    if status == "REJECTED":
        has_fail = any(str(rule.get("result", "")).upper() == "FAIL" for rule in evaluated_rules if isinstance(rule, dict))
        if not has_fail:
            raise DecisionTraceValidationError("Rejected traces require at least one FAIL rule")

    flow_integrity = trace.get("flow_integrity")
    if not isinstance(flow_integrity, dict):
        raise DecisionTraceValidationError("`flow_integrity` must be an object")
    _require_keys(flow_integrity, REQUIRED_FLOW_INTEGRITY_KEYS, "flow_integrity")

    if status == "ACCEPTED":
        order_plan = trace.get("order_plan_snapshot")
        if not isinstance(order_plan, dict):
            raise DecisionTraceValidationError("Accepted traces require `order_plan_snapshot`")
        _require_keys(order_plan, REQUIRED_ORDER_PLAN_KEYS, "order_plan_snapshot")

    return True


def build_snapshot(state, candle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collects all signal values from state into a flat dict for DB insertion.
    
    Args:
        state: SymbolState instance (after signal calculation for this candle)
        candle: Raw candle dict with 't', 'o', 'h', 'l', 'c', 'v', 'symbol'
    Returns:
        Dict ready for INSERT into aureus_signal_snapshots
    """
    ts_unix = int(candle['t'])
    dt = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
    symbol = candle.get('symbol', state.symbol)

    def _get_ema_val(period: int) -> float:
        v = state.emas.get(period)
        return v.get('current') if isinstance(v, dict) else v

    # Collect EMA values
    ema_21 = _get_ema_val(21)
    ema_34 = _get_ema_val(34)
    ema_55 = _get_ema_val(55)
    ema_89 = _get_ema_val(89)
    ema_100 = _get_ema_val(100)
    ema_200 = _get_ema_val(200)

    # Collect events from transient_signals
    events = None
    if state.transient_signals:
        events = json.dumps(list(state.transient_signals.values()))

    # Collect active (non-mitigated) OBs — limit to 10 most recent
    active_obs = None
    if hasattr(state, 'obs') and state.obs:
        live_obs = [ob for ob in state.obs if not ob.get('mitigated', False)][-10:]
        if live_obs:
            active_obs = json.dumps(live_obs)

    # Phase 7: Full OBs snapshot (all OBs, limit 20 most recent)
    obs_full = None
    if hasattr(state, 'obs') and state.obs:
        obs_full = json.dumps(state.obs[-20:])

    # Phase 7: Swing points snapshot (last 50)
    swing_points_snapshot = None
    if hasattr(state, 'swing_points') and state.swing_points:
        swing_points_snapshot = json.dumps(state.swing_points[-50:])

    # Phase 7: Strategy progress
    strategy_progress = None
    if hasattr(state, 'strategy_progress') and state.strategy_progress:
        strategy_progress = json.dumps(state.strategy_progress)

    # Detect swing label if swing_points was just updated
    swing_label = None
    if state.swing_points:
        last_sp = state.swing_points[-1]
        if last_sp.get('t') == ts_unix:
            swing_label = last_sp.get('type', 'HH' if last_sp.get('is_high') else 'LL')

    return {
        'time': dt,
        'symbol': symbol,
        'atr': state.atr if state.atr else None,
        'ema_21': ema_21,
        'ema_34': ema_34,
        'ema_55': ema_55,
        'ema_89': ema_89,
        'ema_100': ema_100,
        'ema_200': ema_200,
        'vol_sma_20': state.vol_sma_20 if hasattr(state, 'vol_sma_20') else None,
        'htf_trend': getattr(state, 'htf_trend', None),
        'market_regime': getattr(state, 'market_regime', None),
        'session': getattr(state, 'current_session', None),
        'events': events,
        'active_obs': active_obs,
        'swing_label': swing_label,
        # Phase 7: New fields for live/backtest data unification
        'aci': getattr(state, 'aci', 0),
        'sentiment': getattr(state, 'sentiment', 'NEUTRAL'),
        'narrative': getattr(state, 'narrative', None),
        'obs_full': obs_full,
        'swing_points_snapshot': swing_points_snapshot,
        'strategy_progress': strategy_progress,
    }


async def insert_single_snapshot(db_pool, snapshot: Dict[str, Any], table_name: str = "aureus_signal_snapshots"):
    """
    Insert a single snapshot row. Fire-and-forget safe.
    Uses ON CONFLICT DO UPDATE for idempotency.
    """
    try:
        query = f"""
            INSERT INTO {table_name} 
                (time, symbol, atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200,
                 vol_sma_20, htf_trend, market_regime, session, events, active_obs, swing_label,
                 aci, sentiment, narrative, obs_full, swing_points_snapshot, strategy_progress)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                    $17, $18, $19, $20, $21, $22)
            ON CONFLICT (time, symbol) DO UPDATE SET
                atr = EXCLUDED.atr,
                ema_21 = EXCLUDED.ema_21, ema_34 = EXCLUDED.ema_34,
                ema_55 = EXCLUDED.ema_55, ema_89 = EXCLUDED.ema_89,
                ema_100 = EXCLUDED.ema_100, ema_200 = EXCLUDED.ema_200,
                vol_sma_20 = EXCLUDED.vol_sma_20,
                htf_trend = EXCLUDED.htf_trend,
                market_regime = EXCLUDED.market_regime,
                session = EXCLUDED.session,
                events = EXCLUDED.events,
                active_obs = EXCLUDED.active_obs,
                swing_label = EXCLUDED.swing_label,
                aci = EXCLUDED.aci,
                sentiment = EXCLUDED.sentiment,
                narrative = EXCLUDED.narrative,
                obs_full = EXCLUDED.obs_full,
                swing_points_snapshot = EXCLUDED.swing_points_snapshot,
                strategy_progress = EXCLUDED.strategy_progress
        """
        await db_pool.execute(query,
            snapshot['time'], snapshot['symbol'],
            snapshot['atr'], snapshot['ema_21'], snapshot['ema_34'],
            snapshot['ema_55'], snapshot['ema_89'], snapshot['ema_100'], snapshot['ema_200'],
            snapshot['vol_sma_20'],
            snapshot['htf_trend'], snapshot['market_regime'], snapshot['session'],
            snapshot['events'], snapshot['active_obs'], snapshot['swing_label'],
            snapshot.get('aci', 0), snapshot.get('sentiment', 'NEUTRAL'),
            snapshot.get('narrative'), snapshot.get('obs_full'),
            snapshot.get('swing_points_snapshot'), snapshot.get('strategy_progress'),
        )
    except Exception as e:
        logger.warning(f"[Snapshot] Insert into {table_name} failed for {snapshot.get('symbol')} @ {snapshot.get('time')}: {e}")


async def batch_insert_snapshots(db_pool, snapshots: List[Dict[str, Any]], table_name: str = "aureus_signal_snapshots"):
    """
    Batch insert multiple snapshot rows efficiently.
    Uses ON CONFLICT DO UPDATE for idempotency.
    """
    if not snapshots:
        return 0

    try:
        async with db_pool.acquire() as conn:
            # Use prepared statement for batch performance
            query = f"""
                INSERT INTO {table_name} 
                    (time, symbol, atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200,
                     vol_sma_20, htf_trend, market_regime, session, events, active_obs, swing_label,
                     aci, sentiment, narrative, obs_full, swing_points_snapshot, strategy_progress)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                        $17, $18, $19, $20, $21, $22)
                ON CONFLICT (time, symbol) DO UPDATE SET
                    atr = EXCLUDED.atr,
                    ema_21 = EXCLUDED.ema_21, ema_34 = EXCLUDED.ema_34,
                    ema_55 = EXCLUDED.ema_55, ema_89 = EXCLUDED.ema_89,
                    ema_100 = EXCLUDED.ema_100, ema_200 = EXCLUDED.ema_200,
                    vol_sma_20 = EXCLUDED.vol_sma_20,
                    htf_trend = EXCLUDED.htf_trend,
                    market_regime = EXCLUDED.market_regime,
                    session = EXCLUDED.session,
                    events = EXCLUDED.events,
                    active_obs = EXCLUDED.active_obs,
                    swing_label = EXCLUDED.swing_label,
                    aci = EXCLUDED.aci,
                    sentiment = EXCLUDED.sentiment,
                    narrative = EXCLUDED.narrative,
                    obs_full = EXCLUDED.obs_full,
                    swing_points_snapshot = EXCLUDED.swing_points_snapshot,
                    strategy_progress = EXCLUDED.strategy_progress
            """
            stmt = await conn.prepare(query)
            
            for s in snapshots:
                await stmt.fetch(
                    s['time'], s['symbol'],
                    s['atr'], s['ema_21'], s['ema_34'],
                    s['ema_55'], s['ema_89'], s['ema_100'], s['ema_200'],
                    s['vol_sma_20'],
                    s['htf_trend'], s['market_regime'], s['session'],
                    s['events'], s['active_obs'], s['swing_label'],
                    s.get('aci', 0), s.get('sentiment', 'NEUTRAL'),
                    s.get('narrative'), s.get('obs_full'),
                    s.get('swing_points_snapshot'), s.get('strategy_progress'),
                )
        
        return len(snapshots)
    except Exception as e:
        logger.error(f"[Snapshot] Batch insert failed ({len(snapshots)} rows): {e}")
        return 0
