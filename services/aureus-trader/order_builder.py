"""
Order builder — converts STRATEGY_MATCH events into OPEN_ORDER commands.

Maps strategy match event fields to the Phase 28 D-01 OPEN_ORDER
command schema and generates deterministic idempotency keys.
"""
import hashlib


def generate_cmd_id(event: dict) -> str:
    """Generate a deterministic idempotency key from full event dict.

    Format: ord-{12-char hex md5}
    Key components: strategy_id, symbol, t, direction
    """
    data = event.get("data", {})
    symbol = event.get("symbol", "")
    # Check top-level first, then fall back to data sub-dict
    signal_ts = event.get("t") or event.get("signal_ts") or data.get("signal_ts") or data.get("t") or ""
    direction = data.get("direction") or data.get("side") or event.get("side", "")
    key_str = f"{data.get('strategy_id', event.get('strategy_id', ''))}:{symbol}:{signal_ts}:{direction}"
    hash_val = hashlib.md5(key_str.encode()).hexdigest()[:12]
    return f"ord-{hash_val}"


def build_order_command(match_event: dict) -> dict:
    """Convert a STRATEGY_MATCH event into an OPEN_ORDER command.

    Accepts both Phase 26 field names (side, sl, tp)
    and Phase 29 canonical names (direction, sl_absolute, tp_absolute).
    """
    data = match_event["data"]
    cmd_id = generate_cmd_id(match_event)

    # Accept both naming conventions
    direction = data.get("direction") or data.get("side")
    sl = data.get("sl_absolute") or data.get("sl")
    tp = data.get("tp_absolute") or data.get("tp")

    size_mode = data.get("size_mode", "FIXED_UNITS")
    risk_amount = data.get("risk_amount")

    command = {
        "type": "OPEN_ORDER",
        "symbol": match_event.get("symbol", ""),
        "cmd_id": cmd_id,
        "direction": direction,
        "order_type": data.get("entry_type", "MARKET"),
        "volume": data.get("size_value", 0),
        "price": data.get("entry_price", 0),
        "sl": sl,
        "tp": tp,
        "magic": data.get("magic_number", 0),
        "comment": _build_comment(match_event, data),
        "trace_id": data.get("trace_id", match_event.get("trace_id", "")),
    }

    # Forward size_mode and risk_amount when using RISK_FIXED_AMOUNT
    # MT5 will calculate actual lot size from real entry price and SL distance
    if size_mode == "RISK_FIXED_AMOUNT":
        command["size_mode"] = size_mode
        command["risk_amount"] = risk_amount if risk_amount else 50.0
        # Set volume=0 as placeholder — MT5 will calculate real lot
        command["volume"] = 0

    return command


def _build_comment(match_event: dict, data: dict) -> str:
    """Build MT5 comment embedding strategy_name + trace_id for journal correlation.

    Format: "strategy_name|trace_id_suffix" (max 31 chars).
    If no trace_id, falls back to strategy_name only.
    """
    strategy_name = str(
        data.get("strategy_name", data.get("strategy", data.get("strategy_id", "")))
    )
    trace_id = match_event.get("trace_id", "")
    trace_suffix = f"|{trace_id[:9]}" if trace_id else ""
    # Reserve space for trace_suffix (10 chars: "|" + 9 hex), rest for strategy name
    max_name_len = 31 - len(trace_suffix)
    return f"{strategy_name[:max_name_len]}{trace_suffix}"
