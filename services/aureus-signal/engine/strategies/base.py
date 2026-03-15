from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Optional

class BaseStrategy(ABC):
    """Base class for all Strategy Evaluators (SMC Reversal, Trend Follow, etc.)"""

    def __init__(self, name: str, strategy_id: int = 0, weight: float = 1.0):
        self.name = name
        self.strategy_id = strategy_id
        self.weight = weight

    @abstractmethod
    def evaluate(self, df: pd.DataFrame, signals: Dict[str, Any], state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluate if the strategy is met based on active signals and current state.
        Returns a signal object (with score) if strategy is triggered.
        """
        pass
