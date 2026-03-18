import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


REQUIRED_EVENT_FIELDS = ("trace_id", "symbol", "event_time")

SIDE_MAP = {
    "BUY": "BUY",
    "SELL": "SELL",
}

TYPE_MAP = {
    "MARKET": "MARKET",
    "LIMIT": "LIMIT",
    "STOP": "STOP",
}

STATUS_MAP = {
    "ORDER_ACCEPTED": "ORDER_ACCEPTED",
    "ACCEPTED": "ORDER_ACCEPTED",
    "PARTIAL_FILL": "PARTIAL_FILL",
    "PARTIALLY_FILLED": "PARTIAL_FILL",
    "FILLED": "FILLED",
    "CANCELED": "CANCELED",
    "CANCELLED": "CANCELED",
    "REJECTED": "REJECTED",
    "RISK_BLOCKED": "RISK_BLOCKED",
}


def _to_unix_seconds(value: Any) -> int:
    if value is None:
        raise ValueError("event_time is required")

    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        return int(ts)

    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError("event_time is empty")
        try:
            ts = float(value)
            if ts > 1e12:
                ts = ts / 1000.0
            return int(ts)
        except ValueError:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())

    raise ValueError(f"Unsupported timestamp value: {value!r}")


def _to_optional_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    return float(value)


def validate_required_fields(payload: Dict[str, Any], required_fields: Iterable[str] = REQUIRED_EVENT_FIELDS) -> None:
    missing = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def map_status(raw_status: Any) -> str:
    if raw_status is None:
        return "ORDER_ACCEPTED"
    normalized = str(raw_status).upper().strip()
    return STATUS_MAP.get(normalized, "REJECTED")


def map_order_intent(order_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(order_payload, dict):
        raise ValueError("order_payload must be a dict")

    trace_id = order_payload.get("trace_id")
    symbol = order_payload.get("symbol")
    event_time_raw = order_payload.get("event_time", order_payload.get("open_time"))

    intent = {
        "trace_id": trace_id,
        "symbol": symbol,
        "event_time": _to_unix_seconds(event_time_raw),
        "side": SIDE_MAP.get(str(order_payload.get("side", "BUY")).upper(), "BUY"),
        "type": TYPE_MAP.get(str(order_payload.get("type", "MARKET")).upper(), "MARKET"),
        "quantity": float(order_payload.get("quantity", 1.0)),
        "entry_price": float(order_payload.get("entry_price", 0.0)),
        "sl": _to_optional_float(order_payload.get("sl")),
        "tp": _to_optional_float(order_payload.get("tp")),
        "strategy_id": order_payload.get("strategy_id"),
        "execution_mode": order_payload.get("execution_mode", "simulated"),
    }

    validate_required_fields(intent)
    return intent


def build_execution_event(intent: Dict[str, Any], adapter_report: Dict[str, Any]) -> Dict[str, Any]:
    status = map_status(adapter_report.get("status"))

    execution_event = {
        "trace_id": intent["trace_id"],
        "symbol": intent["symbol"],
        "event_time": _to_unix_seconds(adapter_report.get("event_time", intent["event_time"])),
        "status": status,
        "side": intent["side"],
        "type": intent["type"],
        "quantity": float(adapter_report.get("quantity", intent.get("quantity", 1.0))),
        "entry_price": _to_optional_float(adapter_report.get("entry_price", intent.get("entry_price", 0.0)), 0.0),
        "fill_price": float(adapter_report.get("fill_price", intent.get("entry_price", 0.0))),
        "sl": _to_optional_float(adapter_report.get("sl", intent.get("sl"))),
        "tp": _to_optional_float(adapter_report.get("tp", intent.get("tp"))),
        "realized_pnl": _to_optional_float(adapter_report.get("realized_pnl"), 0.0),
        "unrealized_pnl": _to_optional_float(adapter_report.get("unrealized_pnl"), 0.0),
        "position_id": adapter_report.get("position_id"),
        "adapter_order_id": adapter_report.get("adapter_order_id"),
        "rejection_reason": adapter_report.get("rejection_reason"),
        "execution_mode": intent.get("execution_mode", "simulated"),
        "raw_status": adapter_report.get("status"),
        "event_version": 2,
    }

    validate_required_fields(execution_event)
    return execution_event


def parse_order_data(raw_data: Any) -> Dict[str, Any]:
    if isinstance(raw_data, dict):
        return raw_data
    if isinstance(raw_data, str):
        parsed = json.loads(raw_data)
        if not isinstance(parsed, dict):
            raise ValueError("Parsed order payload must be a JSON object")
        return parsed
    raise ValueError(f"Unsupported order data type: {type(raw_data)}")
