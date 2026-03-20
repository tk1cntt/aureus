import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.atr import ATRSignal


class TestATRExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.period = 14
        self.window_manager = WindowManager(max_window=300)
        self.signals = {"atr_14": ATRSignal(self.period)}

    def _candle(self, idx: int) -> dict:
        base = 2050.0 + idx * 0.3
        spread = 1.4 + ((idx % 4) * 0.2)
        return {
            "t": 1701000000 + idx * 60,
            "o": base,
            "h": base + spread,
            "l": base - (spread - 0.3),
            "c": base + (0.2 if idx % 2 == 0 else 0.7),
            "v": 300 + idx,
            "tf": "M1",
            "symbol": self.symbol,
        }

    def _run_until(self, last_idx: int):
        state = None
        for i in range(last_idx + 1):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            state.transient_signals = {}
            execute_signals_for_candle(self.signals, df, state, self.symbol, None)
        return state

    def test_execute_signals_for_candle_emits_atr_after_warmup(self):
        state = self._run_until(self.period + 2)
        tags = [item.get("tag") for item in state.signal_history]
        self.assertIn("atr_14", tags)
        self.assertIsNotNone(state.atr)

    def test_atr_state_progresses_after_warmup(self):
        state = self._run_until(self.period + 1)
        atr_after_warmup = state.atr
        self.assertIsNotNone(atr_after_warmup)

        df, state = self.window_manager.update(self.symbol, self._candle(self.period + 2))
        state.transient_signals = {}
        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        self.assertIsNotNone(state.atr)
        self.assertNotEqual(atr_after_warmup, state.atr)

    def test_execute_signals_populates_atr_signal_history(self):
        state = self._run_until(self.period + 4)
        self.assertIsNotNone(state)

        atr_entries = [item for item in state.signal_history if item.get("tag") == "atr_14"]
        self.assertGreater(len(atr_entries), 0)
        self.assertEqual(atr_entries[-1].get("tag"), "atr_14")
        self.assertEqual(atr_entries[-1].get("t"), int(self._candle(self.period + 4)["t"]))


if __name__ == "__main__":
    unittest.main()
