"""
Order builder — converts STRATEGY_MATCH events into OPEN_ORDER commands.

Maps strategy match event fields to the Phase 28 D-01 OPEN_ORDER
command schema and generates deterministic idempotency keys.
"""
import hashlib


def generate_cmd_id(data: dict) -> str:
    """Generate a deterministic idempotency key from event data.

    Format: ord-{12-char hex md5}
    Key components: strategy_id, symbol, signal_ts, direction
    """
    symbol = data.get("symbol", "")
    signal_ts = data.get("signal_ts", data.get("t", ""))
    key_str = f"{data['strategy_id']}:{symbol}:{signal_ts}:{data['direction']}"
    hash_val = hashlib.md5(key_str.encode()).hexdigest()[:12]
    return f"ord-{hash_val}"


def build_order_command(match_event: dict) -> dict:
    """Convert a STRATEGY_MATCH event into an OPEN_ORDER command.

    Maps fields per the D-04 mapping spec:
    - entry_type → order_type
    - size_value → volume
    - sl_absolute → sl
    - tp_absolute → tp
    - magic_number → magic
    - strategy_id → comment
    """
    data = match_event["data"]
    cmd_id = generate_cmd_id(data)

    return {
        "type": "OPEN_ORDER",
        "symbol": match_event["symbol"],
        "cmd_id": cmd_id,
        "direction": data["direction"],
        "order_type": data["entry_type"],
        "volume": data["size_value"],
        "price": data.get("entry_price", 0),
        "sl": data["sl_absolute"],
        "tp": data["tp_absolute"],
        "magic": data["magic_number"],
        "comment": data["strategy_id"],
    }
