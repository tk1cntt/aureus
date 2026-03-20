import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.fvg import FVGSignal
from engine.signals.fvg_down import FVGDownSignal
from engine.signals.fvg_up import FVGUpSignal


class TestFVGExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=300)
        self.signals = {
            "fvg_processor": FVGSignal(),
            "fvg_up": FVGUpSignal(),
            "fvg_down": FVGDownSignal(),
        }

    def _candle(self, idx: int) -> dict:
        if idx == 0:
            return {
                "t": 1703000000,
                "o": 100.0,
                "h": 101.0,
                "l": 99.0,
                "c": 100.4,
                "v": 200,
                "tf": "M1",
                "symbol": self.symbol,
            }
        if idx == 1:
            return {
                "t": 1703000060,
                "o": 100.6,
                "h": 101.4,
                "l": 100.1,
                "c": 101.0,
                "v": 201,
                "tf": "M1",
                "symbol": self.symbol,
            }
        if idx == 2:
            return {
                "t": 1703000120,
                "o": 105.6,
                "h": 106.0,
                "l": 105.2,
                "c": 105.7,
                "v": 202,
                "tf": "M1",
                "symbol": self.symbol,
            }
        # Follow-up candle mitigates bullish gap by dropping into the zone.
        return {
            "t": 1703000180,
            "o": 104.8,
            "h": 105.3,
            "l": 104.5,
            "c": 104.9,
            "v": 203,
            "tf": "M1",
            "symbol": self.symbol,
        }

    def _run_until(self, last_idx: int):
        state = None
        for i in range(last_idx + 1):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            state.transient_signals = {}
            execute_signals_for_candle(self.signals, df, state, self.symbol, None)
        self.assertIsNotNone(state)
        return state

    def test_execute_signals_emits_fvg_tags_after_three_candles(self):
        state = self._run_until(2)

        tags = [item.get("tag") for item in state.signal_history]
        self.assertIn("fvg_up", tags)

    def test_execute_signals_populates_fvg_timestamp_in_signal_history(self):
        state = self._run_until(2)

        fvg_entries = [item for item in state.signal_history if item.get("tag") == "fvg_up"]
        self.assertGreater(len(fvg_entries), 0)
        self.assertEqual(fvg_entries[-1].get("t"), int(self._candle(2)["t"]))

    def test_execute_signals_emits_transient_fvg_event_keys(self):
        state = self._run_until(2)
        self.assertIn("fvg_bull_new", state.transient_signals)

        state = self._run_until(3)
        self.assertIn("fvg_bull_mitigated", state.transient_signals)


if __name__ == "__main__":
    unittest.main()
