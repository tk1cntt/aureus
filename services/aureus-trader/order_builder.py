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

    return {
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
        "comment": str(data.get("strategy_id", "")),
    }
