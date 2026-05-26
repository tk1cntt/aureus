from __future__ import annotations

import math
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

EPSILON = 1e-9
SHAPES = ("D", "p", "b")
SCORE_KEYS = ("D", "B", "p", "b")

import pandas as pd

from .base import BaseSignal, SignalType
from .resampler import resample_to_tf


class TPOSignal(BaseSignal):
    signal_type = SignalType.INDICATOR

    _TFS = ("D1", "H1", "M30")
    _SYMBOL_TICK_SIZE_FLOORS = {
        "BTC": 1.0,
        "ETH": 0.1,
        "USTEC": 1.0,
        "XAU": 0.1,
        "JPY": 0.001,
    }

    def __init__(self, value_area_pct: float = 0.7, tick_size: float = 0.1, symbol: Optional[str] = None):
        super().__init__("TPO")
        self.value_area_pct = max(0.01, min(float(value_area_pct), 1.0))
        self.tick_size = max(float(tick_size), 1e-9)
        self.symbol = str(symbol or "").upper()
        self.max_levels = max(100, int(os.getenv("AUREUS_TPO_MAX_LEVELS", "5000")))

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

        symbol = str(kwargs.get("symbol") or self.symbol or "").upper()
        tpo_daily_cache = getattr(state_obj, "tpo_daily_cache", {})
        if not isinstance(tpo_daily_cache, dict):
            tpo_daily_cache = {}
        current_day = datetime.fromtimestamp(ts, tz=timezone.utc).date()

        payload = {
            "tpo_d0": self._compute_daily(df, ts, days_ago=0, symbol=symbol),
            "tpo_d1": tpo_daily_cache.get((current_day - timedelta(days=1)).strftime("%Y%m%d")) or self._compute_daily(df, ts, days_ago=1, symbol=symbol),
            "tpo_d2": tpo_daily_cache.get((current_day - timedelta(days=2)).strftime("%Y%m%d")) or self._compute_daily(df, ts, days_ago=2, symbol=symbol),
            "tpo_d3": tpo_daily_cache.get((current_day - timedelta(days=3)).strftime("%Y%m%d")) or self._compute_daily(df, ts, days_ago=3, symbol=symbol),
            "tpo_h1": self._compute_sliding(df, ts, tf="H1", count=6, cache=state_obj.tpo_cache, symbol=symbol),
            "tpo_m30": self._compute_sliding(df, ts, tf="M30", count=6, cache=state_obj.tpo_cache, symbol=symbol),
        }

        state_obj.tpo_profile = payload

        return {
            "tag": "tpo",
            "value": payload,
            "t": ts,
        }

    def _compute_daily(self, m1_df: pd.DataFrame, now_ts: int, days_ago: int, symbol: str = "") -> Optional[Dict[str, Any]]:
        current_day_start = now_ts - (now_ts % 86400)
        day_start = current_day_start - (int(days_ago) * 86400)
        day_end = now_ts if days_ago == 0 else day_start + 86400 - 60
        session = m1_df[(m1_df["t"] >= day_start) & (m1_df["t"] <= day_end)]
        if session is None or len(session) == 0:
            return None

        return self._build_tpo_block(session, symbol=symbol)

    def _compute_sliding(self, m1_df: pd.DataFrame, now_ts: int, tf: str, count: int, cache: Dict[str, Dict[str, Any]], symbol: str = "") -> Optional[Dict[str, Any]]:
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

            cached_block = cache.get(bucket_key) if not is_current_bucket else None
            if cached_block is not None:
                latest_block = cached_block
                continue

            session = m1_df[(m1_df["t"] >= bucket_start) & (m1_df["t"] <= min(bucket_end, now_ts))]
            if session is None or len(session) == 0:
                continue

            block = self._build_tpo_block(session, symbol=symbol)
            if block is None:
                continue

            if not is_current_bucket:
                cache[bucket_key] = block
            latest_block = block

        return latest_block

    def _build_tpo_block(self, session_df: pd.DataFrame, symbol: str = "") -> Optional[Dict[str, Any]]:
        built = self._build_levels_and_counts(session_df, symbol=symbol)
        if built is None:
            return None

        levels, counts = built
        profile = self._build_profile_from_counts(levels, counts)
        if profile is None:
            return None

        poc, vah, val, poc_idx = profile
        shape, confidence_pct, scores = self._classify_shape(levels, counts, poc_idx)
        distr = self._calculate_distr(counts)

        return {
            "POC": poc,
            "VAH": vah,
            "VAL": val,
            "OPEN": float(session_df.iloc[0]["o"]) if "o" in session_df.columns else None,
            "HIGH": float(pd.to_numeric(session_df["h"], errors="coerce").max()) if "h" in session_df.columns else None,
            "LOW": float(pd.to_numeric(session_df["l"], errors="coerce").min()) if "l" in session_df.columns else None,
            "CLOSE": float(session_df.iloc[-1]["c"]) if "c" in session_df.columns else None,
            "shape": shape,
            "shape_confidence_pct": confidence_pct,
            "shape_scores_pct": scores,
            "distr": distr,
            "distribution_regime": self._classify_distribution_regime(distr),
        }

    def _calculate_distr(self, counts: List[int]) -> float:
        if not counts:
            return 0.0
        safe_counts = [max(0, int(c)) for c in counts]
        max_count = max(safe_counts) if safe_counts else 0
        if max_count <= 0:
            return 0.0
        return round(float(sum(safe_counts)) / float(max_count), 8)

    def _classify_distribution_regime(self, distr: float) -> str:
        return "UNKNOWN"

    def _classify_shape(self, levels: List[float], counts: List[int], poc_idx: int) -> Tuple[Optional[str], float, Dict[str, float]]:
        n = len(counts)
        if n == 0:
            return None, 0.0, {shape: 0.0 for shape in SCORE_KEYS}

        total = float(sum(max(0, c) for c in counts))
        if total <= EPSILON:
            return None, 0.0, {shape: 0.0 for shape in SCORE_KEYS}

        poc_idx = max(0, min(int(poc_idx), n - 1))
        max_count = float(max(counts))
        usable_bins = sum(1 for c in counts if c > 0)
        if usable_bins < 2 or total < 4.0:
            return None, 0.0, {"D": 33.33, "B": 0.0, "p": 33.33, "b": 33.34}
        coverage = usable_bins / float(n)
        maturity = min(1.0, total / 20.0)
        usable_quality = min(1.0, usable_bins / 5.0)
        data_quality = max(0.15, min(1.0, coverage * 1.4, maturity, usable_quality))

        poc_pos = (poc_idx / float(n - 1)) if n > 1 else 0.5
        middle_proximity = max(0.0, 1.0 - (abs(poc_pos - 0.5) / 0.5))
        upper_third = 1.0 if poc_pos >= (2.0 / 3.0) else 0.0
        lower_third = 1.0 if poc_pos <= (1.0 / 3.0) else 0.0

        target = max(1, int(round(total * self.value_area_pct)))
        covered = max(0, counts[poc_idx])
        val_idx = poc_idx
        vah_idx = poc_idx
        while covered < target and (val_idx > 0 or vah_idx < n - 1):
            up_count = counts[vah_idx + 1] if vah_idx < n - 1 else -1
            down_count = counts[val_idx - 1] if val_idx > 0 else -1
            if up_count > down_count:
                vah_idx += 1
                covered += max(0, counts[vah_idx])
            elif down_count > up_count:
                val_idx -= 1
                covered += max(0, counts[val_idx])
            elif up_count >= 0:
                vah_idx += 1
                covered += max(0, counts[vah_idx])
                if covered < target and val_idx > 0:
                    val_idx -= 1
                    covered += max(0, counts[val_idx])
            elif val_idx > 0:
                val_idx -= 1
                covered += max(0, counts[val_idx])
            else:
                break

        range_den = float(max(1, n - 1))
        lower_va = (poc_idx - val_idx) / range_den
        upper_va = (vah_idx - poc_idx) / range_den
        va_balance = 1.0 - (abs(upper_va - lower_va) / (upper_va + lower_va + EPSILON)) if (upper_va + lower_va) > EPSILON else 1.0

        peaks = []
        min_prominence = max(2.0, max_count * 0.45)
        for i, c in enumerate(counts):
            left = counts[i - 1] if i > 0 else -1
            right = counts[i + 1] if i < n - 1 else -1
            if c >= min_prominence and c >= left and c >= right:
                peaks.append((i, float(c)))

        peak_pair_candidates = peaks
        if len(peak_pair_candidates) > 64:
            peak_pair_candidates = sorted(peak_pair_candidates, key=lambda item: item[1], reverse=True)[:64]
            peak_pair_candidates.sort(key=lambda item: item[0])

        b_evidence = 0.0
        for first_idx, first_count in peak_pair_candidates:
            for second_idx, second_count in peak_pair_candidates:
                if second_idx <= first_idx:
                    continue
                separation = second_idx - first_idx
                if separation < max(2, int(math.ceil(n / 3.0))):
                    continue
                valley = min(float(c) for c in counts[first_idx + 1:second_idx]) if second_idx > first_idx + 1 else max_count
                weaker_peak = min(first_count, second_count)
                peak_balance = weaker_peak / (max(first_count, second_count) + EPSILON)
                if peak_balance < 0.75:
                    continue
                valley_depth = max(0.0, 1.0 - (valley / (weaker_peak + EPSILON)))
                if valley_depth < 0.35:
                    continue
                separation_score = min(1.0, separation / max(3.0, n / 2.0))
                b_evidence = max(b_evidence, peak_balance * valley_depth * separation_score)

        d_score = max(0.0, (0.65 * middle_proximity) + (0.35 * va_balance) - (1.15 * b_evidence))
        p_score = max(0.0, upper_third * 1.25 * (1.0 - min(0.85, b_evidence)))
        b_lower_score = max(0.0, lower_third * 1.25 * (1.0 - min(0.85, b_evidence)))
        if 0.3 <= poc_pos <= 0.7 and d_score > 0.0:
            p_score = 0.0
            b_lower_score = 0.0

        scores = {"D": d_score, "p": p_score, "b": b_lower_score}
        score_sum = sum(scores.values())
        if score_sum <= EPSILON:
            normalized = {"D": 33.33, "B": 0.0, "p": 33.33, "b": 33.34}
            return None, 0.0, normalized

        normalized = {shape: round((scores[shape] / score_sum) * 100.0, 2) for shape in SHAPES}
        normalized["B"] = 0.0
        best_shape = max(SHAPES, key=lambda shape: normalized[shape])
        top_score = normalized[best_shape]
        if top_score <= 70.0:
            return None, 0.0, normalized

        return best_shape, top_score, normalized

    def _symbol_tick_floor(self, symbol: str) -> float:
        symbol_upper = str(symbol or self.symbol or "").upper()
        for prefix, tick_floor in self._SYMBOL_TICK_SIZE_FLOORS.items():
            if prefix in symbol_upper:
                return max(float(tick_floor), self.tick_size)
        return self.tick_size

    def _effective_tick_size(self, high_max: float, low_min: float, symbol: str = "") -> float:
        price_range = max(0.0, high_max - low_min)
        tick_floor = self._symbol_tick_floor(symbol)
        if price_range <= EPSILON:
            return tick_floor
        target_levels = max(1, self.max_levels - 1)
        range_tick = price_range / float(target_levels)
        return max(tick_floor, range_tick, self.tick_size)

    def _build_levels_and_counts(self, session_df: pd.DataFrame, symbol: str = "") -> Optional[Tuple[List[float], List[int]]]:
        high_max = float(session_df["h"].max())
        low_min = float(session_df["l"].min())

        if not math.isfinite(high_max) or not math.isfinite(low_min):
            return None
        if high_max < low_min:
            return None

        effective_tick_size = self._effective_tick_size(high_max, low_min, symbol=symbol)
        levels_count = int(math.floor((high_max - low_min) / effective_tick_size)) + 1
        levels_count = max(1, min(levels_count, self.max_levels))

        levels = [low_min + (i * effective_tick_size) for i in range(levels_count)]
        deltas = [0 for _ in range(levels_count + 1)]

        for _, row in session_df.iterrows():
            h = float(row["h"])
            l = float(row["l"])
            if h < l:
                continue
            start_idx = max(0, int(math.floor((l - low_min) / effective_tick_size)))
            end_idx = min(levels_count - 1, int(math.floor((h - low_min) / effective_tick_size)))
            deltas[start_idx] += 1
            deltas[end_idx + 1] -= 1

        counts = []
        running = 0
        for idx in range(levels_count):
            running += deltas[idx]
            counts.append(running)

        return levels, counts

    def _build_profile(self, session_df: pd.DataFrame) -> Optional[Tuple[float, float, float]]:
        built = self._build_levels_and_counts(session_df)
        if built is None:
            return None

        profile = self._build_profile_from_counts(*built)
        if profile is None:
            return None

        poc, vah, val, _ = profile
        return poc, vah, val

    def _build_profile_from_counts(self, levels: List[float], counts: List[int]) -> Optional[Tuple[float, float, float, int]]:
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
        return poc, vah, val, poc_idx

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
