"""
OHLCV Resampler — converts M1 candle DataFrames into higher timeframe candles.

Uses pandas resample with origin="epoch" so HTF boundaries align to clean
UTC multiples (e.g., M5 to :00/:05/:10 regardless of stream start time).
"""
import pandas as pd
from typing import Optional

# Supported timeframes in minutes
TF_MINUTES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}


def resample_to_tf(df: pd.DataFrame, tf: str) -> Optional[pd.DataFrame]:
    """Resample a M1 OHLCV DataFrame to a higher timeframe.

    Args:
        df: DataFrame with columns [t, o, h, l, c, v] (or subset)
        tf: Target timeframe string ("M5", "M15", "M30", "H1", ...)

    Returns:
        Resampled DataFrame with same column names, or None if invalid.
        The last row is the forming (incomplete) HTF candle.
    """
    if df is None or len(df) == 0:
        return None

    minutes = TF_MINUTES.get(tf.upper())
    if minutes is None or minutes <= 1:
        return None

    # Ensure 't' column exists
    if "t" not in df.columns:
        return None

    try:
        ts_index = pd.to_datetime(df["t"], unit="s", utc=True)
    except (ValueError, TypeError):
        return None

    resampled = df.set_index(ts_index).resample(
        f"{minutes}min", label="left", closed="left", origin="epoch"
    )

    agg_map = {"o": "first", "h": "max", "l": "min", "c": "last", "t": "last"}
    result = resampled.agg(agg_map).dropna(subset=["o"])

    # Restore original column order
    cols = [c for c in ["t", "o", "h", "l", "c"] if c in result.columns]
    if "v" in df.columns and "v" in result.columns:
        cols.append("v")
    result = result[cols]

    if len(result) == 0:
        return None

    # Convert t back to int timestamps
    result["t"] = result["t"].astype(int).astype("Int64")

    return result.reset_index(drop=True)