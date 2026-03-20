import os
import sys
import unittest
from typing import Any

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.signals.fvg import FVGSignal


class _DummyState:
    def __init__(self):
        self.fvgs: list[Any] = []
        self.transient_signals = {}

    def add_fvg(self, fvg_data):
        payload = dict(fvg_data)
        payload.setdefault("state", "FRESH")
        self.fvgs.append(payload)


def _df(rows):
    return pd.DataFrame(rows)


class TestFVGSignalBehavior(unittest.TestCase):
    def setUp(self):
        self.signal = FVGSignal()

    def test_returns_none_when_candle_count_is_insufficient(self):
        state = _DummyState()
        df = _df([
            {"t": 1, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0},
            {"t": 2, "o": 100.5, "h": 101.5, "l": 99.5, "c": 100.8},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.fvgs, [])

    def test_detects_bullish_gap_and_emits_transient_new_key(self):
        state = _DummyState()
        df = _df([
            {"t": 1, "o": 100.0, "h": 101.0, "l": 99.5, "c": 100.5},
            {"t": 2, "o": 101.2, "h": 101.8, "l": 100.9, "c": 101.4},
            {"t": 3, "o": 105.5, "h": 106.2, "l": 105.1, "c": 105.8},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["direction"], "BULLISH")
        self.assertIn("fvg_bull_new", state.transient_signals)
        self.assertEqual(len(state.fvgs), 1)
        self.assertEqual(state.fvgs[0]["direction"], "BULLISH")

    def test_detects_bearish_gap_and_emits_transient_new_key(self):
        state = _DummyState()
        df = _df([
            {"t": 10, "o": 120.0, "h": 121.0, "l": 119.5, "c": 120.4},
            {"t": 11, "o": 119.8, "h": 120.1, "l": 118.9, "c": 119.1},
            {"t": 12, "o": 114.0, "h": 114.4, "l": 113.2, "c": 113.8},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["direction"], "BEARISH")
        self.assertIn("fvg_bear_new", state.transient_signals)
        self.assertEqual(len(state.fvgs), 1)
        self.assertEqual(state.fvgs[0]["direction"], "BEARISH")

    def test_mitigation_emits_once_for_existing_bullish_fvg(self):
        state = _DummyState()
        state.fvgs = [
            {
                "t": 100,
                "direction": "BULLISH",
                "top": 105.0,
                "bottom": 101.0,
                "state": "FRESH",
            }
        ]

        first_df = _df([
            {"t": 200, "o": 107.0, "h": 107.3, "l": 104.0, "c": 106.9},
            {"t": 201, "o": 106.8, "h": 107.1, "l": 106.2, "c": 106.4},
            {"t": 202, "o": 104.9, "h": 105.4, "l": 104.4, "c": 104.7},
        ])

        first = self.signal.calculate(first_df, state)

        self.assertIsNone(first)
        self.assertIn("fvg_bull_mitigated", state.transient_signals)
        mitigated_payload = state.transient_signals["fvg_bull_mitigated"]
        self.assertEqual(mitigated_payload["direction"], "BULLISH")

        state.transient_signals = {}
        second_df = _df([
            {"t": 201, "o": 106.8, "h": 107.1, "l": 105.0, "c": 106.4},
            {"t": 202, "o": 104.9, "h": 105.4, "l": 104.4, "c": 104.7},
            {"t": 203, "o": 104.6, "h": 105.1, "l": 104.0, "c": 104.3},
        ])

        second = self.signal.calculate(second_df, state)

        self.assertIsNone(second)
        self.assertNotIn("fvg_bull_mitigated", state.transient_signals)
        self.assertTrue(state.fvgs[0].get("_mitigated_emitted"))

    def test_ignores_malformed_fvg_state_entries_without_raising(self):
        state = _DummyState()
        state.fvgs = [
            {"direction": "BULLISH", "top": "bad", "bottom": 101.0, "state": "FRESH"},
            {"direction": None, "top": 105.0, "bottom": 101.0},
            "not-a-dict",
        ]
        df = _df([
            {"t": 1, "o": 100.0, "h": 100.8, "l": 99.2, "c": 100.1},
            {"t": 2, "o": 100.2, "h": 100.7, "l": 99.5, "c": 100.0},
            {"t": 3, "o": 100.1, "h": 100.4, "l": 99.4, "c": 99.7},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.transient_signals, {})


if __name__ == "__main__":
    unittest.main()
