import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.ema import EMASignal


class TestEMAExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.period = 21
        self.window_manager = WindowManager(max_window=300)
        self.signals = {f"ema_{self.period}": EMASignal(self.period)}

    def _candle(self, idx: int) -> dict:
        base = 2050.0 + idx * 0.35
        spread = 1.2 + ((idx % 5) * 0.15)
        return {
            "t": 1702000000 + idx * 60,
            "o": base,
            "h": base + spread,
            "l": base - (spread - 0.25),
            "c": base + (0.15 if idx % 2 == 0 else 0.55),
            "v": 320 + idx,
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

    @staticmethod
    def _normalized_records(state):
        return [item for item in state.log_signal_normalize if isinstance(item, dict)]

    def test_execute_signals_for_candle_emits_ema_after_warmup(self):
        state = self._run_until(self.period + 2)
        records = self._normalized_records(state)

        self.assertTrue(
            any(f"ema_{self.period}" in rec.get("signals", {}).get("ema", {}) for rec in records)
        )
        self.assertIn(self.period, state.emas)
        self.assertIsNotNone(state.emas[self.period].get("current"))

    def test_ema_state_progresses_after_warmup(self):
        state = self._run_until(self.period + 1)
        ema_after_warmup = state.emas[self.period]["current"]

        df, state = self.window_manager.update(self.symbol, self._candle(self.period + 2))
        state.transient_signals = {}
        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        self.assertIn(self.period, state.emas)
        self.assertNotEqual(ema_after_warmup, state.emas[self.period]["current"])

    def test_execute_signals_populates_ema_signal_history_timestamp(self):
        last_idx = self.period + 4
        state = self._run_until(last_idx)
        records = self._normalized_records(state)

        ema_records = [
            rec
            for rec in records
            if f"ema_{self.period}" in rec.get("signals", {}).get("ema", {})
        ]
        self.assertGreater(len(ema_records), 0)
        self.assertEqual(ema_records[-1].get("t"), int(self._candle(last_idx)["t"]))


if __name__ == "__main__":
    unittest.main()
