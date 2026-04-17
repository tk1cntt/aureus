import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal, SignalType
from typing import Dict, Any, Optional

logger = get_logger(__name__)
class VolumeSMASignal(BaseSignal):
    """
    Calculates Simple Moving Average of Volume.
    Updates state_obj.vol_sma_20 for Hybrid Judges.

    Phase 44.2: Incremental cache with circular buffer — O(1) per candle
    with drift verification every 10 candles, full recalc every 50 candles.
    """

    signal_type = SignalType.INDICATOR

    def __init__(self, period: int = 20, spike_threshold: float = 1.5):
        super().__init__(f"Volume SMA ({period})")
        self.period = period
        self.spike_threshold = spike_threshold

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < self.period:
            return None

        vol_col = 'v' if 'v' in df.columns else ('vol' if 'vol' in df.columns else None)
        if not vol_col:
            return None

        current_vol = float(df[vol_col].iloc[-1])

        # --- Phase 44.2: Incremental cache with verification ---
        buffer_attr = f"_vol_sma_{self.period}_buffer"
        sma_attr = f"vol_sma_{self.period}"

        # Full recalc every 50 candles (drift prevention)
        should_full_recalc = getattr(state_obj, '_verification_counter', 0) > 0 and getattr(state_obj, '_verification_counter', 0) % 50 == 0

        if not hasattr(state_obj, buffer_attr) or should_full_recalc:
            # Full calculation (warmup or drift prevention)
            recent_vol = df[vol_col].tail(self.period).fillna(0)
            sma_val = float(recent_vol.mean())
            setattr(state_obj, buffer_attr, list(df[vol_col].tail(self.period).fillna(0)))
            setattr(state_obj, sma_attr, sma_val)

            if should_full_recalc:
                logger.debug(f"[44.2] VolSMA full recalc every-50 for {getattr(state_obj, 'symbol', '?')}")
        else:
            # Incremental update: SMA = prev_SMA - oldest/n + new/n
            buffer = getattr(state_obj, buffer_attr)
            prev_sma = getattr(state_obj, sma_attr)

            oldest = buffer[0]
            new_sma = prev_sma - oldest / self.period + current_vol / self.period
            buffer.append(current_vol)
            buffer.pop(0)  # Maintain fixed size

            setattr(state_obj, buffer_attr, buffer)
            setattr(state_obj, sma_attr, new_sma)

            # Verification check every 10 candles
            if getattr(state_obj, '_verification_counter', 0) % 10 == 0:
                vol_full = float(df[vol_col].tail(self.period).fillna(0).mean())
                sma_incr = getattr(state_obj, sma_attr)
                if vol_full > 0:
                    drift = abs(sma_incr - vol_full) / vol_full
                    if drift > 0.0001:  # 0.01% threshold
                        logger.warning(
                            f"[DRIFT] VolSMA drift={drift:.4%} on {getattr(state_obj, 'symbol', '?')} — correcting"
                        )
                        setattr(state_obj, sma_attr, vol_full)
                        setattr(state_obj, buffer_attr, list(df[vol_col].tail(self.period).fillna(0)))

        sma_val = getattr(state_obj, sma_attr)

        # Only return metadata if volume spikes beyond the threshold
        if current_vol > sma_val * self.spike_threshold:
            return {
                "tag": f"vol_sma_{self.period}",
                "value": round(sma_val, 2),
                "current_vol": current_vol
            }

        return None
