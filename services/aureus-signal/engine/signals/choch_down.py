from .base import BaseSignal, SignalType
import pandas as pd
from typing import Dict, Any, Optional

class CHOCHDownSignal(BaseSignal):
    """Consumer signal for Market Structure Shift (Bearish)."""
    signal_type = SignalType.EVENT
    TAG = "choch_down"
    
    def __init__(self):
        super().__init__("CHoCH Down")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        # Consume from the central StructureProcessor
        return state_obj.transient_signals.get(self.TAG)
