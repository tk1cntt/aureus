import json
import logging
import os
import time
from typing import Dict, Any, Optional
import httpx

from .base import DecisionProvider, DecisionSignal

logger = logging.getLogger(__name__)

class TradingAgentsProvider(DecisionProvider):
    def __init__(self, endpoint: str, cache_ttl: float = 15.0):
        self.endpoint = endpoint
        self.cache_ttl = cache_ttl
        self._symbols_map: Dict[str, Any] = {}
        # Simple cache: dict of {symbol: (timestamp, signal_result)}
        self._cache: Dict[str, tuple[float, Optional[DecisionSignal]]] = {}

    async def setup(self) -> None:
        """Load symbols configuration."""
        try:
            # Assuming symbols.json is at the root of aureus-signal
            symbols_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "symbols.json")
            with open(symbols_path, "r") as f:
                self._symbols_map = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load symbols.json: {e}")
            self._symbols_map = {}

    def _format_external_symbol(self, symbol: str) -> str:
        """Format the internal symbol to external representation if needed."""
        # For this milestone, we use the directly mapped symbol string
        return symbol

    async def _fetch_from_api(self, symbol: str, context: Optional[Dict[str, Any]]) -> Optional[DecisionSignal]:
        """Make actual HTTP request to trading agents API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                external_symbol = self._format_external_symbol(symbol)
                payload = {
                    "symbol": external_symbol,
                    "context": context or {}
                }
                response = await client.post(f"{self.endpoint.rstrip('/')}/decisions", json=payload)
                response.raise_for_status()
                data = response.json()
                
                return DecisionSignal(
                    action=data.get("action", "HOLD"),
                    confidence=data.get("confidence", 0.0),
                    reasoning=data.get("reasoning", ""),
                    timestamp=int(time.time()),
                    symbol=symbol,
                    source="tradingagents",
                    metadata=data.get("metadata", {})
                )
        except Exception as e:
            logger.warning(f"Failed to fetch decision for {symbol}: {e}")
            return None

    async def get_decision(self, symbol: str, context: Optional[Dict[str, Any]] = None) -> Optional[DecisionSignal]:
        now = time.monotonic()
        # Check cache
        if symbol in self._cache:
            cache_time, cached_signal = self._cache[symbol]
            if now - cache_time < self.cache_ttl:
                return cached_signal

        # Cache miss or expired
        signal = await self._fetch_from_api(symbol, context)
        
        # Store in cache
        self._cache[symbol] = (time.monotonic(), signal)
        
        return signal
