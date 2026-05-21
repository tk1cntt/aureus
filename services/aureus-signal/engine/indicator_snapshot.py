"""
Indicator Snapshot — Lightweight helper for building Telegram-friendly indicator snapshots.

Unlike build_snapshot() in snapshot_utils.py (which includes OB lists, swing points,
strategy progress, etc.), this function extracts only the values needed for display.
"""
from typing import Dict, Any, Optional

import pandas as pd

from engine.mtf_snapshot import build_mtf_candle_color_map, build_bb_payload
from engine.signals.resampler import resample_to_tf


BB_TFS = ("M1", "M5", "M15", "M30", "H1")


def _compute_bb_lines_from_df(df: Optional[pd.DataFrame], period: int = 20, std_mult: float = 2.0) -> Optional[Dict[str, float]]:
    if df is None or len(df) < period or "c" not in df.columns:
        return None

    closes = pd.to_numeric(df["c"], errors="coerce").dropna()
    if len(closes) < period:
        return None

    window = closes.iloc[-period:]
    middle = float(window.mean())
    std = float(window.std(ddof=0))
    upper = middle + (std_mult * std)
    lower = middle - (std_mult * std)
    return {"upper": upper, "middle": middle, "lower": lower}


def _build_bb_by_tf_from_m1_df(m1_df: Optional[pd.DataFrame]) -> Dict[str, Optional[Dict[str, float]]]:
    bb_by_tf: Dict[str, Optional[Dict[str, float]]] = {}

    if m1_df is None or len(m1_df) == 0:
        for tf in BB_TFS:
            bb_by_tf[tf] = None
        return bb_by_tf

    for tf in BB_TFS:
        if tf == "M1":
            tf_df = m1_df
        else:
            tf_df = resample_to_tf(m1_df, tf)
            if tf_df is not None and len(tf_df) >= 2:
                tf_df = tf_df.iloc[:-1]
        bb_by_tf[tf] = _compute_bb_lines_from_df(tf_df)

    return bb_by_tf


def build_indicator_snapshot_for_telegram(state, m1_df=None) -> Dict[str, Any]:
    """Build a lightweight indicator snapshot for Telegram notification.

    Collects current indicator values from state. Designed for display,
    not DB storage — omits heavy fields (OB lists, swing points, etc.).

    Args:
        state: SymbolState instance (after signal calculation for current candle)
        m1_df: M1 OHLCV DataFrame used for candle color and BB computation

    Returns:
        Dict with keys: emas, atr_14, vol_sma_20, htf_trend, digits,
            candle_color_{tf}, bb_{tf}
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
                    return " 📈"
                if "cross_down" in cross_str:
                    return " 📉"
        return ""

    ema_periods = [21, 34, 55, 89, 100, 200]
    ema_values = [_get_ema_val(p) for p in ema_periods]
    ema_markers = [_ema_cross_marker(p) for p in ema_periods]

    cisd_mtf = {}
    for tf_lower in ("m5", "m15", "m30", "h1", "h4"):
        for status in ("bullish", "bearish"):
            tag = f"cisd_{tf_lower}_{status}"
            if tag in transient:
                cisd_mtf[tf_lower.upper()] = status
                break

    digits = get_symbol_digits(state.symbol) if hasattr(state, 'symbol') else 2

    source_df = m1_df
    candle_color_fields = {
        "candle_color_d1": None,
        "candle_color_h1": None,
        "candle_color_m30": None,
        "candle_color_m15": None,
        "candle_color_m5": None,
    }
    if isinstance(source_df, pd.DataFrame):
        candle_color_fields = build_mtf_candle_color_map(source_df, digits)

    state_bb = getattr(state, "bb_by_tf", None)
    bb_by_tf = state_bb if isinstance(state_bb, dict) else _build_bb_by_tf_from_m1_df(source_df)
    bb_fields = build_bb_payload(bb_by_tf)

    tpo_profile = getattr(state, "tpo_profile", None) if hasattr(state, "tpo_profile") else None
    if not isinstance(tpo_profile, dict):
        tpo_profile = {}

    def _get_tpo_block(key: str):
        block = tpo_profile.get(key) if tpo_profile else None
        return block if isinstance(block, dict) else None

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
        "tpo_d0": _get_tpo_block("tpo_d0"),
        "tpo_d1": _get_tpo_block("tpo_d1"),
        "tpo_d2": _get_tpo_block("tpo_d2"),
        "tpo_d3": _get_tpo_block("tpo_d3"),
        "tpo_h1": _get_tpo_block("tpo_h1"),
        "tpo_m30": _get_tpo_block("tpo_m30"),
        **candle_color_fields,
        **bb_fields,
        "digits": digits,
    }
