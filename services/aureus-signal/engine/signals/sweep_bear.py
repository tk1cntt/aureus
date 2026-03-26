from .base import BaseSignal
import pandas as pd
from typing import Dict, Any, Optional

class SweepBearSignal(BaseSignal):
    """Consumer signal for Bearish Stop Hunt (Price swept above target)."""
    TAG = "sweep_bear"
    
    def __init__(self):
        super().__init__("Sweep Bearish")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        # Consume from the transient signals populated by SweepProcessor
        # TODO: Kiểm tra nến hiện tại và state_obj.transient_signals.get(self.TAG) có cùng thời gian hay không
        if state_obj.transient_signals.get(self.TAG) and int(state_obj.transient_signals.get(self.TAG).get("t")) == int(df.iloc[-1]["t"]):
            return state_obj.transient_signals.get(self.TAG)
        return None
