import logging
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = logging.getLogger("aureus-signal.volume_sma")

class VolumeSMASignal(BaseSignal):
    """
    Calculates Simple Moving Average of Volume.
    Updates state_obj.vol_sma_20 for Hybrid Judges.
    """
    def __init__(self, period: int = 20):
        super().__init__(f"Volume SMA ({period})")
        self.period = period

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if len(df) < self.period:
            return None
            
        # Extract volume column
        vol_col = 'v' if 'v' in df.columns else ('vol' if 'vol' in df.columns else None)
        if not vol_col:
            return None

        # Calculate SMA
        recent_vol = df[vol_col].tail(self.period)
        sma_val = float(recent_vol.mean())
        
        # Enrich state object
        state_obj.vol_sma_20 = sma_val
        
        # Only return metadata if it's statistically significant or requested
        return {
            "tag": f"vol_sma_{self.period}",
            "value": round(sma_val, 2),
            "current_vol": float(df[vol_col].iloc[-1])
        }
