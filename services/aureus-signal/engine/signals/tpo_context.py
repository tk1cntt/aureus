from __future__ import annotations

from typing import Any, Dict, Optional

from engine.signals.tpo_history import TPOHistoryStore


class TPOContextBuilder:
    _TIMEFRAMES = {
        "D1": "tpo_d1",
        "H1": "tpo_h1",
        "M30": "tpo_m30",
    }

    def __init__(self, tick_size: float = 0.1, near_poc_ticks: float = 2.0):
        self.tick_size = max(float(tick_size), 1e-9)
        self.near_poc_ticks = max(float(near_poc_ticks), 0.0)

    def build(
        self,
        tpo_value: Dict[str, Any],
        close: float,
        history: Optional[TPOHistoryStore] = None,
        now: Optional[float] = None,
        max_age: Optional[float] = None,
    ) -> Dict[str, Any]:
        close_value = float(close)
        timeframes = {
            tf: self._build_timeframe(tpo_value.get(source_key), close_value)
            for tf, source_key in self._TIMEFRAMES.items()
        }

        if history is not None:
            for tf, timeframe in timeframes.items():
                if timeframe is not None:
                    timeframe["poc_shift"] = history.poc_shift(tf)
                    timeframe["va_width_change"] = history.va_width_change(tf)

        context = {
            "timeframes": timeframes,
            "bias": {"d1": self._build_d1_bias(timeframes["D1"], close_value)},
        }
        if history is not None:
            context["history_guard"] = history.freshness_status(now=now, max_age=max_age)
        return context

    def _build_timeframe(self, block: Optional[Dict[str, Any]], close: float) -> Optional[Dict[str, Any]]:
        if block is None:
            return None

        try:
            poc = float(block["POC"])
            vah = float(block["VAH"])
            val = float(block["VAL"])
        except (KeyError, TypeError, ValueError):
            return None

        return {
            "poc": poc,
            "vah": vah,
            "val": val,
            "shape": block.get("shape"),
            "shape_confidence_pct": block.get("shape_confidence_pct"),
            "distr": block.get("distr"),
            "distribution_regime": block.get("distribution_regime", "UNKNOWN"),
            "price_location": self._price_location(close, poc, vah, val),
            "distance_to_poc_ticks": (close - poc) / self.tick_size,
            "distance_to_vah_ticks": (close - vah) / self.tick_size,
            "distance_to_val_ticks": (close - val) / self.tick_size,
            "va_width": vah - val,
        }

    def _price_location(self, close: float, poc: float, vah: float, val: float) -> str:
        if abs(close - poc) <= self.near_poc_ticks * self.tick_size:
            return "near_poc"
        if close > vah:
            return "above_vah"
        if close < val:
            return "below_val"
        return "inside_value_area"

    def _build_d1_bias(self, d1: Optional[Dict[str, Any]], close: float) -> str:
        if d1 is None:
            return "neutral"
        if close > d1["vah"] or close > d1["poc"]:
            return "bullish"
        if close < d1["val"] or close < d1["poc"]:
            return "bearish"
        return "neutral"
