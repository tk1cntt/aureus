from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

EPSILON = 1e-9
SHAPES = ("D", "B", "p", "b")

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

        current = df.iloc[-1]
        ts = int(float(current.get("t")))

        if not hasattr(state_obj, "tpo_profile"):
            state_obj.tpo_profile = {}
        if not hasattr(state_obj, "tpo_cache") or not isinstance(getattr(state_obj, "tpo_cache"), dict):
            state_obj.tpo_cache = {}

        payload = {
            "tpo_d1": self._compute_d1(df, ts),
            "tpo_h1": self._compute_sliding(df, ts, tf="H1", count=6, cache=state_obj.tpo_cache),
            "tpo_m30": self._compute_sliding(df, ts, tf="M30", count=6, cache=state_obj.tpo_cache),
        }

        state_obj.tpo_profile = payload

        return {
            "tag": "tpo",
            "value": payload,
            "t": ts,
        }

    def _compute_d1(self, m1_df: pd.DataFrame, now_ts: int) -> Optional[Dict[str, Any]]:
        day_start = now_ts - (now_ts % 86400)
        session = m1_df[(m1_df["t"] >= day_start) & (m1_df["t"] <= now_ts)]
        if session is None or len(session) == 0:
            return None

        return self._build_tpo_block(session)

    def _compute_sliding(self, m1_df: pd.DataFrame, now_ts: int, tf: str, count: int, cache: Dict[str, Tuple[float, float, float]]) -> Optional[Dict[str, Any]]:
        tf_df = resample_to_tf(m1_df, tf)
        if tf_df is None or len(tf_df) == 0:
            return None

        bucket_seconds = 3600 if tf.upper() == "H1" else 1800
        tf_df = tf_df.copy()
        tf_df["bucket_start"] = tf_df["t"].astype(int) - bucket_seconds + 60

        recent = tf_df.tail(count)
        if recent is None or len(recent) == 0:
            return None

        latest_block = None
        for _, row in recent.iterrows():
            bucket_start = int(row["bucket_start"])
            bucket_end = int(row["t"])
            bucket_key = f"{tf.upper()}:{bucket_start}"
            is_current_bucket = bucket_start <= now_ts <= bucket_end

            session = m1_df[(m1_df["t"] >= bucket_start) & (m1_df["t"] <= min(bucket_end, now_ts))]
            if session is None or len(session) == 0:
                continue

            profile = cache.get(bucket_key) if (not is_current_bucket and bucket_key in cache) else None
            if profile is None:
                profile = self._build_profile(session)
                if profile and not is_current_bucket:
                    cache[bucket_key] = profile

            if profile:
                latest_block = self._build_tpo_block(session)

        return latest_block

    def _build_tpo_block(self, session_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        profile = self._build_profile(session_df)
        if profile is None:
            return None

        poc, vah, val = profile
        built = self._build_levels_and_counts(session_df)
        if built is None:
            return {"POC": poc, "VAH": vah, "VAL": val}

        levels, counts = built
        if not levels or not counts:
            return {"POC": poc, "VAH": vah, "VAL": val}

        poc_idx = min(range(len(levels)), key=lambda i: abs(levels[i] - poc))
        shape, confidence_pct, scores = self._classify_shape(levels, counts, poc_idx)

        return {
            "POC": poc,
            "VAH": vah,
            "VAL": val,
            "shape": shape,
            "shape_confidence_pct": confidence_pct,
            "shape_scores_pct": scores,
        }

    def _classify_shape(self, levels: List[float], counts: List[int], poc_idx: int) -> Tuple[str, float, Dict[str, float]]:
        n = len(counts)
        if n == 0:
            return "D", 0.0, {shape: 0.0 for shape in SHAPES}

        total = float(sum(counts))
        if total <= EPSILON:
            return "D", 0.0, {shape: 0.0 for shape in SHAPES}

        upper_mass = float(sum(counts[poc_idx + 1:]))
        lower_mass = float(sum(counts[:poc_idx]))
        skew = (upper_mass - lower_mass) / (total + EPSILON)

        max_count = max(counts)
        prominences = []
        for i, c in enumerate(counts):
            left = counts[i - 1] if i > 0 else -1
            right = counts[i + 1] if i < n - 1 else -1
            if c >= left and c >= right:
                prominences.append(c)
        prominences.sort(reverse=True)
        p1 = float(prominences[0]) if prominences else 0.0
        p2 = float(prominences[1]) if len(prominences) > 1 else 0.0
        dual_peak_ratio = p2 / (p1 + EPSILON)

        upper_tail = counts[max(0, n - max(1, n // 5)):]
        lower_tail = counts[:max(1, n // 5)]
        upper_tail_mean = (sum(upper_tail) / len(upper_tail)) if upper_tail else 0.0
        lower_tail_mean = (sum(lower_tail) / len(lower_tail)) if lower_tail else 0.0

        scores = {
            "D": max(0.0, 1.0 - abs(skew) - max(0.0, dual_peak_ratio - 0.45)),
            "B": max(0.0, min(1.0, dual_peak_ratio - 0.35) + max(0.0, 0.25 - abs(skew))),
            "p": max(0.0, skew + max(0.0, (lower_tail_mean - upper_tail_mean) / (max_count + EPSILON))),
            "b": max(0.0, -skew + max(0.0, (upper_tail_mean - lower_tail_mean) / (max_count + EPSILON))),
        }

        score_sum = sum(scores.values())
        if score_sum <= EPSILON:
            normalized = {shape: 25.0 for shape in SHAPES}
            return "D", 25.0, normalized

        normalized = {
            shape: round((scores[shape] / score_sum) * 100.0, 2)
            for shape in SHAPES
        }
        best_shape = max(SHAPES, key=lambda shape: normalized[shape])
        best_confidence = normalized[best_shape]
        return best_shape, best_confidence, normalized

    def _build_levels_and_counts(self, session_df: pd.DataFrame) -> Optional[Tuple[List[float], List[int]]]:
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

        return levels, counts

    def _build_profile(self, session_df: pd.DataFrame) -> Optional[Tuple[float, float, float]]:
        built = self._build_levels_and_counts(session_df)
        if built is None:
            return None

        levels, counts = built
        levels_count = len(levels)
        if levels_count == 0:
            return None

        high_max = levels[-1]
        low_min = levels[0]

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
