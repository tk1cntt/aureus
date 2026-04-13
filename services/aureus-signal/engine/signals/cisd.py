"""
CISD (Change in State of Delivery) Signal Detector.

Detects when a candle direction flip fails — price breaks back through
the tracking line (open price of the flip candle), confirming reversal
to the original direction.

Based on Pine Script by SB / ote618 (CC BY-NC-SA 4.0).
"""
from .base import BaseSignal, SignalType
from engine.logging_common import get_logger
import pandas as pd
from typing import Dict, Any, Optional, cast

logger = get_logger(__name__)


class CISDSignal(BaseSignal):
    """Detects Change in State of Delivery (CISD) events.

    Logic:
    1. Bear→Bull flip: track open price. If price later drops BELOW it
       → Bearish CISD (bullish flip failed, bearish delivery resumes).
    2. Bull→Bear flip: track open price. If price later rises ABOVE it
       → Bullish CISD (bearish flip failed, bullish delivery resumes).
    """
    signal_type = SignalType.EVENT

    TAG_BULL = "cisd_bull"
    TAG_BEAR = "cisd_bear"

    def __init__(
        self,
        min_length: int = 0,
        max_length: int = 100,
    ):
        super().__init__("CISD")
        self.min_length = max(0, min_length)
        self.max_length = max(1, max_length)

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or len(df) < 2:
            return None

        current = df.iloc[-1]
        c_t = self._as_int(current.get("t"))
        c_c = self._as_float(current.get("c"))
        c_o = self._as_float(current.get("o"))
        c_h = self._as_float(current.get("h"))
        c_l = self._as_float(current.get("l"))

        if any(v is None for v in (c_t, c_c, c_o, c_h, c_l)):
            return None

        c_t = cast(int, c_t)
        c_c = cast(float, c_c)
        c_o = cast(float, c_o)
        c_h = cast(float, c_h)
        c_l = cast(float, c_l)

        # Determine current candle direction
        is_bull = c_c > c_o
        is_bear = c_c < c_o

        symbol = getattr(state_obj, "symbol", "UNKNOWN")

        # Check previous candle direction
        prev = df.iloc[-2]
        prev_c = self._as_float(prev.get("c"))
        prev_o = self._as_float(prev.get("o"))

        if prev_c is None or prev_o is None:
            return None

        prev_is_bull = prev_c > prev_o
        prev_is_bear = prev_c < prev_o

        # Initialize tracking state
        if not hasattr(state_obj, "cisd_tracker"):
            state_obj.cisd_tracker = {}

        tracker = state_obj.cisd_tracker
        result = None

        # --- STEP 1: Check existing tracking for CISD breaks FIRST ---
        # (before flip detection overwrites the tracker)

        # Bullish CISD: bear tracking active, price breaks ABOVE
        if result is None and "bear_start_bar" in tracker and "bear_track_price" in tracker:
            track_price = tracker["bear_track_price"]
            start_bar = tracker["bear_start_bar"]
            span = c_t - start_bar

            if span > self.max_length:
                tracker.pop("bear_start_bar", None)
                tracker.pop("bear_track_price", None)
            elif c_c > track_price:
                if span >= self.min_length:
                    result = {
                        "t": c_t,
                        "direction": "BULLISH",
                        "tag": self.TAG_BULL,
                        "track_price": track_price,
                        "start_bar": start_bar,
                        "span": span,
                        "category": "cisd",
                        "value": round((c_c - c_l) / (c_h - c_l) * 100, 2) if c_h != c_l else None,
                        "explain": f"Bullish CISD (span={span}, min={self.min_length}, max={self.max_length})",
                        "inputs": {
                            "track_price": track_price,
                            "start_bar": start_bar,
                            "min_length": self.min_length,
                            "max_length": self.max_length,
                        }
                    }
                    logger.info(
                        f"[t={c_t}] [{symbol}] [CISD] BULLISH CISD: "
                        f"close={c_c} > track={track_price}, span={span}"
                    )
                    self._emit_transient(state_obj, "cisd_bull", result)
                    tracker.pop("bear_start_bar", None)
                    tracker.pop("bear_track_price", None)
                else:
                    tracker.pop("bear_start_bar", None)
                    tracker.pop("bear_track_price", None)

        # Bearish CISD: bull tracking active, price breaks BELOW
        if result is None and "bull_start_bar" in tracker and "bull_track_price" in tracker:
            track_price = tracker["bull_track_price"]
            start_bar = tracker["bull_start_bar"]
            span = c_t - start_bar

            if span > self.max_length:
                tracker.pop("bull_start_bar", None)
                tracker.pop("bull_track_price", None)
            elif c_c < track_price:
                if span >= self.min_length:
                    result = {
                        "t": c_t,
                        "direction": "BEARISH",
                        "tag": self.TAG_BEAR,
                        "track_price": track_price,
                        "start_bar": start_bar,
                        "span": span,
                        "category": "cisd",
                        "value": round((c_h - c_c) / (c_h - c_l) * 100, 2) if c_h != c_l else None,
                        "explain": f"Bearish CISD (span={span}, min={self.min_length}, max={self.max_length})",
                        "inputs": {
                            "track_price": track_price,
                            "start_bar": start_bar,
                            "min_length": self.min_length,
                            "max_length": self.max_length,
                        }
                    }
                    logger.info(
                        f"[t={c_t}] [{symbol}] [CISD] BEARISH CISD: "
                        f"close={c_c} < track={track_price}, span={span}"
                    )
                    self._emit_transient(state_obj, "cisd_bear", result)
                    tracker.pop("bull_start_bar", None)
                    tracker.pop("bull_track_price", None)
                else:
                    tracker.pop("bull_start_bar", None)
                    tracker.pop("bull_track_price", None)

        # --- STEP 2: Direction flip detection (AFTER break checks) ---
        # Bear→Bull flip: start BULL tracking
        if is_bull and prev_is_bear:
            tracker["bull_start_bar"] = c_t
            tracker["bull_track_price"] = c_o
            # Invalidate old bear tracking
            tracker.pop("bear_start_bar", None)
            tracker.pop("bear_track_price", None)
            logger.debug(
                f"[t={c_t}] [{symbol}] [CISD] Bull flip: tracking @ {c_o}"
            )

        # Bull→Bear flip: start BEAR tracking
        if is_bear and prev_is_bull:
            tracker["bear_start_bar"] = c_t
            tracker["bear_track_price"] = c_o
            # Invalidate old bull tracking
            tracker.pop("bull_start_bar", None)
            tracker.pop("bull_track_price", None)
            logger.debug(
                f"[t={c_t}] [{symbol}] [CISD] Bear flip: tracking @ {c_o}"
            )

        return result

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _emit_transient(self, state_obj: Any, key: str, payload: Dict[str, Any]) -> None:
        ts = getattr(state_obj, "transient_signals", None)
        if isinstance(ts, dict):
            ts[key] = payload
