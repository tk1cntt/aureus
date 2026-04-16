from typing import Any, Dict, Optional

import pandas as pd

from engine.signals.resampler import resample_to_tf


CANDLE_COLOR_TFS = ["D1", "H1", "M30", "M15", "M5"]
BB_TFS = ["M1", "M5", "M15", "M30", "H1"]


def compute_candle_color(candle: Dict[str, Any], digits: int) -> Optional[str]:
    if candle is None:
        return None

    open_price = candle.get("o")
    close_price = candle.get("c")

    if open_price is None or close_price is None:
        return None

    open_norm = round(float(open_price), digits)
    close_norm = round(float(close_price), digits)

    if close_norm > open_norm:
        return "BULLISH"
    if close_norm < open_norm:
        return "BEARISH"
    return "DOJI"


def get_last_closed_candle(m1_df: pd.DataFrame, tf: str) -> Optional[Dict[str, Any]]:
    if m1_df is None or len(m1_df) == 0:
        return None

    tf_upper = tf.upper()
    if tf_upper == "M1":
        row = m1_df.iloc[-1]
        return row.to_dict()

    htf_df = resample_to_tf(m1_df, tf_upper)
    if htf_df is None or len(htf_df) < 2:
        return None

    row = htf_df.iloc[-2]
    return row.to_dict()


def build_mtf_candle_color_map(m1_df: pd.DataFrame, digits: int) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}

    for tf in CANDLE_COLOR_TFS:
        key = f"candle_color_{tf.lower()}"
        candle = get_last_closed_candle(m1_df, tf)
        result[key] = compute_candle_color(candle, digits) if candle is not None else None

    return result


def build_bb_payload(bb_by_tf: Optional[Dict[str, Optional[Dict[str, Any]]]]) -> Dict[str, Optional[Dict[str, Any]]]:
    payload: Dict[str, Optional[Dict[str, Any]]] = {}
    source = bb_by_tf or {}

    for tf in BB_TFS:
        key = f"bb_{tf.lower()}"
        value = source.get(tf)

        if not value:
            payload[key] = None
            continue

        upper = value.get("upper")
        middle = value.get("middle")
        lower = value.get("lower")

        if upper is None or middle is None or lower is None:
            payload[key] = None
            continue

        payload[key] = {"upper": upper, "middle": middle, "lower": lower}

    return payload
