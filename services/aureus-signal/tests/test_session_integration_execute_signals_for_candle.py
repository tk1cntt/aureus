import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.session import SessionSignal


class TestSessionExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=300)
        self.signals = {"session": SessionSignal(gmt_user=7)}

    def _candle(self, ts_unix: int, idx: int) -> dict:
        return {
            "t": ts_unix,
            "o": 2050.0 + idx * 0.25,
            "h": 2051.0 + idx * 0.25,
            "l": 2049.0 + idx * 0.25,
            "c": 2050.5 + idx * 0.25,
            "v": 300 + idx,
            "tf": "M1",
            "symbol": self.symbol,
        }

    def _run_for_timestamps(self, timestamps: list[int]):
        state = None
        for idx, ts in enumerate(timestamps):
            df, state = self.window_manager.update(self.symbol, self._candle(ts, idx))
            state.transient_signals = {}
            execute_signals_for_candle(self.signals, df, state, self.symbol, None)
        self.assertIsNotNone(state)
        return state

    def test_execute_signals_logs_market_session_tag_with_expected_timestamp(self):
        ts = 1704067200  # 07:00 in GMT+7
        state = self._run_for_timestamps([ts])

        entries = [item for item in state.signal_history if item.get("tag") == "market_session"]
        self.assertGreater(len(entries), 0)
        self.assertEqual(entries[-1].get("t"), ts)

    def test_current_session_progresses_across_defined_windows(self):
        timestamps = [
            1704067200,  # 07:00 GMT+7 => ASIA
            1704092400,  # 14:00 GMT+7 => LONDON
            1704110400,  # 19:00 GMT+7 => NEW_YORK
        ]
        state = self._run_for_timestamps(timestamps)

        self.assertEqual(state.current_session, "NEW_YORK")
        self.assertIn("session_hlo", state.tracking_vars)
        self.assertEqual(state.tracking_vars["session_hlo"].get("session"), "NEW_YORK")


if __name__ == "__main__":
    unittest.main()
