from .base import BaseSignal
import pandas as pd
from typing import Dict, Any, Optional

class SweepBullSignal(BaseSignal):
    """Consumer signal for Bullish Stop Hunt (Price swept below target)."""
    TAG = "sweep_bull"
    
    def __init__(self):
        super().__init__("Sweep Bullish")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        # Consume from the transient signals populated by SweepProcessor
        return state_obj.transient_signals.get(self.TAG)
