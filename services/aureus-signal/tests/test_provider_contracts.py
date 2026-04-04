"""Tests for provider abstraction contracts (Phase 22).

Verifies:
- ABC enforcement (cannot instantiate abstract classes)
- DecisionSignal dataclass correctness
- RedisMarketDataProvider interface compliance
- Backward compatibility (existing imports unchanged)
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.providers.base import (
    MarketDataProvider,
    DecisionProvider,
    DecisionSignal,
)
from engine.providers.redis_provider import RedisMarketDataProvider
from engine.providers import (
    MarketDataProvider as MP_reexport,
    DecisionProvider as DP_reexport,
    DecisionSignal as DS_reexport,
    RedisMarketDataProvider as RMP_reexport,
)


class TestABCEnforcement(unittest.TestCase):
    """Verify abstract classes cannot be instantiated."""

    def test_market_data_provider_is_abstract(self):
        with self.assertRaises(TypeError):
            MarketDataProvider()

    def test_decision_provider_is_abstract(self):
        with self.assertRaises(TypeError):
            DecisionProvider()



class TestDecisionSignal(unittest.TestCase):
    """Verify DecisionSignal dataclass contract."""

    def test_required_fields(self):
        sig = DecisionSignal(
            action="BUY",
            confidence=0.85,
            reasoning="Strong bullish structure",
            timestamp=1710000000,
            symbol="XAUUSD",
            source="tradingagents",
        )
        self.assertEqual(sig.action, "BUY")
        self.assertAlmostEqual(sig.confidence, 0.85)
        self.assertEqual(sig.reasoning, "Strong bullish structure")
        self.assertEqual(sig.timestamp, 1710000000)
        self.assertEqual(sig.symbol, "XAUUSD")
        self.assertEqual(sig.source, "tradingagents")
        self.assertEqual(sig.metadata, {})

    def test_metadata_default_is_empty_dict(self):
        sig = DecisionSignal(
            action="HOLD", confidence=0.5, reasoning="", timestamp=0,
            symbol="BTCUSD", source="test",
        )
        self.assertIsInstance(sig.metadata, dict)
        self.assertEqual(len(sig.metadata), 0)

    def test_metadata_accepts_custom_dict(self):
        sig = DecisionSignal(
            action="SELL", confidence=0.9, reasoning="Breakdown confirmed",
            timestamp=1710000100, symbol="XAUUSD", source="manual",
            metadata={"model": "deepseek-r1", "latency_ms": 450},
        )
        self.assertEqual(sig.metadata["model"], "deepseek-r1")
        self.assertEqual(sig.metadata["latency_ms"], 450)



class TestRedisMarketDataProviderInterface(unittest.TestCase):
    """Verify RedisMarketDataProvider implements MarketDataProvider."""

    def test_is_subclass_of_market_data_provider(self):
        self.assertTrue(issubclass(RedisMarketDataProvider, MarketDataProvider))

    def test_constructor_accepts_required_params(self):
        redis = MagicMock()
        db = MagicMock()
        provider = RedisMarketDataProvider(redis_client=redis, db_pool=db)
        self.assertIsNotNone(provider)

    def test_constructor_accepts_optional_params(self):
        redis = MagicMock()
        db = MagicMock()
        provider = RedisMarketDataProvider(
            redis_client=redis, db_pool=db,
            group_name="custom-group", consumer_name="consumer-test",
        )
        self.assertEqual(provider._group_name, "custom-group")
        self.assertEqual(provider._consumer_name, "consumer-test")



class TestRedisMarketDataProviderGetHistorical(unittest.TestCase):
    """Verify get_historical() returns correctly formatted candles."""

    def test_returns_oldest_first_candle_dicts(self):
        mock_db = AsyncMock()
        # Simulate DB rows (newest first, as returned by ORDER BY DESC)
        mock_rows = [
            {
                "time": datetime(2026, 4, 3, 12, 2, tzinfo=timezone.utc),
                "open": 2300.50, "high": 2301.00, "low": 2299.80,
                "close": 2300.90, "volume": 150,
            },
            {
                "time": datetime(2026, 4, 3, 12, 1, tzinfo=timezone.utc),
                "open": 2299.00, "high": 2300.50, "low": 2298.50,
                "close": 2300.50, "volume": 200,
            },
        ]
        mock_db.fetch = AsyncMock(return_value=mock_rows)

        provider = RedisMarketDataProvider(redis_client=MagicMock(), db_pool=mock_db)
        candles = asyncio.run(provider.get_historical("XAUUSD", limit=2))

        # Should be oldest-first (reversed)
        self.assertEqual(len(candles), 2)
        self.assertLess(int(candles[0]["t"]), int(candles[1]["t"]))

        # Verify candle dict keys
        for c in candles:
            self.assertIn("t", c)
            self.assertIn("o", c)
            self.assertIn("h", c)
            self.assertIn("l", c)
            self.assertIn("c", c)
            self.assertIn("v", c)
            self.assertIn("symbol", c)
            self.assertEqual(c["symbol"], "XAUUSD")



class TestReexports(unittest.TestCase):
    """Verify __init__.py re-exports are correct."""

    def test_reexported_classes_are_same_objects(self):
        self.assertIs(MP_reexport, MarketDataProvider)
        self.assertIs(DP_reexport, DecisionProvider)
        self.assertIs(DS_reexport, DecisionSignal)
        self.assertIs(RMP_reexport, RedisMarketDataProvider)



class TestBackwardCompatibility(unittest.TestCase):
    """Verify existing engine imports still work after providers/ addition."""

    def test_candle_record_import_unchanged(self):
        from engine.state import CandleRecord
        # Verify CandleRecord can be imported and instantiated
        cr = CandleRecord(t=1710000000, price=2300.0)
        self.assertEqual(cr.t, 1710000000)
        self.assertEqual(cr.price, 2300.0)

    def test_symbol_state_import_unchanged(self):
        from engine.state import SymbolState
        state = SymbolState("XAUUSD")
        self.assertEqual(state.symbol, "XAUUSD")

    def test_execute_signals_for_candle_import_unchanged(self):
        from engine.live_engine import execute_signals_for_candle
        self.assertTrue(callable(execute_signals_for_candle))



if __name__ == "__main__":
    unittest.main()
