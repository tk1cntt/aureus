import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal, SignalType
from typing import Dict, Any, Optional

logger = get_logger(__name__)
class ATRSignal(BaseSignal):
    """
    Calculates Average True Range (ATR).
    Updates state_obj.atr for quantitative normalization in Judges.
    """
    signal_type = SignalType.INDICATOR

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

        # With warmup gate above, previous candle always exists.
        prev_close = float(df.iloc[-2]['c'])
        tr_now = max(high - low, abs(high - prev_close), abs(low - prev_close))

        # 2. Optimized O(1) ATR (Wilder's RMA)
        # Formula: ATR = (ATR_prev * (n-1) + TR) / n
        if hasattr(state_obj, 'atr') and state_obj.atr is not None:
            curr_atr = (state_obj.atr * (self.period - 1) + tr_now) / self.period
        else:
            h_series = df['h']
            l_series = df['l']
            pc_series = df['c'].shift(1)
            tr_series = pd.concat(
                [h_series - l_series, abs(h_series - pc_series), abs(l_series - pc_series)],
                axis=1,
            ).max(axis=1)

            atr_batch = tr_series.ewm(alpha=1 / self.period, adjust=False).mean()
            curr_atr = float(atr_batch.iloc[-1])

        # 3. Enrich state object
        state_obj.atr = curr_atr

        return {
            "tag": f"atr_{self.period}",
            "value": round(curr_atr, 6),
            "t": int(df.iloc[-1]['t']),
        }
