import os
import sys
import unittest
from typing import Any

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.signals.sweep import SweepSignal


class _DummyState:
    def __init__(self):
        self.symbol = "XAUUSD"
        self.htf_trend = "NEUTRAL"
        self.obs: list[Any] = []
        self.signal_history: list[dict[str, Any]] = []
        self.transient_signals: dict[str, Any] = {}
        self.ai_events: list[str] = []

    def request_ai_update(self, event_type: str):
        self.ai_events.append(event_type)


class TestSweepSignalBehavior(unittest.TestCase):
    def setUp(self):
        self.signal = SweepSignal()

    @staticmethod
    def _df(rows):
        return pd.DataFrame(rows)

    def test_returns_none_when_targets_missing(self):
        state = _DummyState()
        df = self._df([
            {"t": 1, "o": 2000.0, "h": 2002.0, "l": 1998.0, "c": 2001.0},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.transient_signals, {})

    def test_bullish_sweep_emits_canonical_payload_and_transient(self):
        state = _DummyState()
        state.obs = [
            {
                "ob_type": "BULLISH", "bottom": 1999.5, "top": 2000.0, "t_start": 1700000000, "status": "PENDING"
            }
        ]
        df = self._df([
            {"t": 1700000060, "o": 2001.0, "h": 2002.0, "l": 1998.9, "c": 2000.5},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep")
        self.assertEqual(result["value"], "sweep_bull")
        self.assertIn("sweep", state.transient_signals)
        self.assertEqual(state.transient_signals["sweep"]["data"]["status"], "SWEEP")
        self.assertEqual(state.obs[0]["status"], "SWEEP")
        self.assertEqual(state.ai_events, [])

    def test_bearish_sweep_emits_even_when_htf_trend_is_bullish(self):
        state = _DummyState()
        state.htf_trend = "BULLISH"
        state.obs = [{"ob_type": "BEARISH", "bottom": 2009.0, "top": 2010.0, "t_start": 1700000000, "status": "PENDING"}]
        df = self._df([
            {"t": 1700000120, "o": 2008.0, "h": 2011.5, "l": 2007.4, "c": 2008.4},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep")
        self.assertEqual(result["value"], "sweep_bear")
        self.assertIn("sweep", state.transient_signals)

    def test_dedup_skips_existing_history_same_value_price_and_time(self):
        state = _DummyState()
        state.obs = [{"ob_type": "BULLISH", "bottom": 1999.5, "top": 2000.0, "t_start": 1700000000, "status": "PENDING"}]
        state.signal_history = [
            {
                "tag": "sweep",
                "value": "sweep_bull",
                "t": 1700000180,
                "data": {"price_swept": 1999.5},
            },
        ]
        df = self._df([
            {"t": 1700000180, "o": 2001.0, "h": 2002.0, "l": 1998.5, "c": 2000.2},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(len(state.obs), 1)
        self.assertNotIn("sweep", state.transient_signals)

    def test_ignores_malformed_targets_without_raising(self):
        state = _DummyState()
        state.obs = [
            "not-a-dict",
            {"ob_type": "BULLISH", "bottom": "bad"},
            {"ob_type": None, "bottom": 2000.0},
        ]
        df = self._df([
            {"t": 1700000240, "o": 2000.0, "h": 2000.8, "l": 1999.2, "c": 1999.9},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.transient_signals, {})
        self.assertEqual(len(state.obs), 3)

    def test_touched_status_emits_only_when_unmitigated(self):
        state = _DummyState()
        state.obs = [
            {
                "ob_type": "BULLISH",
                "bottom": 1999.0,
                "top": 2000.0,
                "t_start": 1700000000,
                "status": "TOUCHED",
                "_just_swept": True,
                "mitigated": False,
            }
        ]
        df = self._df([
            {"t": 1700000300, "o": 2000.3, "h": 2001.0, "l": 1999.6, "c": 2000.2},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep")
        self.assertEqual(result["value"], "sweep_touched_bull")
        self.assertIn("sweep", state.transient_signals)

    def test_mitigated_non_touched_emits_when_mitigation_age_under_five_minutes(self):
        state = _DummyState()
        state.obs = [
            {
                "ob_type": "BULLISH",
                "bottom": 1999.0,
                "top": 2000.0,
                "t_start": 1700000000,
                "status": "SWEEP",
                "_just_swept": True,
                "mitigated": True,
                "t_mitigation": 1700000205,
            }
        ]
        df = self._df([
            {"t": 1700000300, "o": 2000.1, "h": 2000.9, "l": 1998.9, "c": 2000.0},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep")
        self.assertEqual(result["value"], "sweep_bull")
        self.assertIn("sweep", state.transient_signals)

    def test_mitigated_non_touched_skips_when_mitigation_age_over_five_minutes(self):
        state = _DummyState()
        state.obs = [
            {
                "ob_type": "BULLISH",
                "bottom": 1999.0,
                "top": 2000.0,
                "t_start": 1700000000,
                "status": "SWEEP",
                "_just_swept": True,
                "mitigated": True,
                "t_mitigation": 1699999999,
            }
        ]
        df = self._df([
            {"t": 1700000300, "o": 2000.1, "h": 2000.9, "l": 1998.9, "c": 2000.0},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertNotIn("sweep", state.transient_signals)

    def test_clean_breakout_emits_after_broken_pending_second_outside_candle(self):
        state = _DummyState()
        state.obs = [
            {
                "ob_type": "BULLISH",
                "bottom": 1999.0,
                "top": 2000.0,
                "t_start": 1700000000,
                "status": "BROKEN_PENDING",
                "break_counter": 1,
                "mitigated": False,
            }
        ]
        df = self._df([
            {"t": 1700000360, "o": 1998.8, "h": 1998.9, "l": 1997.9, "c": 1998.2},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep")
        self.assertEqual(result["value"], "clean_breakout_bull")
        self.assertEqual(state.obs[0]["status"], "CLEAN_BREAKOUT")
        self.assertIn("sweep", state.transient_signals)

    def test_clean_breakout_respects_history_dedup_for_same_tick_and_price(self):
        state = _DummyState()
        state.obs = [
            {
                "ob_type": "BULLISH",
                "bottom": 1999.0,
                "top": 2000.0,
                "t_start": 1700000000,
                "status": "BROKEN_PENDING",
                "break_counter": 1,
                "mitigated": False,
            }
        ]
        state.signal_history = [
            {
                "tag": "sweep",
                "value": "clean_breakout_bull",
                "t": 1700000360,
                "data": {"price_swept": 1999.0},
            }
        ]
        df = self._df([
            {"t": 1700000360, "o": 1998.8, "h": 1998.9, "l": 1997.9, "c": 1998.2},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertNotIn("sweep", state.transient_signals)


if __name__ == "__main__":
    unittest.main()
