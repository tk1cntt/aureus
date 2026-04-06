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
    if signals:
        signals_lines = "\n".join(
            f"• {html.escape(str(k))}: {html.escape(str(v))}"
            for k, v in signals.items()
        )
    else:
        signals_lines = "• (no active signals)"

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
    entry_type = html.escape(str(data.get("entry_type", "UNKNOWN")))
    reason_code = html.escape(str(data.get("reason_code", "")))

    sl = data.get("sl_absolute") or data.get("sl")
    tp = data.get("tp_absolute") or data.get("tp")
    size_value = data.get("size_value", "N/A")

    def format_price(val):
        if val is None:
            return "N/A"
        if isinstance(val, dict):
            # Fallback if uncalculated config leaks
            return "Auto (Calculated at Entry)"
        try:
            return f"{float(val):.5f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            return str(val)

    sl_display = format_price(sl)
    tp_display = format_price(tp)

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
        f'<b>Entry Type:</b> {entry_type}',
        f'',
        f'<b>Trade Plan:</b>',
        f'• SL: {sl_display}',
        f'• TP: {tp_display}',
        f'• Size: {size_value} lot',
        f'• Risk: N/A',
        f'',
        f'<b>Reason:</b> {reason_code}',
        f'<b>Time:</b> {utc_time} UTC',
        f'',
        f'#{symbol} #{strategy} #{side}',
    ]

    message = "\n".join(parts)
    return message[:4095]  # Telegram limit is 4096 chars
