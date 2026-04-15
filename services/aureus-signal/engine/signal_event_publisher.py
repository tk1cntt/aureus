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
    }
    return await publish_signal_event(
        redis_client, symbol, "STRATEGY_MATCH", t, data
    )
