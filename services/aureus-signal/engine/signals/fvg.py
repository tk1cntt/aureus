from .base import BaseSignal
import logging
from engine.logging_common import get_logger
import pandas as pd
from typing import Dict, Any, Optional, cast

logger = get_logger(__name__)
class FVGSignal(BaseSignal):
    """Signal Calculator for Fair Value Gaps."""

    def __init__(self):
        super().__init__("FVG")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or len(df) < 3:
            return None

        c1 = df.iloc[-3]
        c3 = df.iloc[-1]
        result = None

        c3_low = self._as_float(c3.get("l"))
        c3_high = self._as_float(c3.get("h"))
        c1_high = self._as_float(c1.get("h"))
        c1_low = self._as_float(c1.get("l"))
        c3_t = self._as_int(c3.get("t"))

        if any(v is None for v in (c3_low, c3_high, c1_high, c1_low, c3_t)):
            self._check_mitigations(df, state_obj)
            return None

        c3_low_f = cast(float, c3_low)
        c3_high_f = cast(float, c3_high)
        c1_high_f = cast(float, c1_high)
        c1_low_f = cast(float, c1_low)
        c3_t_i = cast(int, c3_t)

        # Bullish FVG
        if c3_low_f > c1_high_f:
            fvg_data = {
                "t": c3_t_i,
                "direction": "BULLISH",
                "top": c3_low_f,
                "bottom": c1_high_f,
                "msg": "New Bullish FVG",
                "category": "imbalance",
                "value": c3_low_f - c1_high_f,
                "explain": "Bullish FVG Formed",
                "inputs": {"top": c3_low_f, "bottom": c1_high_f}
            }
            self._append_fvg(state_obj, fvg_data)
            self._emit_transient(state_obj, "fvg_bull_new", fvg_data)
            result = fvg_data

        # Bearish FVG
        elif c3_high_f < c1_low_f:
            fvg_data = {
                "t": c3_t_i,
                "direction": "BEARISH",
                "top": c1_low_f,
                "bottom": c3_high_f,
                "msg": "New Bearish FVG",
                "category": "imbalance",
                "value": c3_high_f - c1_low_f,
                "explain": "Bearish FVG Formed",
                "inputs": {"top": c1_low_f, "bottom": c3_high_f}
            }
            self._append_fvg(state_obj, fvg_data)
            self._emit_transient(state_obj, "fvg_bear_new", fvg_data)
            result = fvg_data

        # Story 3.5: Check for FVG mitigation events
        self._check_mitigations(df, state_obj)

        return result

    def _append_fvg(self, state_obj: Any, fvg_data: Dict[str, Any]) -> None:
        add_fvg = getattr(state_obj, "add_fvg", None)
        if callable(add_fvg):
            add_fvg(fvg_data)

    def _emit_transient(self, state_obj: Any, key: str, payload: Dict[str, Any]) -> None:
        ts = getattr(state_obj, "transient_signals", None)
        if isinstance(ts, dict):
            ts[key] = payload

    def _check_mitigations(self, df: pd.DataFrame, state_obj: Any):
        """Detect FVG mitigation on the current candle and emit transient signals."""
        if df is None or len(df) == 0 or state_obj is None:
            return

        fvgs = getattr(state_obj, "fvgs", None)
        if not isinstance(fvgs, list) or not fvgs:
            return

        latest = df.iloc[-1]
        c_t = self._as_int(latest.get("t"))
        c_h = self._as_float(latest.get("h"))
        c_l = self._as_float(latest.get("l"))

        if any(v is None for v in (c_t, c_h, c_l)):
            return

        c_t_i = cast(int, c_t)
        c_h_f = cast(float, c_h)
        c_l_f = cast(float, c_l)

        for fvg in fvgs:
            if not isinstance(fvg, dict):
                continue
            if fvg.get("state") == "BROKEN":
                continue
            if fvg.get("_mitigated_emitted"):
                continue

            direction = str(fvg.get("direction") or "").upper()
            top = self._as_float(fvg.get("top"))
            bottom = self._as_float(fvg.get("bottom"))
            if direction not in {"BULLISH", "BEARISH"} or top is None or bottom is None:
                continue

            top_f = cast(float, top)
            bottom_f = cast(float, bottom)

            # Bullish FVG mitigated: price drops into or through the gap
            if direction == "BULLISH" and c_l_f <= top_f:
                fvg["_mitigated_emitted"] = True
                self._emit_transient(
                    state_obj,
                    "fvg_bull_mitigated",
                    {
                        "t": c_t_i,
                        "direction": "BULLISH",
                        "fvg_t": fvg.get("t"),
                        "top": top_f,
                        "bottom": bottom_f,
                        "category": "imbalance",
                        "value": top_f - bottom_f,
                        "explain": "Bullish FVG Mitigated",
                        "inputs": {"fvg_t": fvg.get("t"), "top": top_f, "bottom": bottom_f}
                    },
                )
                symbol = getattr(state_obj, "symbol", "UNKNOWN")
                logger.info(
                    f"[t={c_t_i}] [{symbol}] [_check_mitigations] Bullish FVG ({fvg.get('t')}) MITIGATED at {c_t_i}"
                )

            # Bearish FVG mitigated: price rises into or through the gap
            elif direction == "BEARISH" and c_h_f >= bottom_f:
                fvg["_mitigated_emitted"] = True
                self._emit_transient(
                    state_obj,
                    "fvg_bear_mitigated",
                    {
                        "t": c_t_i,
                        "direction": "BEARISH",
                        "fvg_t": fvg.get("t"),
                        "top": top_f,
                        "bottom": bottom_f,
                        "category": "imbalance",
                        "value": top_f - bottom_f,
                        "explain": "Bearish FVG Mitigated",
                        "inputs": {"fvg_t": fvg.get("t"), "top": top_f, "bottom": bottom_f}
                    },
                )
                symbol = getattr(state_obj, "symbol", "UNKNOWN")
                logger.info(
                    f"[t={c_t_i}] [{symbol}] [_check_mitigations] Bearish FVG ({fvg.get('t')}) MITIGATED at {c_t_i}"
                )

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
