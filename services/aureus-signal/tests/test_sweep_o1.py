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
        self.market_regime = "SIDEWAYS"
        self.sweep_targets: list[Any] = []
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

    def test_bullish_sweep_emits_payload_transient_and_consumes_target(self):
        state = _DummyState()
        state.sweep_targets = [
            {
                "side": "BULLISH",
                "price": 1999.5,
                "type": "liquidity_low",
                "t_source": 1700000000,
                "fidelity": 0.9,
            }
        ]
        df = self._df([
            {"t": 1700000060, "o": 2001.0, "h": 2002.0, "l": 1998.9, "c": 2000.5},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep_bull")
        self.assertIn("sweep_bull", state.transient_signals)
        self.assertEqual(state.sweep_targets, [])
        self.assertIn("STOP_HUNT", state.ai_events)

    def test_bearish_sweep_respects_trend_dn_filter(self):
        state = _DummyState()
        state.market_regime = "TREND_DN"
        state.sweep_targets = [{"side": "BEARISH", "price": 2010.0, "type": "liquidity_high"}]
        df = self._df([
            {"t": 1700000120, "o": 2008.0, "h": 2011.5, "l": 2007.4, "c": 2008.4},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "sweep_bear")
        self.assertIn("sweep_bear", state.transient_signals)

    def test_dedup_skips_existing_history_same_tag_price_and_time(self):
        state = _DummyState()
        state.sweep_targets = [{"side": "BULLISH", "price": "1999.5", "type": "liquidity_low"}]
        state.signal_history = [
            {"tag": "sweep_bull", "price_swept": 1999.5, "t": 1700000180},
        ]
        df = self._df([
            {"t": 1700000180, "o": 2001.0, "h": 2002.0, "l": 1998.5, "c": 2000.2},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(len(state.sweep_targets), 1)
        self.assertNotIn("sweep_bull", state.transient_signals)

    def test_ignores_malformed_targets_without_raising(self):
        state = _DummyState()
        state.sweep_targets = [
            "not-a-dict",
            {"side": "BULLISH", "price": "bad"},
            {"side": None, "price": 2000.0},
        ]
        df = self._df([
            {"t": 1700000240, "o": 2000.0, "h": 2000.8, "l": 1999.2, "c": 1999.9},
        ])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.transient_signals, {})
        self.assertEqual(len(state.sweep_targets), 3)


if __name__ == "__main__":
    unittest.main()
