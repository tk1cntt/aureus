from __future__ import annotations

from typing import Any, Dict, Optional


class VARejectionDetector:
    def detect(self, context: Dict[str, Any], previous_close: float, current_close: float) -> Dict[str, Any]:
        reasons = []
        timeframes = context.get("timeframes") or {}
        missing = [tf for tf in ("D1", "H1", "M30") if not timeframes.get(tf)]
        if missing:
            return self._invalid([f"missing required TPO context: {', '.join(missing)}"])

        malformed = [tf for tf in ("D1", "H1", "M30") if not self._has_levels(timeframes.get(tf))]
        if malformed:
            return self._invalid([f"malformed TPO levels: {', '.join(malformed)}"])

        history_guard = context.get("history_guard")
        if history_guard:
            stale = history_guard.get("stale_timeframes") or []
            missing_history = history_guard.get("missing_timeframes") or []
            if history_guard.get("is_stale"):
                return self._invalid([f"history guard stale: {', '.join(stale) or 'unknown'}"])
            if missing_history:
                return self._invalid([f"history guard missing: {', '.join(missing_history)}"])

        previous = float(previous_close)
        current = float(current_close)
        bias = (context.get("bias") or {}).get("d1", "neutral")

        long_tf = self._find_long_timeframe(timeframes, previous, current)
        short_tf = self._find_short_timeframe(timeframes, previous, current)

        if long_tf and bias == "bearish":
            return self._invalid([f"long setup conflicts with D1 bearish bias on {long_tf}"])
        if short_tf and bias == "bullish":
            return self._invalid([f"short setup conflicts with D1 bullish bias on {short_tf}"])

        if long_tf:
            return self._valid("long", long_tf, timeframes[long_tf], current)
        if short_tf:
            return self._valid("short", short_tf, timeframes[short_tf], current)

        reasons.append("no H1/M30 VAL reclaim or VAH reject price relation")
        reasons.append("shape is not sufficient without price rejection relation")
        return self._invalid(reasons)

    def _find_long_timeframe(self, timeframes: Dict[str, Dict[str, Any]], previous: float, current: float) -> Optional[str]:
        for tf in ("H1", "M30"):
            value_area = timeframes[tf]
            val = float(value_area["val"])
            if previous < val <= current and self._current_is_below_or_near_poc(value_area, current):
                return tf
        return None

    def _find_short_timeframe(self, timeframes: Dict[str, Dict[str, Any]], previous: float, current: float) -> Optional[str]:
        for tf in ("H1", "M30"):
            value_area = timeframes[tf]
            vah = float(value_area["vah"])
            if previous > vah >= current and self._current_is_above_or_near_poc(value_area, current):
                return tf
        return None

    def _current_is_below_or_near_poc(self, value_area: Dict[str, Any], current: float) -> bool:
        return current <= float(value_area["poc"]) or self._is_near_poc(value_area)

    def _current_is_above_or_near_poc(self, value_area: Dict[str, Any], current: float) -> bool:
        return current >= float(value_area["poc"]) or self._is_near_poc(value_area)

    def _is_near_poc(self, value_area: Dict[str, Any]) -> bool:
        return value_area.get("price_location") == "near_poc" or abs(float(value_area.get("distance_to_poc_ticks", 999999.0))) <= 2.0

    def _has_levels(self, value_area: Any) -> bool:
        if not isinstance(value_area, dict):
            return False
        try:
            float(value_area["poc"])
            float(value_area["vah"])
            float(value_area["val"])
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def _valid(self, side: str, timeframe: str, value_area: Dict[str, Any], current: float) -> Dict[str, Any]:
        shape = value_area.get("shape")
        level_key = "val" if side == "long" else "vah"
        level_name = "VAL" if side == "long" else "VAH"
        level = float(value_area[level_key])
        score = 0.75
        reasons = [f"{timeframe} close {'reclaimed' if side == 'long' else 'rejected'} {level_name}"]

        if shape in ({"b", "D"} if side == "long" else {"p", "D"}):
            score += 0.1
            reasons.append(f"{timeframe} shape {shape} supports {side} VA rejection")
        else:
            reasons.append(f"{timeframe} shape {shape} is neutral; price relation remains primary")

        return {
            "setup": "va_rejection",
            "side": side,
            "valid": True,
            "score": round(score, 2),
            "entry_zone": [level, current] if side == "long" else [current, level],
            "invalidation": level,
            "reasons": reasons,
        }

    def _invalid(self, reasons: list[str]) -> Dict[str, Any]:
        return {
            "setup": "va_rejection",
            "side": None,
            "valid": False,
            "score": 0.0,
            "entry_zone": None,
            "invalidation": None,
            "reasons": reasons or ["VA rejection setup invalid"],
        }
