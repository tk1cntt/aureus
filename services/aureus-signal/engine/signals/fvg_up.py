from .base import BaseSignal
import pandas as pd
from typing import Dict, Any, Optional

class FVGUpSignal(BaseSignal):
    """Bullish Fair Value Gap signal."""
    TAG = "fvg_up"
    
    def __init__(self):
        super().__init__("Bullish FVG")

    def calculate(self, df: pd.DataFrame, state_obj: Any) -> Optional[Dict[str, Any]]:
        if len(df) < 3: return None
        c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
        
        if c3['l'] > c1['h']:
            fvg_data = {
                "tag": self.TAG,
                "direction": "BULLISH",
                "top": float(c3['l']),
                "bottom": float(c1['h']),
                "t": int(c3['t'])
            }
            state_obj.add_fvg(fvg_data)
            return fvg_data
        return None
