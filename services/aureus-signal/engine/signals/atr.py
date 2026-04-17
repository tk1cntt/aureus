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

    Phase 44.2: Verification layer — drift detection every 10 candles,
    full recalc every 50 candles to prevent silent failure.
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
        if hasattr(state_obj, 'atr') and state_obj.atr is not None:
            curr_atr = (state_obj.atr * (self.period - 1) + tr_now) / self.period
        else:
            curr_atr = self._full_calc_atr(df, tr_now)

        # 3. Phase 44.2: Verification layer
        verification_counter = getattr(state_obj, '_verification_counter', 0)
        if verification_counter > 0 and verification_counter % 10 == 0:
            atr_full = self._full_calc_atr(df, tr_now)
            if atr_full > 0:
                drift = abs(curr_atr - atr_full) / atr_full
                if drift > 0.0001:  # 0.01% threshold
                    logger.warning(
                        f"[DRIFT] ATR drift={drift:.4%} on {getattr(state_obj, 'symbol', '?')} — correcting"
                    )
                    curr_atr = atr_full

        if verification_counter > 0 and verification_counter % 50 == 0:
            curr_atr = self._full_calc_atr(df, tr_now)
            logger.debug(f"[44.2] ATR full recalc every-50 for {getattr(state_obj, 'symbol', '?')}")

        # 4. Enrich state object
        state_obj.atr = curr_atr

        return {
            "tag": f"atr_{self.period}",
            "value": round(curr_atr, 6),
            "t": int(df.iloc[-1]['t']),
        }

    def _full_calc_atr(self, df: pd.DataFrame, tr_now: float) -> float:
        """Full batch ATR calculation — used for warmup and verification."""
        h_series = df['h']
        l_series = df['l']
        pc_series = df['c'].shift(1)
        tr_series = pd.concat(
            [h_series - l_series, abs(h_series - pc_series), abs(l_series - pc_series)],
            axis=1,
        ).max(axis=1)

        atr_batch = tr_series.ewm(alpha=1 / self.period, adjust=False).mean()
        return float(atr_batch.iloc[-1])
