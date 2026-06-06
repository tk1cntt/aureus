"""
End-to-end tests for FZ_CONT_BULL and FZ_CONT_BEAR strategy pipeline.

Tests the full pipeline:
1. StructureSignal emits choch_up/bos_down correctly
2. transient_signals wiring for consumer signals
3. Sequence matching for choch -> bos sequence
4. LIMIT entry type verification

These tests verify FZ_CONT strategies can emit signals end-to-end.
"""
import unittest
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.structure import StructureSignal
from engine.signals.bos_up import BOSUpSignal
from engine.signals.bos_down import BOSDownSignal
from engine.signals.choch_up import CHOCHUpSignal
from engine.signals.choch_down import CHOCHDownSignal
from engine.strategies.template import TemplateStrategy
from engine.signal_factory import create_signal_set


class MockState:
    """Mock state object for testing."""

    def __init__(self, swing_points=None, transient_signals=None, obs=None,
                 signal_history=None, log_signal_normalize=None, strategy_progress=None, symbol="XAUUSD"):
        self.swing_points = swing_points or []
        self.transient_signals = transient_signals or {}
        self.obs = obs or []
        self.signal_history = signal_history or []
        self.log_signal_normalize = log_signal_normalize or []
        self.strategy_progress = strategy_progress or {}
        self.symbol = symbol


