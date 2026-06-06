"""
Unit tests for bos_up/bos_down signal emission in StructureSignal.

Tests:
1. BOS emission when no opposing extreme exists
2. CHOCH emission when opposing extreme exists (not BOS)
3. BOSDown emission when no opposing extreme
4. BOSUpSignal/BOSDownSignal consumer signals read from transient_signals
5. signal_factory registers bos_up/bos_down
"""
import unittest
import pandas as pd
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.structure import StructureSignal
from engine.signals.bos_up import BOSUpSignal
from engine.signals.bos_down import BOSDownSignal
from engine.signal_factory import create_signal_set


class MockState:
    """Mock state object for testing."""

    def __init__(self, swing_points=None, transient_signals=None, obs=None, signal_history=None):
        self.swing_points = swing_points or []
        self.transient_signals = transient_signals or {}
        self.obs = obs or []
        self.signal_history = signal_history or []
        self.symbol = "XAUUSD"
        self.strategy_progress = {}


class TestBOSEmission(unittest.TestCase):
    """Test BOS emission when no opposing extreme exists."""

    def test_bos_up_emitted_when_no_opposing_extreme(self):
        """
        Scenario: HH at t=1000, NO LL after it before breakout.
        Price breaks above HH -> emit bos_up (zone_base_idx == -1).
        """
        # swing_points: HH at t=1000, no LL after it
        swing_points = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
        ]

        state = MockState(swing_points=swing_points)

        # df: candles where price breaks above HH at 1950.0
        # t=1000: HH candle, t=1001: breakout candle above HH
        df = pd.DataFrame({
            't': [998, 999, 1000, 1001, 1002],
            'o': [1940, 1945, 1950, 1955, 1960],
            'h': [1955, 1960, 1965, 1970, 1975],  # All candles above 1950 HH
            'l': [1935, 1940, 1945, 1950, 1955],
            'c': [1950, 1955, 1960, 1965, 1970],
        })

        signal = StructureSignal().calculate(df, state)

        # Verify BOS was emitted
        self.assertIsNotNone(signal, "BOS signal should be emitted")
        self.assertEqual(signal.get("tag"), "bos_up", "Should emit bos_up tag")
        self.assertIn("bos_up", state.transient_signals, "bos_up should be in transient_signals")
        self.assertTrue(state.swing_points[1]["is_bos"], "Swing point should be marked as bos")
        self.assertEqual(state.swing_points[1]["bos_type"], "Up", "Bos type should be Up")

    def test_choch_up_emitted_when_opposing_extreme_exists(self):
        """
        Scenario: HH at t=1000, LL at t=1050 (opposing extreme with t < breakout_t).
        Price breaks above HH at t=1100 -> emit choch_up (NOT bos_up).
        The key is: LL must have t < breakout_t (t < 1100 in this case).
        """
        # swing_points: HH at t=1000, LL at t=1050 (opposing extreme with t < breakout_t)
        swing_points = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1050, "price": 1880.0, "type": "LL", "is_choch": False, "is_bos": False, "is_high": False},
        ]

        state = MockState(swing_points=swing_points)

        # df: HH at t=1000, LL at t=1050, then breakout above HH at t=1100
        # Since 1050 < 1100 (breakout_t), the LL qualifies as opposing extreme
        df = pd.DataFrame({
            't': [998, 999, 1000, 1020, 1030, 1040, 1050, 1060, 1070, 1080, 1090, 1100],
            'o': [1940, 1945, 1950, 1945, 1940, 1935, 1890, 1895, 1900, 1905, 1910, 1960],
            'h': [1955, 1960, 1965, 1948, 1945, 1940, 1920, 1930, 1940, 1950, 1955, 1970],  # Break above 1950 at t=1100
            'l': [1935, 1940, 1945, 1930, 1925, 1920, 1880, 1890, 1900, 1910, 1915, 1920],
            'c': [1950, 1955, 1960, 1940, 1935, 1930, 1895, 1910, 1920, 1930, 1950, 1965],
        })

        signal = StructureSignal().calculate(df, state)

        # Verify CHOCH was emitted (not BOS)
        # The LL at t=1050 has t < breakout_t(1100), so it's an opposing extreme
        self.assertIsNotNone(signal, "CHOCH signal should be emitted")
        self.assertIn(signal.get("tag"), ["choch_up", "choch"], "Should emit choch_up tag")
        self.assertIn("choch_up", state.transient_signals, "choch_up should be in transient_signals")
        self.assertTrue(state.swing_points[1]["is_choch"], "Swing point should be marked as choch")
        self.assertFalse(state.swing_points[1]["is_bos"], "Swing point should NOT be marked as bos")
        # Verify bos_up was NOT emitted
        self.assertNotIn("bos_up", state.transient_signals, "bos_up should NOT be in transient_signals")

    def test_bos_down_emitted_when_no_opposing_extreme(self):
        """
        Scenario: LL at t=1000, NO HH after it before breakdown.
        Price breaks below LL -> emit bos_down (zone_base_idx == -1).
        """
        # swing_points: LL at t=1000, no HH after it
        swing_points = [
            {"t": 900, "price": 2000.0, "type": "HL", "is_choch": False, "is_bos": False, "is_high": False},
            {"t": 1000, "price": 1950.0, "type": "LL", "is_choch": False, "is_bos": False, "is_high": False},
        ]

        state = MockState(swing_points=swing_points)

        # df: candles where price breaks below LL at 1950.0
        df = pd.DataFrame({
            't': [998, 999, 1000, 1001, 1002],
            'o': [1960, 1955, 1950, 1945, 1940],
            'h': [1965, 1960, 1955, 1950, 1945],  # All candles below 1950 LL
            'l': [1945, 1940, 1935, 1930, 1925],
            'c': [1955, 1945, 1940, 1935, 1930],
        })

        signal = StructureSignal().calculate(df, state)

        # Verify BOS was emitted
        self.assertIsNotNone(signal, "BOS signal should be emitted")
        self.assertEqual(signal.get("tag"), "bos_down", "Should emit bos_down tag")
        self.assertIn("bos_down", state.transient_signals, "bos_down should be in transient_signals")
        self.assertTrue(state.swing_points[1]["is_bos"], "Swing point should be marked as bos")
        self.assertEqual(state.swing_points[1]["bos_type"], "Down", "Bos type should be Down")

    def test_choch_down_emitted_when_opposing_extreme_exists(self):
        """
        Scenario: LL at t=1000, HH at t=1050 (opposing extreme with t < breakout_t).
        Price breaks below LL at t=1100 -> emit choch_down (NOT bos_down).
        The key is: HH must have t < breakout_t (t < 1100 in this case).
        """
        # swing_points: LL at t=1000, HH at t=1050 (opposing extreme with t < breakout_t)
        swing_points = [
            {"t": 900, "price": 2000.0, "type": "HL", "is_choch": False, "is_bos": False, "is_high": False},
            {"t": 1000, "price": 1950.0, "type": "LL", "is_choch": False, "is_bos": False, "is_high": False},
            {"t": 1050, "price": 2020.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
        ]

        state = MockState(swing_points=swing_points)

        # df: LL at t=1000, HH at t=1050, then breakout below LL at t=1100
        # All candles before t=1100 must stay ABOVE 1950 (no breakdown)
        # First breakdown at t=1100 (after HH at t=1050)
        df = pd.DataFrame({
            't': [998, 999, 1000, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 1080, 1090, 1100],
            'o': [1965, 1960, 1960, 1965, 1970, 1975, 1980, 2000, 1990, 1980, 1970, 1960, 1940],
            'h': [1970, 1965, 1965, 1970, 1975, 1980, 1985, 2010, 2000, 1990, 1980, 1970, 1950],
            'l': [1960, 1955, 1955, 1960, 1965, 1970, 1975, 1990, 1980, 1970, 1960, 1955, 1920],
            'c': [1965, 1960, 1960, 1965, 1970, 1975, 1980, 1995, 1985, 1975, 1965, 1955, 1930],
        })

        signal = StructureSignal().calculate(df, state)

        # Verify CHOCH was emitted (not BOS)
        # The HH at t=1050 has t=1050 < breakout_t=1100, so it's an opposing extreme
        self.assertIsNotNone(signal, "CHOCH signal should be emitted")
        self.assertEqual(signal.get("tag"), "choch_down", "Should emit choch_down tag")
        self.assertIn("choch_down", state.transient_signals, "choch_down should be in transient_signals")
        self.assertTrue(state.swing_points[1]["is_choch"], "Swing point should be marked as choch")
        self.assertFalse(state.swing_points[1]["is_bos"], "Swing point should NOT be marked as bos")
        self.assertNotIn("bos_down", state.transient_signals, "bos_down should NOT be in transient_signals")


class TestBOSConsumerSignals(unittest.TestCase):
    """Test BOSUpSignal and BOSDownSignal consumer signals."""

    def test_bos_up_signal_reads_from_transient(self):
        """BOSUpSignal.calculate() should read bos_up from transient_signals."""
        df = pd.DataFrame({'t': [1], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        state = MockState(transient_signals={
            "bos_up": {"tag": "bos_up", "t": 1000, "value": "bos_up", "data": {"price": 1950.0}}
        })

        bos_up_signal = BOSUpSignal()
        result = bos_up_signal.calculate(df, state)

        self.assertIsNotNone(result, "Should return bos_up signal from transient")
        self.assertEqual(result["tag"], "bos_up")
        self.assertEqual(result["t"], 1000)

    def test_bos_down_signal_reads_from_transient(self):
        """BOSDownSignal.calculate() should read bos_down from transient_signals."""
        df = pd.DataFrame({'t': [1], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        state = MockState(transient_signals={
            "bos_down": {"tag": "bos_down", "t": 1000, "value": "bos_down", "data": {"price": 1950.0}}
        })

        bos_down_signal = BOSDownSignal()
        result = bos_down_signal.calculate(df, state)

        self.assertIsNotNone(result, "Should return bos_down signal from transient")
        self.assertEqual(result["tag"], "bos_down")
        self.assertEqual(result["t"], 1000)

    def test_bos_up_signal_returns_none_when_missing(self):
        """BOSUpSignal.calculate() should return None when bos_up not in transient."""
        df = pd.DataFrame({'t': [1], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        state = MockState(transient_signals={})

        bos_up_signal = BOSUpSignal()
        result = bos_up_signal.calculate(df, state)

        self.assertIsNone(result, "Should return None when bos_up not present")

    def test_bos_down_signal_returns_none_when_missing(self):
        """BOSDownSignal.calculate() should return None when bos_down not in transient."""
        df = pd.DataFrame({'t': [1], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        state = MockState(transient_signals={})

        bos_down_signal = BOSDownSignal()
        result = bos_down_signal.calculate(df, state)

        self.assertIsNone(result, "Should return None when bos_down not present")


class TestSignalFactoryRegistration(unittest.TestCase):
    """Test that signal_factory registers bos_up and bos_down signals."""

    def test_signal_factory_creates_bos_up_signal(self):
        """create_signal_set should include bos_up signal."""
        signal_set = create_signal_set("XAUUSD", {})

        self.assertIn("bos_up", signal_set, "bos_up should be in signal_set")
        self.assertIsInstance(signal_set["bos_up"], BOSUpSignal, "bos_up should be BOSUpSignal instance")

    def test_signal_factory_creates_bos_down_signal(self):
        """create_signal_set should include bos_down signal."""
        signal_set = create_signal_set("XAUUSD", {})

        self.assertIn("bos_down", signal_set, "bos_down should be in signal_set")
        self.assertIsInstance(signal_set["bos_down"], BOSDownSignal, "bos_down should be BOSDownSignal instance")

    def test_signal_factory_bos_signals_after_structure_processor(self):
        """bos_up/bos_down should be after structure_processor in signal_set order."""
        signal_set = create_signal_set("XAUUSD", {})

        keys = list(signal_set.keys())
        structure_idx = keys.index("structure_processor")
        bos_up_idx = keys.index("bos_up")
        bos_down_idx = keys.index("bos_down")

        self.assertGreater(bos_up_idx, structure_idx, "bos_up should be after structure_processor")
        self.assertGreater(bos_down_idx, structure_idx, "bos_down should be after structure_processor")


class TestBOSEmissionDataIntegrity(unittest.TestCase):
    """Test BOS emission data integrity."""

    def test_bos_signal_contains_required_fields(self):
        """BOS signal should contain tag, t, value, and data fields."""
        swing_points = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
        ]

        state = MockState(swing_points=swing_points)

        df = pd.DataFrame({
            't': [998, 999, 1000, 1001, 1002],
            'o': [1940, 1945, 1950, 1955, 1960],
            'h': [1955, 1960, 1965, 1970, 1975],
            'l': [1935, 1940, 1945, 1950, 1955],
            'c': [1950, 1955, 1960, 1965, 1970],
        })

        signal = StructureSignal().calculate(df, state)

        self.assertIsNotNone(signal)
        self.assertIn("tag", signal, "Signal should have tag field")
        self.assertIn("t", signal, "Signal should have t field")
        self.assertIn("value", signal, "Signal should have value field")
        self.assertIn("data", signal, "Signal should have data field")

        # Verify data contains expected fields
        data = signal.get("data", {})
        self.assertIn("price", data, "Signal data should have price")
        self.assertIn("breakout_t", data, "Signal data should have breakout_t")
        self.assertIn("pivot_t", data, "Signal data should have pivot_t")

    def test_bos_up_and_bos_down_tags_are_distinct(self):
        """BOS up and down tags should be distinct."""
        self.assertNotEqual(StructureSignal.TAG_BOS_UP, StructureSignal.TAG_BOS_DN)
        self.assertEqual(StructureSignal.TAG_BOS_UP, "bos_up")
        self.assertEqual(StructureSignal.TAG_BOS_DN, "bos_down")


if __name__ == '__main__':
    unittest.main()
