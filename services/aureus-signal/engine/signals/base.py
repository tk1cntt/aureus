from abc import ABC, abstractmethod
import pandas as pd
import logging
from typing import Dict, Any, Optional

class BaseSignal(ABC):
    """Base class for all Atomic Signals (FVG, Sweep, EMA, etc.)"""
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate(self, df: pd.DataFrame, state: Dict[str, Any],
                  redis_client: Any = None, symbol: str = None) -> Optional[Dict[str, Any]]:
        """
        Perform calculation on the current candle window.
        Returns a dict of metadata if signal is active, else None.
        """
        pass

    def _log(self, logger, level, symbol, t, method, message):
        """Standardized log formatter with performance check."""
        lvl_num = getattr(logging, level.upper(), logging.DEBUG)
        if not logger.isEnabledFor(lvl_num):
            return
            
        prefix = f"[t={t}] [{symbol}] [{method}]"
        logger.log(lvl_num, f"{prefix} {message}")
