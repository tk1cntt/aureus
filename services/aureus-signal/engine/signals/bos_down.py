from .base import BaseSignal, SignalType
import pandas as pd
from typing import Dict, Any, Optional

class BOSDownSignal(BaseSignal):
    """Consumer signal for Break of Structure (Bearish continuation)."""
    signal_type = SignalType.EVENT
    TAG = "bos_down"

    def __init__(self):
        super().__init__("BOS Down")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        return state_obj.transient_signals.get(self.TAG)
