"""
Signal Event Publisher — Redis pub/sub for downstream notification consumers.

Publishes signal events and strategy match events to:
  aureus:signals:{symbol}  (pub/sub channel)

Consumers: aureus-notifier (Phase 27), dashboard websocket, etc.
"""
import json
from typing import Any, Dict, Optional
from engine.logging_common import get_logger

logger = get_logger(__name__)

CHANNEL_PREFIX = "aureus:signals"


def _build_channel(symbol: str) -> str:
    return f"{CHANNEL_PREFIX}:{symbol}"


def _build_signal_snapshot_from_indicator_snapshot(indicator_snapshot: Any) -> Dict[str, Any]:
    if not isinstance(indicator_snapshot, dict):
        return {}

    snapshot: Dict[str, Any] = {}

    def _normalize_polarity(value: Any) -> Optional[int]:
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

    def _normalize_session(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            code = int(value)
            return code if code in (1, 2, 3) else None
        text = str(value).strip().upper()
        mapping = {"ASIAN": 1, "LONDON": 2, "NEWYORK": 3, "NEW_YORK": 3}
        return mapping.get(text)

    def _to_float(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
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

    ema_values = (
        ((indicator_snapshot.get("emas") or {}).get("values"))
        if isinstance(indicator_snapshot.get("emas"), dict)
        else None
    )
    if isinstance(ema_values, list):
        for idx, period in enumerate((21, 34, 55, 89, 100, 200)):
            if idx < len(ema_values) and ema_values[idx] is not None:
                snapshot[f"ema_{period}"] = ema_values[idx]

    atr_value = _to_float(indicator_snapshot.get("atr"))
    if atr_value is None:
        atr_value = _to_float(indicator_snapshot.get("atr_14"))
    if atr_value is not None:
        snapshot["atr"] = atr_value

    vol_sma_20_value = _to_float(indicator_snapshot.get("vol_sma_20"))
    if vol_sma_20_value is None:
        vol_sma_20_value = _to_float(indicator_snapshot.get("volSma20"))
    if vol_sma_20_value is None:
        vol_sma_20_value = _to_float(indicator_snapshot.get("vol_sma20"))
    if vol_sma_20_value is not None:
        snapshot["vol_sma_20"] = vol_sma_20_value

    session_code = _normalize_session(indicator_snapshot.get("session"))
    if session_code is None:
        session_code = _normalize_session(indicator_snapshot.get("market_session"))
    if session_code is not None:
        snapshot["session"] = session_code

    for tf in ("m1", "m5", "m15", "m30", "h1"):
        bb_key = f"bb_{tf}"
        bb_value = indicator_snapshot.get(bb_key)
        if isinstance(bb_value, dict):
            if bb_value.get("upper") is not None:
                snapshot[f"bb_{tf}_up"] = bb_value.get("upper")
            if bb_value.get("lower") is not None:
                snapshot[f"bb_{tf}_dn"] = bb_value.get("lower")

    candle_color_keys = {
        "candle_color_d1": ("candle_color_d1", "candle_color_D1"),
        "candle_color_h1": ("candle_color_h1", "candle_color_H1"),
        "candle_color_m30": ("candle_color_m30", "candle_color_M30"),
        "candle_color_m15": ("candle_color_m15", "candle_color_M15"),
        "candle_color_m5": ("candle_color_m5", "candle_color_M5"),
    }
    for output_key, source_keys in candle_color_keys.items():
        for source_key in source_keys:
            polarity = _normalize_polarity(indicator_snapshot.get(source_key))
            if polarity is not None:
                snapshot[output_key] = polarity
                break

    cisd_mtf = indicator_snapshot.get("cisd_mtf")
    if isinstance(cisd_mtf, dict):
        tf_map = {"M5": "cisd_m5", "M15": "cisd_m15", "M30": "cisd_m30", "H1": "cisd_h1"}
        for tf, output_key in tf_map.items():
            value = cisd_mtf.get(tf)
            if value is not None:
                snapshot[output_key] = str(value).upper()

    return snapshot


def _merge_signal_snapshots(base_snapshot: Any, fallback_snapshot: Any) -> Dict[str, Any]:
    if not isinstance(base_snapshot, dict):
        base_snapshot = {}
    if not isinstance(fallback_snapshot, dict):
        return dict(base_snapshot)

    merged = dict(base_snapshot)
    for key, value in fallback_snapshot.items():
        if merged.get(key) is None and value is not None:
            merged[key] = value
    return merged


def _resolve_strategy_match_signal_snapshot(strategy_result: Dict[str, Any], active_signals: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    signal_snapshot = strategy_result.get("normalized_signal_snapshot")
    if not isinstance(signal_snapshot, dict):
        signal_snapshot = active_signals if isinstance(active_signals, dict) else {}

    indicator_snapshot = strategy_result.get("indicator_snapshot")
    derived_signal_snapshot = _build_signal_snapshot_from_indicator_snapshot(indicator_snapshot)
    return _merge_signal_snapshots(signal_snapshot, derived_signal_snapshot)




async def publish_signal_event(
    redis_client: Any,
    symbol: str,
    event_type: str,
    t: int,
    data: Dict[str, Any],
) -> bool:
    """Publish a signal event to Redis pub/sub."""
    channel = _build_channel(symbol)
    payload = {
        "type": event_type,
        "symbol": symbol,
        "t": t,
        "data": data,
    }
    try:
        subscriber_count = await redis_client.publish(
            channel, json.dumps(payload, default=str)
        )
        logger.debug(
            f"[{symbol}] [publish_signal_event] type={event_type} t={t} "
            f"channel={channel} subscribers={subscriber_count}"
        )
        return True
    except Exception as e:
        logger.warning(f"[{symbol}] [publish_signal_event] Failed: {e}")
        return False


async def publish_strategy_match(
    redis_client: Any,
    symbol: str,
    strategy_result: Dict[str, Any],
    active_signals: Optional[Dict[str, Any]] = None,
) -> bool:
    """Publish a strategy match event to Redis pub/sub."""
    t = int(strategy_result.get("t", 0))
    strat_id = strategy_result.get("strategy_id", "")
    origin_ts = strategy_result.get("origin_timestamp", t)
    trace_id = f"{symbol}:{strat_id}:{origin_ts}"
    signal_snapshot = _resolve_strategy_match_signal_snapshot(strategy_result, active_signals)

    data = {
        "trace_id": trace_id,
        "symbol": symbol,
        "strategy": strategy_result.get("strategy"),
        "strategy_id": strategy_result.get("strategy_id"),
        "strategy_name": strategy_result.get("strategy"),
        "side": strategy_result.get("side"),
        "entry_type": strategy_result.get("entry_type", "MARKET"),
        "size_value": strategy_result.get("size_value", strategy_result.get("size")),
        "size_mode": strategy_result.get("size_mode", "FIXED_UNITS"),
        "risk_amount": strategy_result.get("risk_amount"),
        "tp_rr_ratio": strategy_result.get("tp_rr_ratio"),
        "magic_number": strategy_result.get("magic_number"),
        "sl": strategy_result.get("sl_absolute") or strategy_result.get("sl"),
        "tp": strategy_result.get("tp_absolute") or strategy_result.get("tp"),
        "sl_absolute": strategy_result.get("sl_absolute"),
        "tp_absolute": strategy_result.get("tp_absolute"),
        "reason_code": strategy_result.get("reason_code"),
        "origin_timestamp": strategy_result.get("origin_timestamp"),
        "entry_price": strategy_result.get("entry_price"),
        "direction": strategy_result.get("side"),
        "active_signals": active_signals or {},
        "signal_snapshot": signal_snapshot,
        "score_total": strategy_result.get("score_total"),
        "score_breakdown": strategy_result.get("score_breakdown"),
        "weights_snapshot": strategy_result.get("weights_snapshot"),
        "missing_data_policy": strategy_result.get("missing_data_policy"),
        "score_version": strategy_result.get("score_version"),
        "signal_schema_version": strategy_result.get("signal_schema_version"),
    }
    return await publish_signal_event(
        redis_client, symbol, "STRATEGY_MATCH", t, data
    )
