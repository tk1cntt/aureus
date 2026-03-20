from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Optional


class BaseSignal(ABC):
    """Base class for all Atomic Signals (FVG, Sweep, EMA, etc.)"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Perform calculation on the current candle window.
        Runtime may pass optional keyword args (e.g. `redis_client`, `symbol`,
        or other contextual fields); implementations should ignore unsupported ones.

        Returns a dict of metadata if signal is active, else None.
        """
        pass
