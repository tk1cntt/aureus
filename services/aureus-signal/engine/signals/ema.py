from .base import BaseSignal
import logging
import traceback
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-signal.ema")

class EMASignal(BaseSignal):
    """
    Exponential Moving Average signal.
    Emits tags like 'ema_{period}_up' (price > ema) or 'ema_{period}_cross_up'.
    """
    
    def __init__(self, period: int):
        super().__init__(f"EMA {period}")
        self.period = period
        self.tag_up = f"ema_{period}_up"
        self.tag_down = f"ema_{period}_down"
        self.tag_cross_up = f"ema_{period}_cross_up"
        self.tag_cross_down = f"ema_{period}_cross_down"
        self.prev_ema = None

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        try:
            if len(df) < 1:  # Need at least one candle
                return None

            curr_candle = df.iloc[-1]
            curr_close = float(curr_candle['c'])
            curr_t = int(curr_candle['t'])

            # Initialize state emas if missing
            if not hasattr(state_obj, 'emas'):
                state_obj.emas = {}

            # Check for cached value from previous candle
            cached_data = state_obj.emas.get(self.period)
            has_valid_cached_state = isinstance(cached_data, dict) and "current" in cached_data

            if has_valid_cached_state:
                # OPTIMIZED O(1) LOGIC (COM-05/SIG-02)
                prev_ema = float(cached_data["current"])

                # EMA formula: EMA = (Price * k) + (Prev_EMA * (1 - k))
                # k = 2 / (period + 1)
                k = 2.0 / (self.period + 1.0)
                curr_ema = (curr_close * k) + (prev_ema * (1.0 - k))
            else:
                # EXPLICIT FALLBACK LOGIC:
                # - warmup: require at least `period` candles before first emit
                # - malformed/partial cache: recompute deterministic batch ewm safely
                if len(df) < self.period:  # Standard warmup period
                    return None

                ema_series = df['c'].ewm(span=self.period, adjust=False).mean()
                curr_ema = float(ema_series.iloc[-1])
                prev_ema = float(ema_series.iloc[-2]) if len(ema_series) > 1 else curr_ema

            prev_close = float(df.iloc[-2]['c']) if len(df) > 1 else curr_close
            
            # Calculate slope (Quantitative Judge requirement)
            slope = (curr_ema - prev_ema) / curr_ema if curr_ema > 0 else 0
            
            # Store in state
            state_obj.emas[self.period] = {
                "current": curr_ema,
                "prev": prev_ema,
                "slope": slope
            }

            res: Dict[str, Any] = {"tag": None, "period": self.period, "value": curr_ema, "t": curr_t}

            # 2. State Tags (Above/Below)
            if curr_close > curr_ema:
                res["tag"] = self.tag_up
            else:
                res["tag"] = self.tag_down
                
            # 2. Cross Crossover Signals (Optional: can be logged separately)
            if prev_close <= prev_ema and curr_close > curr_ema:
                res["cross"] = self.tag_cross_up
            elif prev_close >= prev_ema and curr_close < curr_ema:
                res["cross"] = self.tag_cross_down
                
            return res
        except Exception as e:
            logger.error(f"[GLOBAL] [ema] [calculate] Error: EMASignal({self.period}) failed: {e}\n{traceback.format_exc()}")
            raise e
