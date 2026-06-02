from .base import BaseSignal, SignalType
import pandas as pd
from typing import Dict, Any, Optional

class BOSUpSignal(BaseSignal):
    """Consumer signal for Break of Structure (Bullish continuation)."""
    signal_type = SignalType.EVENT
    TAG = "bos_up"

    def __init__(self):
        super().__init__("BOS Up")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        return state_obj.transient_signals.get(self.TAG)
