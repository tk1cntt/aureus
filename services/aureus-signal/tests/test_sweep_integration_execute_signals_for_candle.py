import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.sweep import SweepSignal
from engine.signals.sweep_bear import SweepBearSignal
from engine.signals.sweep_bull import SweepBullSignal


class TestSweepExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=50)
        self.signals = {
            "sweep_processor": SweepSignal(),
            "sweep_bull": SweepBullSignal(),
            "sweep_bear": SweepBearSignal(),
        }

    def _push_candle(self, candle: dict):
        df, state = self.window_manager.update(self.symbol, candle)
        state.transient_signals = {}
        return df, state

    @staticmethod
    def _normalized_records(state):
        return [item for item in state.log_signal_normalize if isinstance(item, dict)]

    @staticmethod
    def _events_by_tag(record: dict, tag: str) -> list[dict]:
        events = record.get("signals", {}).get("events", [])
        return [
            evt for evt in events
            if isinstance(evt, dict) and str(evt.get("tag")) == tag
        ]

    def test_execute_signals_emits_sweep_bull_and_transient_key(self):
        candle = {
            "t": 1702000000,
            "o": 2001.0,
            "h": 2002.0,
            "l": 1998.7,
            "c": 2000.8,
            "v": 250,
            "tf": "M1",
            "symbol": self.symbol,
        }
        df, state = self._push_candle(candle)
        state.obs = [
            {
                "ob_type": "BULLISH", "bottom": 1999.0, "top": 2000.0, "t_start": 1701999940, "status": "PENDING"
            }
        ]

        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        records = self._normalized_records(state)
        sweep_events = [
            evt
            for rec in records
            for evt in self._events_by_tag(rec, "sweep")
        ]
        values = [evt.get("value") for evt in sweep_events]
        self.assertIn("sweep_bull", values)
        self.assertIn("sweep", state.transient_signals)

    def test_execute_signals_dedup_prevents_duplicate_history_same_candle(self):
        candle = {
            "t": 1702000060,
            "o": 2001.2,
            "h": 2002.1,
            "l": 1998.6,
            "c": 2000.7,
            "v": 251,
            "tf": "M1",
            "symbol": self.symbol,
        }
        df, state = self._push_candle(candle)
        state.obs = [{"ob_type": "BULLISH", "bottom": 1999.0, "top": 2000.0, "t_start": 1701999940, "status": "PENDING"}]

        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        # Seed canonical sweep history shape so processor dedup guard can match.
        state.signal_history.append(
            {
                "tag": "sweep",
                "value": "sweep_bull",
                "t": int(candle["t"]),
                "data": {"price_swept": 1999.0},
            }
        )

        records_before = self._normalized_records(state)
        before_second_run = sum(len(self._events_by_tag(rec, "sweep")) for rec in records_before)

        # Re-seed same target in the same candle: dedup should suppress processor emission.
        state.transient_signals = {}
        state.obs = [{"ob_type": "BULLISH", "bottom": 1999.0, "top": 2000.0, "t_start": 1701999940, "status": "PENDING"}]
        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        records_after = self._normalized_records(state)
        after_second_run = sum(len(self._events_by_tag(rec, "sweep")) for rec in records_after)
        self.assertEqual(before_second_run, after_second_run)

    def test_execute_signals_emits_sweep_bear_with_bearish_target(self):
        candle = {
            "t": 1702000120,
            "o": 2007.0,
            "h": 2012.4,
            "l": 2006.2,
            "c": 2007.9,
            "v": 252,
            "tf": "M1",
            "symbol": self.symbol,
        }
        df, state = self._push_candle(candle)
        state.obs = [{"ob_type": "BEARISH", "top": 2011.0, "bottom": 2010.0, "t_start": 1701999940, "status": "PENDING"}]

        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        records = self._normalized_records(state)
        sweep_events = [
            evt
            for rec in records
            for evt in self._events_by_tag(rec, "sweep")
        ]
        values = [evt.get("value") for evt in sweep_events]
        self.assertIn("sweep_bear", values)
        self.assertIn("sweep", state.transient_signals)


if __name__ == "__main__":
    unittest.main()
