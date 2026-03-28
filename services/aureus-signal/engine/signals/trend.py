import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = get_logger(__name__)
class TrendSignal(BaseSignal):
    """
    Detects macro trend alignment (HTF Trend).
    Updates state_obj.htf_trend for Hybrid Judges.
    """
    def __init__(self, ema_period: int = 200):
        super().__init__(f"HTF Trend ({ema_period})")
        self.ema_period = ema_period

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < self.ema_period:
            state_obj.htf_trend = "NEUTRAL"
            return None

        # We assume EMA signals are already calculated in df by EMASignal
        # Or we calculate it here if not present
        col_name = f"ema_{self.ema_period}"
        if col_name in df.columns:
            ema_series = df[col_name]
        else:
            ema_series = df['c'].ewm(span=self.ema_period, adjust=False).mean()

        current_ema = float(ema_series.iloc[-1])
        current_price = float(df['c'].iloc[-1])

        # M1-Strict Unmitigated OB Counter Matrix
        obs = getattr(state_obj, 'obs', [])
        green_count = sum(1 for ob in obs if not ob.get('mitigated', False) and ob.get('ob_type') == 'BULLISH')
        red_count = sum(1 for ob in obs if not ob.get('mitigated', False) and ob.get('ob_type') == 'BEARISH')

        # "N=2, M>=2" Order Flow Matrix Contract
        if green_count >= 2 and red_count >= 2:
            regime = "SIDEWAYS"
            htf_trend = "NEUTRAL"
        elif (green_count - red_count) >= 2 and current_price > current_ema:
            regime = "TREND_UP"
            htf_trend = "BULLISH"
        elif (red_count - green_count) >= 2 and current_price < current_ema:
            regime = "TREND_DN"
            htf_trend = "BEARISH"
        else:
            # Divergence (Anti-FOMO) or weak trend -> NEUTRAL stood aside
            regime = "SIDEWAYS"
            htf_trend = "NEUTRAL"

        # Canonical state field
        state_obj.htf_trend = htf_trend

        return {
            "tag": "htf_trend",
            "value": htf_trend,
            "t": int(df.iloc[-1]["t"]),
            "data": {
                "regime": regime,
                "ema_ref": round(current_ema, 5),
                "green_ob_count": green_count,
                "red_ob_count": red_count,
                "delta": green_count - red_count
            }
        }
