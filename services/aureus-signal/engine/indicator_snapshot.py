"""
Indicator Snapshot — Lightweight helper for building Telegram-friendly indicator snapshots.

Unlike build_snapshot() in snapshot_utils.py (which includes OB lists, swing points,
strategy progress, etc.), this function extracts only the values needed for display.
"""
from typing import Dict, Any


def build_indicator_snapshot_for_telegram(state) -> Dict[str, Any]:
    """Build a lightweight indicator snapshot for Telegram notification.

    Collects current indicator values from state. Designed for display,
    not DB storage — omits heavy fields (OB lists, swing points, etc.).

    Args:
        state: SymbolState instance (after signal calculation for current candle)

    Returns:
        Dict with keys: emas, atr_14, vol_sma_20, htf_trend, digits
        All values are primitive types (no enums, no complex objects).
    """
    from engine.orders import get_symbol_digits
    transient = getattr(state, "transient_signals", None) or {}

    def _get_ema_val(period: int):
        """Get current EMA value from state.emas dict."""
        v = state.emas.get(period) if hasattr(state, 'emas') else None
        if isinstance(v, dict):
            return v.get("current")
        return v

    def _ema_cross_marker(period: int) -> str:
        """Check if EMA cross occurred in current candle. Returns emoji or empty string."""
        tag_up = f"ema_{period}_up"
        tag_down = f"ema_{period}_down"
        ema_data = transient.get(tag_up) or transient.get(tag_down)
        if isinstance(ema_data, dict):
            cross = ema_data.get("data", {}).get("cross")
            if cross:
                cross_str = str(cross)
                if "cross_up" in cross_str:
                    return " \U0001F4C8"  # 📈
                if "cross_down" in cross_str:
                    return " \U0001F4C9"  # 📉
        return ""

    ema_periods = [21, 34, 55, 89, 100, 200]
    ema_values = [_get_ema_val(p) for p in ema_periods]
    ema_markers = [_ema_cross_marker(p) for p in ema_periods]

    # CISD Multi-TF status — extract current status per TF from transient_signals
    cisd_mtf = {}
    for tf_lower in ("m5", "m15", "m30", "h1", "h4"):
        for status in ("bullish", "bearish"):
            tag = f"cisd_{tf_lower}_{status}"
            if tag in transient:
                cisd_mtf[tf_lower.upper()] = status
                break

    return {
        "emas": {
            "periods": ema_periods,
            "values": ema_values,
            "cross_markers": ema_markers,
        },
        "atr_14": getattr(state, "atr", None),
        "vol_sma_20": getattr(state, "vol_sma_20", None),
        "htf_trend": getattr(state, "htf_trend", None),
        "cisd_mtf": cisd_mtf if cisd_mtf else None,
        "digits": get_symbol_digits(state.symbol) if hasattr(state, 'symbol') else 2,
    }
