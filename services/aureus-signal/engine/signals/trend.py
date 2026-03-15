import logging
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-signal.trend")

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
        prev_ema = float(ema_series.iloc[-2]) if len(ema_series) > 1 else current_ema
        current_price = float(df['c'].iloc[-1])
        slope = (current_ema - prev_ema) / prev_ema if prev_ema > 0 else 0
        
        # Thresholds for SIDEWAYS detection
        is_flat = abs(slope) < 0.00005
        is_close = abs(current_price - current_ema) / current_ema < 0.0003
        
        if is_flat or is_close:
            regime = "SIDEWAYS"
        else:
            regime = "TREND_UP" if current_price > current_ema else "TREND_DN"
            
        # Enrich state object
        state_obj.htf_trend = "BULLISH" if current_price > current_ema else "BEARISH"
        state_obj.market_regime = regime
        
        return {
            "tag": "htf_trend",
            "value": state_obj.htf_trend,
            "regime": regime,
            "ema_ref": round(current_ema, 5),
            "slope": round(slope, 7)
        }
