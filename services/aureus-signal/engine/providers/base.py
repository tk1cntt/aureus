"""Provider abstraction interfaces for Aureus Signal Engine.

MarketDataProvider — supplies OHLCV candle data from any source.
DecisionProvider  — supplies AI/ML trading decisions (BUY/SELL/HOLD).
"""

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class DecisionSignal:
    """Normalized trading decision from any decision provider."""
    action: str            # BUY, SELL, HOLD (canonical subset)
    confidence: float      # 0.0 - 1.0
    reasoning: str         # Human-readable explanation
    timestamp: int         # Unix epoch seconds
    symbol: str            # Aureus symbol (e.g., XAUUSD)
    source: str            # Provider name (e.g., "tradingagents", "manual")
    metadata: Dict[str, Any] = field(default_factory=dict)


class MarketDataProvider(abc.ABC):
    """Abstract base for candle data providers.

    Implementations must supply raw OHLCV candles as dicts with keys:
    t (int, unix epoch), o, h, l, c (float), v (int/float), symbol (str).
    """

    @abc.abstractmethod
    async def subscribe(self, symbol: str) -> AsyncIterator[Dict[str, Any]]:
        """Yield candle dicts as they arrive (streaming).

        Each yielded dict MUST contain: {t, o, h, l, c, v, symbol}.
        """
        ...

    @abc.abstractmethod
    async def get_historical(self, symbol: str, limit: int = 1500) -> List[Dict[str, Any]]:
        """Fetch historical candles for warm-up, oldest-first order.

        Returns list of dicts with keys: {t, o, h, l, c, v, symbol}.
        """
        ...

    async def setup(self) -> None:
        """Optional one-time setup (connection pool, auth, etc.)."""
        pass

    async def teardown(self) -> None:
        """Optional cleanup."""
        pass


class DecisionProvider(abc.ABC):
    """Abstract base for AI/ML decision providers.

    Implementations return a DecisionSignal or None if no decision available.
    """

    @abc.abstractmethod
    async def get_decision(
        self, symbol: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[DecisionSignal]:
        """Request a trading decision for a symbol.

        Args:
            symbol: Aureus symbol identifier (e.g., XAUUSD).
            context: Optional context dict (market state, signals, etc.).

        Returns:
            DecisionSignal if a decision is available, None otherwise.
        """
        ...

    async def setup(self) -> None:
        """Optional one-time setup."""
        pass

    async def teardown(self) -> None:
        """Optional cleanup."""
        pass
