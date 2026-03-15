import logging
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-signal.atr")

class ATRSignal(BaseSignal):
    """
    Calculates Average True Range (ATR).
    Updates state_obj.atr for quantitative normalization in Judges.
    """
    def __init__(self, period: int = 14):
        super().__init__(f"ATR ({period})")
        self.period = period

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < self.period + 1:
            return None
            
        # 1. Calculate current True Range (TR)
        curr_candle = df.iloc[-1]
        high = float(curr_candle['h'])
        low = float(curr_candle['l'])
        t = int(curr_candle['t'])
        
        # Get previous close for TR calculation
        # Preference: Use df.iloc[-2]['c'] if available, else state_obj.last_candle or high/low
        prev_close = None
        if len(df) > 1:
            prev_close = float(df.iloc[-2]['c'])
        elif hasattr(state_obj, 'last_candle') and state_obj.last_candle:
            prev_close = float(state_obj.last_candle['c'])
        else:
            prev_close = high # Fallback for very first candle

        tr_now = max(high - low, abs(high - prev_close), abs(low - prev_close))
        
        # 2. Optimized O(1) ATR (Wilder's RMA)
        # Formula: ATR = (ATR_prev * (n-1) + TR) / n
        if hasattr(state_obj, 'atr') and state_obj.atr is not None:
            # INCREMENTAL O(1) LOGIC
            curr_atr = (state_obj.atr * (self.period - 1) + tr_now) / self.period
        else:
            # WARMUP / BATCH LOGIC
            if len(df) < self.period:
                return None
                
            # Full batch calculation for initiation
            h_series = df['h']
            l_series = df['l']
            pc_series = df['c'].shift(1)
            tr_series = pd.concat([h_series - l_series, 
                                  abs(h_series - pc_series), 
                                  abs(l_series - pc_series)], axis=1).max(axis=1)
            
            atr_batch = tr_series.ewm(alpha=1/self.period, adjust=False).mean()
            curr_atr = float(atr_batch.iloc[-1])
        
        # 3. Enrich state object
        state_obj.atr = curr_atr
        
        return {
            "tag": f"atr_{self.period}",
            "value": round(curr_atr, 6),
            "t": int(df.iloc[-1]['t'])
        }
