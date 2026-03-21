import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.pivots import PivotSignal


class TestPivotsExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=300)
        self.signals = {
            "pivots": PivotSignal(
                ext_period=3,
                min_amplitude=10,
                min_motion=1,
                point=1.0,
                digits=0,
            )
        }

    def _candle(self, idx: int) -> dict:
        candles = [
            {"t": 1705000000, "o": 100.0, "h": 110.0, "l": 90.0, "c": 100.0, "v": 200},
            {"t": 1705000060, "o": 100.0, "h": 110.0, "l": 90.0, "c": 100.0, "v": 201},
            {"t": 1705000120, "o": 150.0, "h": 160.0, "l": 140.0, "c": 150.0, "v": 202},
            {"t": 1705000180, "o": 100.0, "h": 110.0, "l": 90.0, "c": 100.0, "v": 203},
            {"t": 1705000240, "o": 100.0, "h": 200.0, "l": 90.0, "c": 200.0, "v": 204},
            {"t": 1705000300, "o": 80.0, "h": 125.0, "l": 60.0, "c": 70.0, "v": 205},
        ]
        candle = dict(candles[idx])
        candle.update({"tf": "M1", "symbol": self.symbol})
        return candle

    def _run_until(self, last_idx: int):
        state = None
        for i in range(last_idx + 1):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            state.transient_signals = {}
            execute_signals_for_candle(self.signals, df, state, self.symbol, None)
        self.assertIsNotNone(state)
        return state

    def test_execute_signals_emits_latest_confirmed_pivot_tag(self):
        state = self._run_until(5)
        tags = [item.get("tag") for item in state.signal_history]
        self.assertIn("ll", tags)

    def test_execute_signals_persists_pivot_timestamp_in_history(self):
        state = self._run_until(5)
        ll_entries = [item for item in state.signal_history if item.get("tag") == "ll"]
        self.assertGreater(len(ll_entries), 0)
        self.assertEqual(ll_entries[-1].get("t"), int(self._candle(5)["t"]))

    def test_execute_signals_keeps_expected_swing_point_contract(self):
        state = self._run_until(5)
        self.assertGreaterEqual(len(state.swing_points), 3)

        latest = state.swing_points[-1]
        self.assertIn("type", latest)
        self.assertIn(latest.get("type"), {"HH", "HL", "LH", "LL"})
        self.assertIn("price", latest)
        self.assertIn("t", latest)
        self.assertIn("is_high", latest)
        self.assertIsInstance(latest.get("is_high"), bool)


if __name__ == "__main__":
    unittest.main()
