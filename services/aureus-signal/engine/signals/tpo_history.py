from __future__ import annotations

from typing import Any, Dict, List, Optional


class TPOHistoryStore:
    _TIMEFRAMES = ("D1", "H1", "M30")

    def __init__(self, max_length: int = 20, tick_size: float = 0.1):
        self.max_length = max(int(max_length), 1)
        self.tick_size = max(float(tick_size), 1e-9)
        self._history: Dict[str, List[Dict[str, Any]]] = {tf: [] for tf in self._TIMEFRAMES}

    def append(self, timeframe: str, block: Dict[str, Any]) -> bool:
        tf = self._normalize_timeframe(timeframe)
        if tf is None:
            return False

        snapshot = self._build_snapshot(block)
        if snapshot is None:
            return False

        history = self._history[tf]
        if any(item["t"] == snapshot["t"] for item in history):
            return False

        history.append(snapshot)
        if len(history) > self.max_length:
            del history[: len(history) - self.max_length]
        return True

    def snapshots(self, timeframe: str) -> List[Dict[str, Any]]:
        tf = self._normalize_timeframe(timeframe)
        if tf is None:
            return []
        return list(self._history[tf])

    def poc_shift(self, timeframe: str) -> str:
        latest = self._latest_two(timeframe)
        if latest is None:
            return "unknown"

        previous, current = latest
        delta = current["poc"] - previous["poc"]
        if abs(delta) <= self.tick_size:
            return "flat"
        if delta > 0:
            return "up"
        return "down"

    def va_width_change(self, timeframe: str) -> Optional[float]:
        latest = self._latest_two(timeframe)
        if latest is None:
            return None

        previous, current = latest
        return current["va_width"] - previous["va_width"]

    def freshness_status(
        self,
        now: Optional[float],
        max_age: Optional[float],
        required_timeframes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        required = [self._normalize_timeframe(tf) for tf in (required_timeframes or list(self._TIMEFRAMES))]
        required = [tf for tf in required if tf is not None]
        missing = []
        stale = []

        for tf in required:
            history = self._history[tf]
            if not history:
                missing.append(tf)
                stale.append(tf)
                continue
            if now is not None and max_age is not None and float(now) - float(history[-1]["t"]) > float(max_age):
                stale.append(tf)

        return {
            "is_stale": bool(stale),
            "stale_timeframes": stale,
            "missing_timeframes": missing,
        }

    def _latest_two(self, timeframe: str) -> Optional[List[Dict[str, Any]]]:
        tf = self._normalize_timeframe(timeframe)
        if tf is None or len(self._history[tf]) < 2:
            return None
        return self._history[tf][-2:]

    def _normalize_timeframe(self, timeframe: str) -> Optional[str]:
        tf = str(timeframe).upper()
        if tf not in self._history:
            return None
        return tf

    def _build_snapshot(self, block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(block, dict):
            return None
        try:
            t = block["t"]
            poc = float(block["POC"])
            vah = float(block["VAH"])
            val = float(block["VAL"])
        except (KeyError, TypeError, ValueError):
            return None

        return {
            "t": t,
            "poc": poc,
            "vah": vah,
            "val": val,
            "POC": poc,
            "VAH": vah,
            "VAL": val,
            "shape": block.get("shape"),
            "shape_confidence_pct": block.get("shape_confidence_pct"),
            "va_width": vah - val,
        }
