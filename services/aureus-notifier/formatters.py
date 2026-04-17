"""
Message formatters for Telegram notifications.

Formats SIGNAL_EVENT and STRATEGY_MATCH events into HTML messages
suitable for Telegram Bot API (HTML parse mode).
"""
import html
from datetime import datetime, timezone


def _format_indicator_section(snapshot: dict, precision: int = 2) -> str:
    """Format indicator snapshot as HTML lines for Telegram.

    Groups EMAs on one line, other indicators on separate lines.
    Uses em dash (—) for missing/None values.
    """
    lines = []

    # Grouped EMAs — D-09: "EMA(21/34/55/89/100/200): 2341.20/2343.50/..."
    emas = snapshot.get("emas", {})
    ema_periods = emas.get("periods", [])
    ema_values = emas.get("values", [])
    ema_markers = emas.get("cross_markers", [])

    if ema_values:
        ema_parts = []
        for i, val in enumerate(ema_values):
            if val is not None:
                marker = ema_markers[i] if i < len(ema_markers) else ""
                ema_parts.append(f"{val:.{precision}f}{marker}")
            else:
                ema_parts.append("\u2014")  # —
        period_str = "/".join(str(p) for p in ema_periods)
        value_str = "/".join(ema_parts)
        lines.append(f"\u2022 <b>EMA({period_str})</b>: {html.escape(value_str)}")

    # ATR(14) — D-09: "ATR(14): 12.34"
    atr = snapshot.get("atr_14")
    atr_display = f"{atr:.{precision}f}" if atr is not None else "\u2014"
    lines.append(f"\u2022 <b>ATR(14)</b>: {html.escape(atr_display)}")

    # Volume SMA(20) — D-09
    vol = snapshot.get("vol_sma_20")
    vol_display = f"{vol:.0f}" if vol is not None else "\u2014"
    lines.append(f"\u2022 <b>Vol SMA(20)</b>: {html.escape(vol_display)}")

    # HTF Trend — D-11: "HTF Trend: BULLISH"
    htf = snapshot.get("htf_trend")
    htf_display = html.escape(str(htf)) if htf else "\u2014"
    emoji_map = {"BULLISH": "\U0001F7E2", "BEARISH": "\U0001F534", "NEUTRAL": "\u26AA"}
    htf_emoji = emoji_map.get(htf, "")
    if htf_emoji:
        lines.append(f"\u2022 <b>HTF Trend</b>: {htf_emoji} {htf_display}")
    else:
        lines.append(f"\u2022 <b>HTF Trend</b>: {htf_display}")

    # CISD Multi-TF — show each TF on its own line
    cisd_mtf = snapshot.get("cisd_mtf") or {}
    status_emoji = {
        "bullish": "\U0001F7E2",  # 🟢
        "bearish": "\U0001F534",  # 🔴
    }
    lines.append("\u2022 <b>CISD MTF</b>:")
    for tf in ("M5", "M15", "M30", "H1"):
        status = cisd_mtf.get(tf)
        if status:
            emoji = status_emoji.get(status, "")
            lines.append(f"  \u2022 {tf}: {emoji} {status.capitalize()}")
        else:
            lines.append(f"  \u2022 {tf}: \u2014")  # — no tracking

    # Candle Color MTF
    color_emoji = {
        "BULLISH": "\U0001F7E2",  # 🟢
        "BEARISH": "\U0001F534",  # 🔴
        "DOJI": "\u26AA",         # ⚪
    }
    lines.append("\u2022 <b>Candle Color MTF</b>:")
    for tf in ("D1", "H1", "M30", "M15", "M5"):
        val = snapshot.get(f"candle_color_{tf.lower()}")
        if val:
            emoji = color_emoji.get(str(val).upper(), "")
            lines.append(f"  \u2022 {tf}: {emoji} {html.escape(str(val))}")
        else:
            lines.append(f"  \u2022 {tf}: \u2014")

    # Bollinger Bands MTF
    def _fmt_bb(bb: dict | None) -> str:
        if not bb or not isinstance(bb, dict):
            return "\u2014"
        upper = bb.get("upper")
        middle = bb.get("middle")
        lower = bb.get("lower")
        if upper is None or middle is None or lower is None:
            return "\u2014"
        return html.escape(f"U:{upper:.{precision}f} M:{middle:.{precision}f} L:{lower:.{precision}f}")

    lines.append("\u2022 <b>BB MTF</b>:")
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        lines.append(f"  \u2022 {tf}: {_fmt_bb(snapshot.get(f'bb_{tf.lower()}'))}")

    return "\n".join(lines)


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

            if key in ("cisd_bull", "cisd_bear") and "value" in val:
                pct = val["value"]
                close = val.get("close")
                if close is not None:
                    return f"{pct}% (Close: {close})"
                return f"{pct}%"

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

    # Filter out CISD MTF tags from Active Signals — they're shown in Indicator Snapshot
    import re
    _CISD_MTF_RE = re.compile(r"^cisd_(m5|m15|m30|h1|h4)_(bullish|bearish)$", re.IGNORECASE)
    signals = {k: v for k, v in signals.items() if not _CISD_MTF_RE.match(str(k))}

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

    # Indicator Snapshot section — D-08: AFTER "Active Signals", BEFORE hashtags
    indicator_snapshot = data.get("indicator_snapshot")
    indicator_section = ""
    if indicator_snapshot and isinstance(indicator_snapshot, dict):
        # Infer precision:
        # 1. Try from digits in snapshot (passed from engine symbols config)
        # 2. Try from close price in signals (most accurate for current symbol)
        # 3. Try from symbol name (standard forex/metal precision)
        # 4. Default to 2
        precision = 2

        # Method 1: Digits from snapshot
        if "digits" in indicator_snapshot:
            try:
                precision = int(indicator_snapshot["digits"])
            except (ValueError, TypeError):
                pass
        else:
            # Method 2: Signals close
            found_in_signals = False
            for s_val in signals.values():
                if isinstance(s_val, dict) and "close" in s_val:
                    close_str = str(s_val["close"])
                    if "." in close_str:
                        precision = len(close_str.split(".")[1])
                    found_in_signals = True
                    break

            # Method 3: Symbol name heuristics (if not found in signals)
            if not found_in_signals:
                sym_upper = str(event.get("symbol", "")).upper()
                if any(major in sym_upper for major in ["EUR", "GBP", "AUD", "NZD", "USD", "CHF", "CAD"]):
                    if "JPY" in sym_upper:
                        precision = 3
                    elif "XAU" in sym_upper or "GOLD" in sym_upper:
                        precision = 2
                    else:
                        precision = 5
                elif "BTC" in sym_upper or "ETH" in sym_upper:
                    precision = 2

        parts.append('')
        indicator_section = _format_indicator_section(indicator_snapshot, precision=precision)
        parts.append('<b>\U0001F4C8 Indicator Snapshot:</b>')
        parts.append(indicator_section)

    parts.append('')
    parts.append(f'#{symbol} #Signal')

    # D-10: Safety truncate — if message >4095 chars, remove indicator section first
    message = "\n".join(parts)
    if len(message) > 4095:
        # Try without indicator section
        if indicator_section:
            parts_without_indicator = [p for p in parts if p != indicator_section and p != '<b>\U0001F4C8 Indicator Snapshot:</b>']
            message = "\n".join(parts_without_indicator)
        if len(message) > 4095:
            # Hard truncate as last resort
            message = message[:4095]
    return message


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
    order_plan = data.get("order_plan", {})
    entry_method = order_plan.get("entry_method", "CURRENT")
    method_suffix = f" - {entry_method}" if entry_method != "CURRENT" else ""

    if entry_type.upper() == "MARKET":
        entry_display = format_price(entry_price)
        entry_label = f"<b>Entry (Market{method_suffix}):</b> {entry_display}"
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
        entry_label = f"<b>Entry (Limit{method_suffix}):</b> {entry_display}"
    else:
        entry_display = format_price(entry_price)
        entry_label = f"<b>Entry ({entry_type}{method_suffix}):</b> {entry_display}"

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
