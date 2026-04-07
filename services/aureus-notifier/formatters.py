"""
Message formatters for Telegram notifications.

Formats SIGNAL_EVENT and STRATEGY_MATCH events into HTML messages
suitable for Telegram Bot API (HTML parse mode).
"""
import html
from datetime import datetime, timezone


def format_signal_event(event: dict) -> str:
    """Format a SIGNAL_EVENT into an HTML message for Telegram.

    Args:
        event: dict with keys {type, symbol, t, data} where data contains
               {signals: dict, session: str}

    Returns:
        HTML-formatted string under 4096 chars.
    """
    symbol = html.escape(str(event.get("symbol", "UNKNOWN")))
    t = event.get("t", 0)
    utc_time = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    data = event.get("data", {})
    session = data.get("session")
    signals = data.get("signals", {})

    # Build signals section
    if not signals:
        return ""
        
    def format_signal_value(key: str, val) -> str:
        if isinstance(val, dict):
            if key == "ob_state" and "active_obs" in val:
                bull = sum(1 for ob in val.get("active_obs", []) if ob.get("ob_type") == "BULLISH")
                bear = sum(1 for ob in val.get("active_obs", []) if ob.get("ob_type") == "BEARISH")
                return f"{bull} Bullish / {bear} Bearish OBs"
            if key == "zigzag_state":
                status = val.get("status", "UNKNOWN")
                if "last_pivot" in val and isinstance(val["last_pivot"], dict):
                    return html.escape(f"{status} (Last: {val['last_pivot'].get('type', '?')})")
                return html.escape(status)
            
            if "value" in val:
                return html.escape(str(val["value"]))
            
            if "ob_type" in val and "top" in val and "bottom" in val:
                ob_type = html.escape(str(val.get("ob_type", "")))
                bottom = html.escape(str(val.get("bottom", "?")))
                top = html.escape(str(val.get("top", "?")))
                status = html.escape(str(val.get("status", "UNKNOWN")))
                return f"{ob_type.capitalize()} {bottom} - {top} (Status: {status})"
            inner_keys = ", ".join(str(k) for k in val.keys())
            return html.escape(f"[Detail: {inner_keys}]")
        return html.escape(str(val))

    signals_lines = "\n".join(
        f"• <b>{html.escape(str(k))}</b>: {format_signal_value(str(k), v)}"
        for k, v in signals.items()
    )

    # Build message
    parts = [
        f'📊 <b>SIGNAL ALERT</b>',
        f'━━━━━━━━━━━━━━━━━━━',
        f'<b>Symbol:</b> {symbol}',
        f'<b>Time:</b> {utc_time} UTC',
    ]

    if session:
        parts.append(f'<b>Session:</b> {html.escape(str(session))}')

    parts.append('')
    parts.append('<b>Active Signals:</b>')
    parts.append(signals_lines)
    parts.append('')
    parts.append(f'#{symbol} #Signal')

    message = "\n".join(parts)
    return message[:4095]  # Telegram limit is 4096 chars


def format_strategy_match(event: dict) -> str:
    """Format a STRATEGY_MATCH into an HTML message for Telegram.

    Args:
        event: dict with keys {type, symbol, t, data} where data contains
               {strategy, strategy_id, side, entry_type, sl, tp, size_value, reason_code}

    Returns:
        HTML-formatted string under 4096 chars.
    """
    symbol = html.escape(str(event.get("symbol", "UNKNOWN")))
    t = event.get("t", 0)
    utc_time = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    data = event.get("data", {})

    strategy = html.escape(str(data.get("strategy", "UNKNOWN")))
    strategy_id = data.get("strategy_id", "?")
    side = html.escape(str(data.get("side", "UNKNOWN")))
    entry_type = html.escape(str(data.get("entry_type", "MARKET")))
    reason_code = html.escape(str(data.get("reason_code", "")))

    sl = data.get("sl_absolute") or data.get("sl")
    tp = data.get("tp_absolute") or data.get("tp")
    size_value = data.get("size_value", "N/A")
    entry_price = data.get("entry_price")

    def format_price(val):
        if val is None:
            return "N/A"
        if isinstance(val, dict):
            # Fallback if uncalculated config leaks
            return "Auto (Calculated at Entry)"

        # Calculate precision statically from entry_price, fallback to 5
        entry_price_str = str(data.get("entry_price", ""))
        num_decimals = 5
        if "." in entry_price_str:
            num_decimals = len(entry_price_str.split(".")[1])

        try:
            v = float(val)
            return f"{v:.{num_decimals}f}"
        except (ValueError, TypeError):
            return str(val)

    sl_display = format_price(sl)
    tp_display = format_price(tp)

    # Entry price display based on entry_type
    if entry_type.upper() == "MARKET":
        entry_display = format_price(entry_price)
        entry_label = f"<b>Entry (Market):</b> {entry_display}"
    elif entry_type.upper() == "LIMIT":
        limit_price = data.get("entry_price") or data.get("limit_price")
        if limit_price and not isinstance(limit_price, dict):
            try:
                lp = float(limit_price)
                # Use limit price precision
                lp_str = str(limit_price)
                num_decimals = 5
                if "." in lp_str:
                    num_decimals = len(lp_str.split(".")[1])
                entry_display = f"{lp:.{num_decimals}f}"
            except (ValueError, TypeError):
                entry_display = str(limit_price)
        else:
            entry_display = "N/A (pending limit)"
        entry_label = f"<b>Entry (Limit):</b> {entry_display}"
    else:
        entry_display = format_price(entry_price)
        entry_label = f"<b>Entry ({entry_type}):</b> {entry_display}"

    # Direction emoji
    if side.upper() == "BUY":
        direction_emoji = "🟢"
    elif side.upper() == "SELL":
        direction_emoji = "🔴"
    else:
        direction_emoji = "⚪"

    parts = [
        f'🎯 <b>STRATEGY MATCH</b>',
        f'━━━━━━━━━━━━━━━━━━━',
        f'<b>Symbol:</b> {symbol}',
        f'<b>Strategy:</b> {strategy} #{strategy_id}',
        f'<b>Direction:</b> {side} {direction_emoji}',
        entry_label,
        f'',
        f'<b>Trade Plan:</b>',
        f'• SL: {sl_display}',
        f'• TP: {tp_display}',
        f'• Size: {size_value} lot',
        f'',
        f'<b>Reason:</b> {reason_code}',
        f'<b>Time:</b> {utc_time} UTC',
        f'',
        f'#{symbol} #{strategy} #{side}',
    ]

    message = "\n".join(parts)
    return message[:4095]  # Telegram limit is 4096 chars
