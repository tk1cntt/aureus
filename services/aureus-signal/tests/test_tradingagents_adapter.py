import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.providers.base import DecisionProvider, DecisionSignal
from engine.providers.tradingagents import TradingAgentsProvider


class TestTradingAgentsProvider(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Supply a fake endpoint
        self.provider = TradingAgentsProvider(endpoint="http://localhost:8005/v1")
        # In setup, mock the loading of JSON
        self.provider._symbols_map = {
            "XAUUSD": {"description": "Gold vs US Dollar"},
            "BTCUSD": {"description": "Bitcoin vs US Dollar"}
        }

    async def test_decision_provider_interface(self):
        # Must implement DecisionProvider
        self.assertTrue(issubclass(TradingAgentsProvider, DecisionProvider))
        self.assertTrue(hasattr(self.provider, "get_decision"))
        self.assertTrue(hasattr(self.provider, "setup"))

    async def test_symbol_mapping(self):
        # Mapping logic test
        self.assertIn("XAUUSD", self.provider._symbols_map)
        # Assuming the Provider uses a helper to format to external string
        mapped = self.provider._format_external_symbol("XAUUSD")
        # By default, TradingAgents might just take the same name or add a dash. Let's assume same for now
        self.assertEqual(mapped, "XAUUSD")

    @patch("engine.providers.tradingagents.time.monotonic")
    async def test_cache_and_backoff(self, mock_time):
        mock_time.return_value = 100.0

        mock_signal = DecisionSignal(
            action="BUY", confidence=0.8, reasoning="Test",
            timestamp=100, symbol="XAUUSD", source="tradingagents"
        )
        self.provider._fetch_from_api = AsyncMock(return_value=mock_signal)

        # First call hits API
        res1 = await self.provider.get_decision("XAUUSD")
        self.assertEqual(res1, mock_signal)
        self.assertEqual(self.provider._fetch_from_api.call_count, 1)

        # Second call immediately should hit cache (mock time unchanged)
        res2 = await self.provider.get_decision("XAUUSD")
        self.assertEqual(res2, mock_signal)
        self.assertEqual(self.provider._fetch_from_api.call_count, 1)

        # Fast forward time past TTL (default 15s)
        mock_time.return_value = 116.0
        res3 = await self.provider.get_decision("XAUUSD")
        self.assertEqual(self.provider._fetch_from_api.call_count, 2)

    @patch("engine.providers.tradingagents.httpx.AsyncClient.post")
    async def test_error_fallback(self, mock_post):
        # Force HTTP fetch to raise Exception
        mock_post.side_effect = Exception("Connection refused or 500 Server Error")

        # Should gracefully return None instead of crashing
        res = await self.provider.get_decision("XAUUSD")
        self.assertIsNone(res)

if __name__ == "__main__":
    unittest.main()
