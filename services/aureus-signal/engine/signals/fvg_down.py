from .base import BaseSignal
import pandas as pd
from typing import Dict, Any, Optional

class FVGDownSignal(BaseSignal):
    """Bearish Fair Value Gap signal."""
    TAG = "fvg_down"
    
    def __init__(self):
        super().__init__("Bearish FVG")

    def calculate(self, df: pd.DataFrame, state_obj: Any) -> Optional[Dict[str, Any]]:
        if len(df) < 3: return None
        c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
        
        if c3['h'] < c1['l']:
            fvg_data = {
                "tag": self.TAG,
                "direction": "BEARISH",
                "top": float(c1['l']),
                "bottom": float(c3['h']),
                "t": int(c3['t'])
            }
            state_obj.add_fvg(fvg_data)
            return fvg_data
        return None
