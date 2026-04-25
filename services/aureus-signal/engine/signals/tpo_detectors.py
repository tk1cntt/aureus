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


class VABreakoutAcceptanceDetector:
    def detect(self, context: Dict[str, Any], current_close: float, acceptance_closes: list[float]) -> Dict[str, Any]:
        timeframes = context.get("timeframes") or {}
        invalid_reasons = self._validate_context(context, timeframes)
        if invalid_reasons:
            return self._invalid(invalid_reasons)
        if not acceptance_closes or len(acceptance_closes) > 2:
            return self._invalid(["missing required 1-2 acceptance closes"])

        current = float(current_close)
        acceptance = [float(close) for close in acceptance_closes]
        bias = (context.get("bias") or {}).get("d1", "neutral")

        long_tf = self._find_long_timeframe(timeframes, current, acceptance)
        short_tf = self._find_short_timeframe(timeframes, current, acceptance)

        if long_tf and bias == "bearish":
            return self._invalid([f"long setup conflicts with D1 bearish bias on {long_tf}"])
        if short_tf and bias == "bullish":
            return self._invalid([f"short setup conflicts with D1 bullish bias on {short_tf}"])
        if long_tf and timeframes[long_tf].get("poc_shift") == "down":
            return self._invalid([f"{long_tf} POC shift down conflicts with long breakout acceptance"])
        if short_tf and timeframes[short_tf].get("poc_shift") == "up":
            return self._invalid([f"{short_tf} POC shift up conflicts with short breakout acceptance"])

        if long_tf:
            return self._valid("long", long_tf, timeframes[long_tf], current)
        if short_tf:
            return self._valid("short", short_tf, timeframes[short_tf], current)

        return self._invalid([
            "no H1/M30 VAH breakout or VAL breakdown with acceptance",
            "shape is not sufficient without breakout and acceptance price relation",
        ])

    def _find_long_timeframe(self, timeframes: Dict[str, Dict[str, Any]], current: float, acceptance: list[float]) -> Optional[str]:
        for tf in ("H1", "M30"):
            vah = float(timeframes[tf]["vah"])
            if current > vah and all(close >= vah for close in acceptance):
                return tf
        return None

    def _find_short_timeframe(self, timeframes: Dict[str, Dict[str, Any]], current: float, acceptance: list[float]) -> Optional[str]:
        for tf in ("H1", "M30"):
            val = float(timeframes[tf]["val"])
            if current < val and all(close <= val for close in acceptance):
                return tf
        return None

    def _validate_context(self, context: Dict[str, Any], timeframes: Dict[str, Any]) -> list[str]:
        missing = [tf for tf in ("D1", "H1", "M30") if not timeframes.get(tf)]
        if missing:
            return [f"missing required TPO context: {', '.join(missing)}"]
        malformed = [tf for tf in ("D1", "H1", "M30") if not self._has_levels(timeframes.get(tf))]
        if malformed:
            return [f"malformed TPO levels: {', '.join(malformed)}"]
        history_guard = context.get("history_guard")
        if history_guard:
            stale = history_guard.get("stale_timeframes") or []
            missing_history = history_guard.get("missing_timeframes") or []
            if history_guard.get("is_stale"):
                return [f"history guard stale: {', '.join(stale) or 'unknown'}"]
            if missing_history:
                return [f"history guard missing: {', '.join(missing_history)}"]
        return []

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
        level_key = "vah" if side == "long" else "val"
        level_name = "VAH" if side == "long" else "VAL"
        level = float(value_area[level_key])
        shape = value_area.get("shape")
        score = 0.78
        reasons = [f"{timeframe} breakout accepted {'above VAH' if side == 'long' else 'below VAL'}"]
        if shape in ({"b", "D"} if side == "long" else {"p", "D"}):
            score += 0.07
            reasons.append(f"{timeframe} shape {shape} supports {side} continuation")
        else:
            reasons.append(f"{timeframe} shape {shape} is metadata only; acceptance remains primary")
        return {
            "setup": "va_breakout_acceptance",
            "side": side,
            "valid": True,
            "score": round(score, 2),
            "entry_zone": [level, current] if side == "long" else [current, level],
            "invalidation": level,
            "reasons": reasons,
        }

    def _invalid(self, reasons: list[str]) -> Dict[str, Any]:
        return {
            "setup": "va_breakout_acceptance",
            "side": None,
            "valid": False,
            "score": 0.0,
            "entry_zone": None,
            "invalidation": None,
            "reasons": reasons or ["VA breakout acceptance setup invalid"],
        }


