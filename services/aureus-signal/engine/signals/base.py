from abc import ABC, abstractmethod
from enum import Enum
import pandas as pd
from typing import Dict, Any, Optional


class SignalType(Enum):
    """Classifies signals as either continuous indicators or discrete events."""
    INDICATOR = "indicator"
    EVENT = "event"


class BaseSignal(ABC):
    """Base class for all Atomic Signals (FVG, Sweep, EMA, etc.)"""

    signal_type = SignalType.INDICATOR  # Default: safe for gradual migration

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def get_signal_type(cls) -> SignalType:
        st = getattr(cls, "signal_type", None)
        if st is None:
            import logging
            logging.getLogger(__name__).warning(
                f"Signal class {cls.__name__} missing signal_type, defaulting to INDICATOR"
            )
            return SignalType.INDICATOR
        return st

    @abstractmethod
    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Perform calculation on the current candle window.
        Runtime may pass optional keyword args (e.g. `redis_client`, `symbol`,
        or other contextual fields); implementations should ignore unsupported ones.

        Returns a dict of metadata if signal is active, else None.
        """
        pass
