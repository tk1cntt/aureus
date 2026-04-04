import unittest
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Ensure the engine module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.snapshot_utils import build_snapshot
from engine.gap_detector import GapDetector
from datetime import datetime

class TestStory13(unittest.TestCase):
    def test_build_snapshot_dry_ema(self):
        # Case 1: EMAs are dictionaries (new format)
        mock_state = MagicMock()
        mock_state.emas = {
            21: {'current': 1.1},
            34: {'current': 1.2},
            55: {'current': 1.3},
            89: {'current': 1.4},
            100: {'current': 1.5},
            200: {'current': 1.6}
        }
        mock_state.transient_signals = {}
        mock_state.swing_points = []
        mock_state.obs = []
        mock_state.strategy_progress = {}
        mock_state.atr = 0.1
        mock_state.symbol = "BTCUSDT"
        
        candle = {'t': 1600000000, 'o': 1, 'h': 2, 'l': 0.5, 'c': 1.5, 'symbol': 'BTCUSDT'}
        
        snapshot = build_snapshot(mock_state, candle)
        
        self.assertEqual(snapshot['ema_21'], 1.1)
        self.assertEqual(snapshot['ema_200'], 1.6)

        # Case 2: EMAs are floats (fallback format)
        mock_state.emas = {21: 2.1, 34: 2.2, 55: 2.3, 89: 2.4, 100: 2.5, 200: 2.6}
        snapshot = build_snapshot(mock_state, candle)
        self.assertEqual(snapshot['ema_21'], 2.1)
        self.assertEqual(snapshot['ema_200'], 2.6)

    def test_gap_detector_parameterization(self):
        # We want to verify that GapDetector.find_gaps calls fetch with the right arguments
        # instead of building a string with .replace()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        detector = GapDetector(mock_pool)
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(detector.find_gaps("ETHUSDT", "M1", 48))
        
        args = mock_conn.fetch.call_args[0]
        # args[0] is the query string
        # args[1], args[2], args[3] should be symbol, timeframe, lookback_hours
        self.assertIn("$1", args[0])
        self.assertIn("$2", args[0])
        self.assertIn("$3", args[0])
        self.assertEqual(args[1], "ETHUSDT")
        self.assertEqual(args[2], "M1")
        self.assertEqual(args[3], 48)

if __name__ == '__main__':
    unittest.main()