class TrendPullbackDetector:
    def detect(self, context: Dict[str, Any], previous_close: float, current_close: float) -> Dict[str, Any]:
        timeframes = context.get("timeframes") or {}
        invalid_reasons = self._validate_context(context, timeframes)
        if invalid_reasons:
            return self._invalid(invalid_reasons)

        previous = float(previous_close)
        current = float(current_close)
        bias = (context.get("bias") or {}).get("d1", "neutral")
        d1 = timeframes["D1"]

        long_context = bias in {"bullish", "neutral-up"} or current > float(d1["poc"])
        short_context = bias in {"bearish", "neutral-down"} or current < float(d1["poc"])
        long_pullback = self._has_long_pullback(timeframes["H1"], previous, current)
        short_pullback = self._has_short_pullback(timeframes["H1"], previous, current)
        long_confirm = self._has_long_confirmation(timeframes["M30"], previous, current)
        short_confirm = self._has_short_confirmation(timeframes["M30"], previous, current)

        if long_pullback and long_confirm and bias == "bearish":
            return self._invalid(["long pullback conflicts with D1 bearish bias"])
        if short_pullback and short_confirm and bias == "bullish":
            return self._invalid(["short pullback conflicts with D1 bullish bias"])

        if long_context and long_pullback and long_confirm and bias != "bearish":
            return self._valid("long", timeframes["H1"], timeframes["M30"], current)
        if short_context and short_pullback and short_confirm and bias != "bullish":
            return self._valid("short", timeframes["H1"], timeframes["M30"], current)

        reasons = []
        if not long_context and not short_context:
            reasons.append("missing D1 trend or price relation context")
        if not long_pullback and not short_pullback:
            reasons.append("missing H1 pullback to POC/value edge")
        elif long_context and not long_pullback:
            reasons.append("missing H1 pullback to POC/value edge")
        elif short_context and not short_pullback:
            reasons.append("missing H1 pullback to POC/value edge")
        if (long_context or long_pullback) and not long_confirm and not short_confirm:
            reasons.append("missing M30 confirmation")
        if not reasons:
            reasons.append("shape is not sufficient without D1 context, H1 pullback, and M30 confirmation")
        return self._invalid(reasons)

    def _has_long_pullback(self, h1: Dict[str, Any], previous: float, current: float) -> bool:
        poc = float(h1["poc"])
        val = float(h1["val"])
        return (
            previous <= poc <= current
            or previous <= val <= current
            or abs(float(h1.get("distance_to_poc_ticks", 999999.0))) <= 2.0
            or abs(float(h1.get("distance_to_val_ticks", 999999.0))) <= 2.0
        )

    def _has_short_pullback(self, h1: Dict[str, Any], previous: float, current: float) -> bool:
        poc = float(h1["poc"])
        vah = float(h1["vah"])
        return (
            previous >= poc >= current
            or previous >= vah >= current
            or abs(float(h1.get("distance_to_poc_ticks", 999999.0))) <= 2.0
            or abs(float(h1.get("distance_to_vah_ticks", 999999.0))) <= 2.0
        )

    def _has_long_confirmation(self, m30: Dict[str, Any], previous: float, current: float) -> bool:
        val = float(m30["val"])
        poc = float(m30["poc"])
        return previous < val <= current or (previous < poc <= current and current >= val)

    def _has_short_confirmation(self, m30: Dict[str, Any], previous: float, current: float) -> bool:
        vah = float(m30["vah"])
        poc = float(m30["poc"])
        return previous > vah >= current or (previous > poc >= current and current <= vah)

    def _validate_context(self, context: Dict[str, Any], timeframes: Dict[str, Any]) -> list[str]:
        missing = [tf for tf in ("D1", "H1", "M30") if not timeframes.get(tf)]
        if missing:
            return [f"missing required TPO context: {', '.join(missing)}"]
        malformed = [tf for tf in ("D1", "H1", "M30") if not self._has_levels(timeframes.get(tf))]
        if malformed:
            return [f"malformed TPO levels: {', '.join(malformed)}"]
        history_guard = context.get("history_guard")
        if history_guard:
            stale = history_guard.get("stale_timeframes") or []
            missing_history = history_guard.get("missing_timeframes") or []
            if history_guard.get("is_stale"):
                return [f"history guard stale: {', '.join(stale) or 'unknown'}"]
            if missing_history:
                return [f"history guard missing: {', '.join(missing_history)}"]
        return []

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

    def _valid(self, side: str, h1: Dict[str, Any], m30: Dict[str, Any], current: float) -> Dict[str, Any]:
        level_key = "val" if side == "long" else "vah"
        level_name = "VAL" if side == "long" else "VAH"
        level = float(h1[level_key])
        shape = m30.get("shape")
        score = 0.76
        reasons = [
            f"H1 pullback held {level_name}/POC zone",
            f"M30 {'reclaimed VAL' if side == 'long' else 'rejected VAH'}",
        ]
        if shape in ({"b", "D"} if side == "long" else {"p", "D"}):
            score += 0.07
            reasons.append(f"M30 shape {shape} supports {side} pullback continuation")
        else:
            reasons.append(f"M30 shape {shape} is metadata only; pullback legs remain primary")
        return {
            "setup": "trend_pullback",
            "side": side,
            "valid": True,
            "score": round(score, 2),
            "entry_zone": [level, current] if side == "long" else [current, level],
            "invalidation": level,
            "reasons": reasons,
        }

    def _invalid(self, reasons: list[str]) -> Dict[str, Any]:
        return {
            "setup": "trend_pullback",
            "side": None,
            "valid": False,
            "score": 0.0,
            "entry_zone": None,
            "invalidation": None,
            "reasons": reasons or ["trend pullback setup invalid"],
        }
