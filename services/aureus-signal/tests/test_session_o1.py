import os
import sys
import unittest
from datetime import datetime, timezone

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.signals.session import SessionSignal


class _DummyState:
    def __init__(self):
        self.symbol = "XAUUSD"
        self.current_session = "OFF_MARKET"
        self.tracking_vars = {}


def _df_from_row(row):
    return pd.DataFrame([row])


class TestSessionSignalBehavior(unittest.TestCase):
    def setUp(self):
        self.signal = SessionSignal(gmt_user=4)

    def test_calculate_returns_none_for_missing_required_columns(self):
        state = _DummyState()
        df = pd.DataFrame([{"t": 1704067200, "o": 2050.0, "h": 2052.0}])

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.current_session, "OFF_MARKET")

    def test_classifies_gmt7_boundaries_as_expected(self):
        state = _DummyState()

        london_result = self.signal.calculate(
            _df_from_row({"t": 1704092400, "o": 2051.0, "h": 2052.0, "l": 2050.0}),  # 02:00 New York (winter)
            state,
        )
        self.assertIsNotNone(london_result)
        self.assertEqual(london_result["session"], "LONDON")

        ny_result = self.signal.calculate(
            _df_from_row({"t": 1704110400, "o": 2052.0, "h": 2053.0, "l": 2051.0}),  # 07:00 New York (winter)
            state,
        )
        self.assertIsNotNone(ny_result)
        self.assertEqual(ny_result["session"], "NEW_YORK")

        lunch_result = self.signal.calculate(
            _df_from_row({"t": 1704128400, "o": 2053.0, "h": 2054.0, "l": 2052.0}),  # 12:00 New York (winter)
            state,
        )
        self.assertIsNotNone(lunch_result)
        self.assertEqual(lunch_result["session"], "LUNCH_TIME")

        asia_result = self.signal.calculate(
            _df_from_row({"t": 1704153600, "o": 2050.0, "h": 2051.0, "l": 2049.0}),  # 19:00 New York (winter)
            state,
        )
        self.assertIsNotNone(asia_result)
        self.assertEqual(asia_result["session"], "ASIA")

        asia_dst_result = self.signal.calculate(
            _df_from_row({"t": 1719874800, "o": 2050.0, "h": 2051.0, "l": 2049.0}),  # 19:00 New York (summer/EDT)
            state,
        )
        self.assertIsNotNone(asia_dst_result)
        self.assertEqual(asia_dst_result["session"], "ASIA")

    def test_updates_session_hlo_deterministically_within_same_session(self):
        state = _DummyState()

        self.signal.calculate(
            _df_from_row({"t": 1704067200, "o": 2050.0, "h": 2051.0, "l": 2049.5}),
            state,
        )
        self.signal.calculate(
            _df_from_row({"t": 1704067260, "o": 2050.4, "h": 2051.8, "l": 2049.2}),
            state,
        )

        hlo = state.tracking_vars["session_hlo"]
        self.assertEqual(hlo["session"], "ASIA")
        self.assertEqual(hlo["open"], 2050.0)
        self.assertEqual(hlo["high"], 2051.8)
        self.assertEqual(hlo["low"], 2049.2)

    def test_invalid_timestamp_is_guarded_without_state_mutation(self):
        state = _DummyState()
        df = _df_from_row({"t": "bad-ts", "o": 2050.0, "h": 2051.0, "l": 2049.0})

        result = self.signal.calculate(df, state)

        self.assertIsNone(result)
        self.assertEqual(state.current_session, "OFF_MARKET")
        self.assertEqual(state.tracking_vars, {})

    def test_dst_boundary_detection_matches_european_schedule(self):
        before_start = datetime(2024, 3, 31, 0, 59, tzinfo=timezone.utc)
        after_start = datetime(2024, 3, 31, 1, 0, tzinfo=timezone.utc)
        before_end = datetime(2024, 10, 27, 0, 59, tzinfo=timezone.utc)
        after_end = datetime(2024, 10, 27, 1, 0, tzinfo=timezone.utc)

        self.assertFalse(self.signal.is_broker_dst(before_start))
        self.assertTrue(self.signal.is_broker_dst(after_start))
        self.assertTrue(self.signal.is_broker_dst(before_end))
        self.assertFalse(self.signal.is_broker_dst(after_end))


if __name__ == "__main__":
    unittest.main()
