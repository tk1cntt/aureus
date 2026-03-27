import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.volume_sma import VolumeSMASignal


class TestVolumeSMAExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=300)
        self.signals = {
            "volume_sma": VolumeSMASignal(period=5, spike_threshold=1.5)
        }

    def _candle(self, idx: int) -> dict:
        v = 100 if idx < 5 else 300  # Spike on the 6th candle (idx 5)
        candles = [
            {"t": 1705000000 + idx * 60, "o": 100.0, "h": 110.0, "l": 90.0, "c": 100.0, "v": v}
        ]
        candle = dict(candles[0])
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

    @staticmethod
    def _normalized_records(state):
        return [item for item in state.log_signal_normalize if isinstance(item, dict)]

    @staticmethod
    def _event_tags(record: dict) -> set[str]:
        events = record.get("signals", {}).get("events", [])
        return {
            str(evt.get("tag"))
            for evt in events
            if isinstance(evt, dict) and evt.get("tag") is not None
        }

    def test_execute_signals_emits_volume_sma_on_spike(self):
        state = self._run_until(5)  # 6 candles total, 6th is spike
        records = self._normalized_records(state)

        self.assertTrue(any("vol_sma_5" in self._event_tags(rec) for rec in records))

        # Verify state property dynamic assignment
        self.assertTrue(hasattr(state, "vol_sma_5"))

    def test_execute_signals_suppresses_noise_on_no_spike(self):
        # Run only first 5 candles where v = 100 (No spike)
        state = self._run_until(4)
        records = self._normalized_records(state)

        self.assertFalse(any("vol_sma_5" in self._event_tags(rec) for rec in records))


if __name__ == "__main__":
    unittest.main()
