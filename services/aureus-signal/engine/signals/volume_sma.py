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
    """
    signal_type = SignalType.INDICATOR

    def __init__(self, period: int = 20, spike_threshold: float = 1.5):
        super().__init__(f"Volume SMA ({period})")
        self.period = period
        self.spike_threshold = spike_threshold

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < self.period:
            return None
            
        # Extract volume column
        vol_col = 'v' if 'v' in df.columns else ('vol' if 'vol' in df.columns else None)
        if not vol_col:
            return None

        # Calculate SMA with missing data imputated to 0
        recent_vol = df[vol_col].tail(self.period).fillna(0)
        sma_val = float(recent_vol.mean())
        
        # Enrich state object dynamically to support multiple volume SMA periods
        setattr(state_obj, f"vol_sma_{self.period}", sma_val)
        
        current_vol = float(df[vol_col].iloc[-1])
        
        # Only return metadata if volume spikes beyond the threshold
        if current_vol > sma_val * self.spike_threshold:
            return {
                "tag": f"vol_sma_{self.period}",
                "value": round(sma_val, 2),
                "current_vol": current_vol
            }
            
        return None
