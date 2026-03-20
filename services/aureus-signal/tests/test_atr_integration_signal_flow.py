import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.manager import WindowManager
from engine.signals.atr import ATRSignal


class TestATRSignalFlowIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.period = 14
        self.signal = ATRSignal(self.period)
        self.window_manager = WindowManager(max_window=200)

    def _candle(self, idx: int) -> dict:
        base = 2000 + idx * 0.25
        return {
            "t": 1700000000 + idx * 60,
            "o": base,
            "h": base + 1.5,
            "l": base - 1.2,
            "c": base + 0.4,
            "v": 100 + idx,
            "tf": "M1",
        }

    def test_warmup_then_incremental_continuity(self):
        emitted = []

        for i in range(self.period + 3):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            out = self.signal.calculate(df, state)
            emitted.append(out)

        # ATR should be unavailable through warmup and available immediately after.
        self.assertTrue(all(x is None for x in emitted[: self.period]))
        self.assertIsNotNone(emitted[self.period])

        warmup = emitted[self.period]
        assert warmup is not None
        self.assertEqual(warmup["tag"], f"atr_{self.period}")
        self.assertIsInstance(warmup["value"], float)

        # Once initialized, every next candle should continue producing ATR.
        for payload in emitted[self.period + 1 :]:
            self.assertIsNotNone(payload)

        state = self.window_manager.states[self.symbol]
        self.assertIsNotNone(state.atr)

    def test_output_timestamp_matches_latest_candle(self):
        for i in range(self.period + 1):
            df, state = self.window_manager.update(self.symbol, self._candle(i))

        out = self.signal.calculate(df, state)
        self.assertIsNotNone(out)
        assert out is not None

        self.assertEqual(out["t"], int(df.iloc[-1]["t"]))
        self.assertEqual(out["tag"], f"atr_{self.period}")


if __name__ == "__main__":
    unittest.main()
