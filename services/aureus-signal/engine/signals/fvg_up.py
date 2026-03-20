from .base import BaseSignal
import pandas as pd
from typing import Dict, Any, Optional, cast


class FVGUpSignal(BaseSignal):
    """Bullish Fair Value Gap signal."""

    TAG = "fvg_up"

    def __init__(self):
        super().__init__("Bullish FVG")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or len(df) < 3:
            return None

        c1 = df.iloc[-3]
        c3 = df.iloc[-1]

        c3_low = self._as_float(c3.get("l"))
        c1_high = self._as_float(c1.get("h"))
        t = self._as_int(c3.get("t"))
        if c3_low is None or c1_high is None or t is None:
            return None

        c3_low_f = cast(float, c3_low)
        c1_high_f = cast(float, c1_high)
        t_i = cast(int, t)

        if c3_low_f > c1_high_f:
            fvg_data = {
                "tag": self.TAG,
                "direction": "BULLISH",
                "top": c3_low_f,
                "bottom": c1_high_f,
                "t": t_i,
            }
            add_fvg = getattr(state_obj, "add_fvg", None)
            if callable(add_fvg):
                add_fvg(fvg_data)
            return fvg_data
        return None

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