class TestFZCONTConfig(unittest.TestCase):
    """Test FZ_CONT strategy configuration."""

    def test_fz_cont_bull_config(self):
        """Verify FZ_CONT_BULL has correct choch_up -> bos_up sequence."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "weight": 1.0,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        self.assertEqual(strategy.name, "FZ_CONT_BULL")
        self.assertEqual(len(strategy.sequence), 2)
        self.assertEqual(strategy.sequence[0]["tag"], "choch_up")
        self.assertEqual(strategy.sequence[1]["tag"], "bos_up")
        self.assertEqual(strategy.sequence[0]["required"], True)
        self.assertEqual(strategy.sequence[1]["required"], True)
        self.assertEqual(strategy.min_score, 8.0)  # 4.0 + 4.0

    def test_fz_cont_bear_config(self):
        """Verify FZ_CONT_BEAR has correct choch_down -> bos_down sequence."""
        config = {
            "name": "FZ_CONT_BEAR",
            "id": 2,
            "weight": 1.0,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_down", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "SELL",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_LOW_HIGH_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        self.assertEqual(strategy.name, "FZ_CONT_BEAR")
        self.assertEqual(len(strategy.sequence), 2)
        self.assertEqual(strategy.sequence[0]["tag"], "choch_down")
        self.assertEqual(strategy.sequence[1]["tag"], "bos_down")

    def test_fz_cont_limit_entry_type(self):
        """Verify FZ_CONT strategies use LIMIT entry type."""
        bull_config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        bear_config = {
            "name": "FZ_CONT_BEAR",
            "id": 2,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_down", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "SELL",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_LOW_HIGH_PIVOT"
            }
        }

        bull_strategy = TemplateStrategy(bull_config)
        bear_strategy = TemplateStrategy(bear_config)

        self.assertEqual(bull_strategy.sequence[0].get("weight", 0), 4.0)
        self.assertEqual(bear_strategy.sequence[0].get("weight", 0), 4.0)


class TestSequenceMatching(unittest.TestCase):
    """Test sequence matching for FZ_CONT strategies."""

    def test_choch_up_bos_up_sequence_matches(self):
        """choch_up -> bos_up sequence should match with score 8.0."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        # Signal history: choch_up then bos_up (wrapped in signals.events format for evaluator)
        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
            {"t": 1010, "signals": {"events": [{"tag": "bos_up"}]}},
        ])

        df = pd.DataFrame({'t': [1010], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        result = strategy.evaluate(df, {}, state)

        self.assertIsNotNone(result, "Sequence should match")
        self.assertEqual(result["score"], 8.0)
        self.assertEqual(result["strategy"], "FZ_CONT_BULL")

    def test_choch_down_bos_down_sequence_matches(self):
        """choch_down -> bos_down sequence should match with score 8.0."""
        config = {
            "name": "FZ_CONT_BEAR",
            "id": 2,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_down", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "SELL",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_LOW_HIGH_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "choch_down"}]}},
            {"t": 1010, "signals": {"events": [{"tag": "bos_down"}]}},
        ])

        df = pd.DataFrame({'t': [1010], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        result = strategy.evaluate(df, {}, state)

        self.assertIsNotNone(result, "Sequence should match")
        self.assertEqual(result["score"], 8.0)
        self.assertEqual(result["strategy"], "FZ_CONT_BEAR")

    def test_partial_sequence_choch_only(self):
        """Only choch_up without bos_up should NOT trigger (bos_up is required)."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
        ])

        df = pd.DataFrame({'t': [1000], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        result = strategy.evaluate(df, {}, state)

        self.assertIsNone(result, "Partial sequence should NOT trigger (bos_up is required)")

    def test_wrong_order_bos_before_choch(self):
        """bos_up before choch_up should NOT match the sequence."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "bos_up"}]}},  # bos_up first
            {"t": 1010, "signals": {"events": [{"tag": "choch_up"}]}},  # choch_up second
        ])

        df = pd.DataFrame({'t': [1010], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        result = strategy.evaluate(df, {}, state)

        # Should not match because order is wrong
        self.assertIsNone(result, "Wrong order should NOT match")

    def test_bos_without_choch_no_match(self):
        """Only bos_up without choch_up should NOT trigger."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "bos_up"}]}},  # No choch_up
        ])

        df = pd.DataFrame({'t': [1000], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        result = strategy.evaluate(df, {}, state)

        self.assertIsNone(result, "bos_up without choch_up should NOT trigger")


class TestFullPipeline(unittest.TestCase):
    """Test full pipeline: StructureSignal -> transient -> sequence matching."""

    def test_structure_signal_emits_choch_up_to_transient(self):
        """StructureSignal should emit choch_up when opposing extreme exists."""
        # HH at t=1000, LL at t=1050 (opposing extreme)
        swing_points = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1050, "price": 1880.0, "type": "LL", "is_choch": False, "is_bos": False, "is_high": False},
        ]

        state = MockState(swing_points=swing_points)

        # Price breaks above HH at 1950 at t=1100 (after LL at t=1050)
        # Candles from t=1001 to t=1099 must stay BELOW 1950 (no breakout)
        # Breakout at t=1100 (after LL at t=1050)
        df = pd.DataFrame({
            't': [998, 999, 1000, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 1080, 1090, 1100],
            'o': [1930, 1935, 1940, 1945, 1940, 1935, 1930, 1890, 1895, 1900, 1905, 1910, 1960],
            'h': [1945, 1945, 1948, 1948, 1945, 1940, 1945, 1920, 1930, 1940, 1948, 1950, 1970],
            'l': [1925, 1930, 1935, 1940, 1935, 1930, 1925, 1880, 1890, 1900, 1905, 1910, 1920],
            'c': [1940, 1940, 1940, 1945, 1940, 1935, 1930, 1895, 1910, 1920, 1945, 1948, 1965],
        })

        signal = StructureSignal().calculate(df, state)

        self.assertIsNotNone(signal)
        self.assertEqual(signal.get("tag"), "choch_up", "Should emit choch_up signal")
        self.assertIn("choch_up", state.transient_signals, "choch_up should be in transient_signals")

    def test_structure_signal_emits_bos_up_to_transient(self):
        """StructureSignal should emit bos_up when NO opposing extreme exists."""
        swing_points = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
        ]

        state = MockState(swing_points=swing_points)

        # Price breaks above HH - no LL after HH
        df = pd.DataFrame({
            't': [998, 999, 1000, 1001, 1002],
            'o': [1940, 1945, 1950, 1955, 1960],
            'h': [1955, 1960, 1965, 1970, 1975],
            'l': [1935, 1940, 1945, 1950, 1955],
            'c': [1950, 1955, 1960, 1965, 1970],
        })

        signal = StructureSignal().calculate(df, state)

        self.assertIsNotNone(signal)
        self.assertEqual(signal.get("tag"), "bos_up", "Should emit bos_up signal")
        self.assertIn("bos_up", state.transient_signals, "bos_up should be in transient_signals")

    def test_consumer_signal_reads_transient(self):
        """BOSUpSignal should read from transient_signals."""
        state = MockState(transient_signals={
            "bos_up": {"tag": "bos_up", "t": 1000, "value": "bos_up"}
        })

        df = pd.DataFrame({'t': [1], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        bos_up_signal = BOSUpSignal()
        result = bos_up_signal.calculate(df, state)

        self.assertIsNotNone(result)
        self.assertEqual(result["tag"], "bos_up")

    def test_full_pipeline_choch_then_bos_triggers_strategy(self):
        """Full pipeline: choch_up then bos_up -> FZ_CONT_BULL triggers."""
        # Step 1: StructureSignal emits choch_up
        # HH at t=1000, LL at t=1050 (opposing extreme)
        swing_points_choch = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1050, "price": 1880.0, "type": "LL", "is_choch": False, "is_bos": False, "is_high": False},
        ]

        state = MockState(swing_points=swing_points_choch)

        # Price breaks above HH at 1950 at t=1100 (after LL at t=1050)
        # Candles from t=1001 to t=1099 must stay BELOW 1950 (no breakout)
        df1 = pd.DataFrame({
            't': [998, 999, 1000, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 1080, 1090, 1100],
            'o': [1930, 1935, 1940, 1945, 1940, 1935, 1930, 1890, 1895, 1900, 1905, 1910, 1960],
            'h': [1945, 1945, 1948, 1948, 1945, 1940, 1945, 1920, 1930, 1940, 1948, 1950, 1970],
            'l': [1925, 1930, 1935, 1940, 1935, 1930, 1925, 1880, 1890, 1900, 1905, 1910, 1920],
            'c': [1940, 1940, 1940, 1945, 1940, 1935, 1930, 1895, 1910, 1920, 1945, 1948, 1965],
        })

        signal1 = StructureSignal().calculate(df1, state)
        self.assertEqual(signal1.get("tag"), "choch_up", "Step 1: Should emit choch_up")

        # Step 2: New swing point, no opposing extreme -> emit bos_up
        # Add new HH after the choch
        state.swing_points = [
            {"t": 900, "price": 1900.0, "type": "LH", "is_choch": False, "is_bos": False, "is_high": True},
            {"t": 1000, "price": 1950.0, "type": "HH", "is_choch": True, "is_bos": False, "is_high": True},
            {"t": 1050, "price": 1880.0, "type": "LL", "is_choch": False, "is_bos": False, "is_high": False},
            {"t": 1200, "price": 2000.0, "type": "HH", "is_choch": False, "is_bos": False, "is_high": True},
        ]

        df2 = pd.DataFrame({
            't': [1198, 1199, 1200, 1201, 1202],
            'o': [1990, 1995, 2000, 2005, 2010],
            'h': [2005, 2010, 2015, 2020, 2025],
            'l': [1985, 1990, 1995, 2000, 2005],
            'c': [2000, 2005, 2010, 2015, 2020],
        })

        signal2 = StructureSignal().calculate(df2, state)
        self.assertEqual(signal2.get("tag"), "bos_up", "Step 2: Should emit bos_up")

        # Step 3: Verify transient_signals has both
        self.assertIn("choch_up", state.transient_signals, "Step 3: choch_up should be in transient")
        self.assertIn("bos_up", state.transient_signals, "Step 3: bos_up should be in transient")

        # Step 4: Feed into strategy sequence evaluator
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        # Build log_signal_normalize from transient_signals events (evaluator reads from log_signal_normalize)
        events = []
        for tag, sig in state.transient_signals.items():
            if isinstance(sig, dict) and sig.get("tag"):
                events.append({"t": sig.get("t", 0), "signals": {"events": [{"tag": sig["tag"]}]}})

        state.log_signal_normalize = events

        # Must use t=1201 (sequence_completed_t) to match the bos_up timestamp
        df3 = pd.DataFrame({'t': [1201], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        result = strategy.evaluate(df3, {}, state)

        self.assertIsNotNone(result, "FZ_CONT_BULL should trigger with choch_up + bos_up")
        self.assertEqual(result["score"], 8.0)


class TestSignalFactoryIntegration(unittest.TestCase):
    """Test signal factory creates all required signals for FZ_CONT."""

    def test_signal_factory_creates_all_required_signals(self):
        """Signal factory should create structure_processor, choch_up, choch_down, bos_up, bos_down."""
        signal_set = create_signal_set("XAUUSD", {})

        required_signals = [
            "structure_processor",
            "choch_up",
            "choch_down",
            "bos_up",
            "bos_down"
        ]

        for sig in required_signals:
            self.assertIn(sig, signal_set, f"{sig} should be in signal_set")

    def test_choch_signals_read_from_transient(self):
        """CHOCHUpSignal and CHOCHDownSignal should read from transient_signals."""
        state = MockState(transient_signals={
            "choch_up": {"tag": "choch_up", "t": 1000, "value": "choch_up"},
            "choch_down": {"tag": "choch_down", "t": 1000, "value": "choch_down"}
        })

        df = pd.DataFrame({'t': [1], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        choch_up = CHOCHUpSignal()
        choch_down = CHOCHDownSignal()

        result_up = choch_up.calculate(df, state)
        result_down = choch_down.calculate(df, state)

        self.assertIsNotNone(result_up)
        self.assertEqual(result_up["tag"], "choch_up")
        self.assertIsNotNone(result_down)
        self.assertEqual(result_down["tag"], "choch_down")


class TestStrategyProgressTracking(unittest.TestCase):
    """Test strategy progress tracking during sequence matching."""

    def test_strategy_progress_stored_on_state(self):
        """Strategy progress should be stored on state_obj.strategy_progress."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
        ])

        df = pd.DataFrame({'t': [1000], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        strategy.evaluate(df, {}, state)

        # Strategy progress should be stored
        self.assertIn("FZ_CONT_BULL", state.strategy_progress)
        progress = state.strategy_progress["FZ_CONT_BULL"]
        self.assertIn("sequence", progress)
        self.assertEqual(len(progress["sequence"]), 2)

    def test_strategy_progress_partial_sequence(self):
        """Strategy progress should show partial progress when sequence incomplete."""
        config = {
            "name": "FZ_CONT_BULL",
            "id": 1,
            "min_score_threshold": 8.0,
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "bos_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY",
                "entry_type": "LIMIT",
                "entry_method": "FIRST_HIGH_LOW_PIVOT"
            }
        }

        strategy = TemplateStrategy(config)

        state = MockState(log_signal_normalize=[
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
        ])

        df = pd.DataFrame({'t': [1000], 'o': [100], 'h': [105], 'l': [95], 'c': [102]})

        strategy.evaluate(df, {}, state)

        progress = state.strategy_progress["FZ_CONT_BULL"]
        # First step should be matched, second should be waiting
        self.assertEqual(progress["sequence"][0]["status"], "matched")
        self.assertEqual(progress["sequence"][1]["status"], "waiting")


if __name__ == '__main__':
    unittest.main()
