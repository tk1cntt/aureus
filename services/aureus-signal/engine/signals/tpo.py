from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from .base import BaseSignal, SignalType
from .resampler import resample_to_tf


class TPOSignal(BaseSignal):
    signal_type = SignalType.INDICATOR

    _TFS = ("D1", "H1", "M30")

    def __init__(self, value_area_pct: float = 0.7, tick_size: float = 0.1):
        super().__init__("TPO")
        self.value_area_pct = max(0.01, min(float(value_area_pct), 1.0))
        self.tick_size = max(float(tick_size), 1e-9)

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or len(df) < 2:
            return None
        if not {"t", "h", "l", "c"}.issubset(df.columns):
            return None

        payload = {
            "tpo_d1": self._compute_tf(df, "D1"),
            "tpo_h1": self._compute_tf(df, "H1"),
            "tpo_m30": self._compute_tf(df, "M30"),
        }

        current = df.iloc[-1]
        ts = int(float(current.get("t")))

        if hasattr(state_obj, "tpo_profile"):
            state_obj.tpo_profile = payload

        return {
            "tag": "tpo",
            "value": payload,
            "t": ts,
        }

    def _compute_tf(self, m1_df: pd.DataFrame, tf: str) -> Optional[Dict[str, Optional[float]]]:
        tf_df = resample_to_tf(m1_df, tf)
        if tf_df is None or len(tf_df) < 2:
            return None

        closed = tf_df.iloc[-2]
        start_ts = self._start_ts(tf, int(float(closed["t"])))
        end_ts = int(float(closed["t"]))

        session = m1_df[(m1_df["t"] >= start_ts) & (m1_df["t"] <= end_ts)]
        if session is None or len(session) == 0:
            return None

        profile = self._build_profile(session)
        if profile is None:
            return None

        poc, vah, val = profile
        return {
            "POC": poc,
            "VAH": vah,
            "VAL": val,
        }

    def _build_profile(self, session_df: pd.DataFrame) -> Optional[Tuple[float, float, float]]:
        high_max = float(session_df["h"].max())
        low_min = float(session_df["l"].min())

        if not math.isfinite(high_max) or not math.isfinite(low_min):
            return None
        if high_max < low_min:
            return None

        levels_count = int(math.floor((high_max - low_min) / self.tick_size)) + 1
        levels_count = max(levels_count, 1)
        levels = [low_min + (i * self.tick_size) for i in range(levels_count)]
        counts = [0 for _ in levels]

        for _, row in session_df.iterrows():
            h = float(row["h"])
            l = float(row["l"])
            if h < l:
                continue
            start_idx = max(0, int(math.floor((l - low_min) / self.tick_size)))
            end_idx = min(levels_count - 1, int(math.floor((h - low_min) / self.tick_size)))
            for idx in range(start_idx, end_idx + 1):
                counts[idx] += 1

        total = sum(counts)
        if total <= 0:
            return None

        midpoint_price = (high_max + low_min) / 2.0
        max_count = max(counts)
        poc_candidates = [i for i, c in enumerate(counts) if c == max_count]
        poc_idx = min(poc_candidates, key=lambda i: (abs(levels[i] - midpoint_price), i))

        target = max(1, int(round(total * self.value_area_pct)))
        covered = counts[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx

        while covered < target and (low_idx > 0 or high_idx < levels_count - 1):
            up_count = counts[high_idx + 1] if high_idx < levels_count - 1 else -1
            down_count = counts[low_idx - 1] if low_idx > 0 else -1

            if up_count > down_count:
                high_idx += 1
                covered += counts[high_idx]
            elif down_count > up_count:
                low_idx -= 1
                covered += counts[low_idx]
            else:
                if up_count < 0 and down_count < 0:
                    break
                up_dist = abs(levels[high_idx + 1] - midpoint_price) if high_idx < levels_count - 1 else float("inf")
                down_dist = abs(levels[low_idx - 1] - midpoint_price) if low_idx > 0 else float("inf")
                if up_dist < down_dist and high_idx < levels_count - 1:
                    high_idx += 1
                    covered += counts[high_idx]
                elif low_idx > 0:
                    low_idx -= 1
                    covered += counts[low_idx]
                elif high_idx < levels_count - 1:
                    high_idx += 1
                    covered += counts[high_idx]
                else:
                    break

        poc = round(levels[poc_idx], 8)
        vah = round(levels[high_idx], 8)
        val = round(levels[low_idx], 8)
        return poc, vah, val

    @staticmethod
    def _start_ts(tf: str, end_ts: int) -> int:
        tf_upper = tf.upper()
        if tf_upper == "M30":
            return end_ts - (30 * 60) + 60
        if tf_upper == "H1":
            return end_ts - (60 * 60) + 60
        if tf_upper == "D1":
            return end_ts - (24 * 60 * 60) + 60
        return end_ts
