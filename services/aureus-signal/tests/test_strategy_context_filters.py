"""Unit tests for TemplateStrategy context_filters (Pillar 1).

Tests each filter type (trend_alignment, session_active, ob_imbalance,
ema_alignment) in isolation, then verifies per-strategy filter composition
for TREND_CONT, SESSION_SWEEP, and ORDER_FLOW_DOM.

No DB, no Redis — pure unit tests.
"""
import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.strategies.template import TemplateStrategy


# ---------------------------------------------------------------------------
# Seed strategy configs (copied from seed_strategies.py — kept in sync
# manually; see services/aureus-signal/engine/strategies/seed_strategies.py)
# ---------------------------------------------------------------------------

TREND_CONT_CONFIG = {
    "name": "TREND_CONT",
    "id": 1,
    "min_score_threshold": 6.5,
    "context_filters": [
        {"type": "trend_alignment", "required_trend": "BULLISH"},
        {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]},
        {"type": "ema_alignment", "required_slope": "POSITIVE", "period": 21},
    ],
    "sequence": [
        {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
        {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 15, "reset_signals": ["choch_down"]},
        {"tag": "fvg_bull", "weight": 2.0, "required": False, "max_wait": 10},
    ],
    "trade_execution": {
        "size": 2.0,
        "sl": {"type": "FIXED_PIPS", "value": 15},
        "tp": {"type": "RR_RATIO", "value": 3.0},
    },
}

SESSION_SWEEP_CONFIG = {
    "name": "SESSION_SWEEP",
    "id": 2,
    "min_score_threshold": 6.0,
    "context_filters": [
        {"type": "trend_alignment", "required_trend": "BULLISH"},
        {"type": "session_active", "allowed": ["LONDON", "NEW_YORK"]},
    ],
    "sequence": [
        {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
        {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]},
    ],
    "trade_execution": {
        "size": 1.5,
        "sl": {"type": "FIXED_PIPS", "value": 10},
        "tp": {"type": "RR_RATIO", "value": 2.5},
    },
}

ORDER_FLOW_DOM_CONFIG = {
    "name": "ORDER_FLOW_DOM",
    "id": 3,
    "min_score_threshold": 7.0,
    "context_filters": [
        {"type": "trend_alignment", "required_trend": "BULLISH"},
        {"type": "ob_imbalance", "min_ratio": 3.0, "lookback": 10},
        {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]},
    ],
    "sequence": [
        {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
    ],
    "trade_execution": {
        "size": 3.0,
        "sl": {"type": "FIXED_PIPS", "value": 12},
        "tp": {"type": "RR_RATIO", "value": 4.0},
    },
}


# ---------------------------------------------------------------------------
# Minimal mock state — only the fields _evaluate_context reads
# ---------------------------------------------------------------------------

class MockState:
    def __init__(self):
        self.htf_trend = "NEUTRAL"
        self.current_session = "OFF_MARKET"
        self.obs = []
        self.emas = {}
        self.signal_history = []
        self.strategy_progress = {}


# ===========================  TREND_CONT  ===========================

class TestTrendContContextFilters(unittest.TestCase):
    """Context filter tests for TREND_CONT strategy."""

    def setUp(self):
        self.strat = TemplateStrategy(TREND_CONT_CONFIG)

    # --- trend_alignment ---

    def test_trend_bullish_passes(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])
        self.assertEqual(ctx["failed_filters"], [])

    def test_trend_bearish_fails(self):
        state = MockState()
        state.htf_trend = "BEARISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])
        self.assertIn("trend_alignment:BULLISH", ctx["failed_filters"])

    def test_trend_neutral_fails(self):
        state = MockState()
        state.htf_trend = "NEUTRAL"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])

    # --- session_active ---

    def test_session_london_passes(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_session_new_york_passes(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "NEW_YORK"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_session_overlap_passes(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON_NY_OVERLAP"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_session_asia_fails(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "ASIA"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])
        self.assertIn("session_active:ASIA", ctx["failed_filters"])

    def test_session_off_market_fails(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "OFF_MARKET"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])

    # --- ema_alignment ---

    def test_ema_positive_slope_passes(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_ema_negative_slope_fails(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": -0.3}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])
        self.assertIn("ema_alignment:period=21", ctx["failed_filters"])

    def test_ema_zero_slope_fails(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])

    def test_ema_missing_period_fails(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {}  # no EMA data
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])

    # --- combined ---

    def test_all_filters_pass(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])
        self.assertEqual(ctx["failed_filters"], [])
        self.assertEqual(len(ctx["details"]), 3)

    def test_one_filter_fails_rejects_all(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "ASIA"  # fail session
        state.emas = {21: {"slope": 0.5}}
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])
        self.assertEqual(len(ctx["failed_filters"]), 1)

    def test_multiple_filters_fail(self):
        state = MockState()
        state.htf_trend = "BEARISH"  # fail
        state.current_session = "ASIA"  # fail
        state.emas = {21: {"slope": -0.1}}  # fail
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])
        self.assertEqual(len(ctx["failed_filters"]), 3)


# ===========================  SESSION_SWEEP  ===========================

class TestSessionSweepContextFilters(unittest.TestCase):
    """Context filter tests for SESSION_SWEEP strategy."""

    def setUp(self):
        self.strat = TemplateStrategy(SESSION_SWEEP_CONFIG)

    def test_trend_and_session_pass(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_new_york_passes(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "NEW_YORK"
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_overlap_not_allowed(self):
        """SESSION_SWEEP only allows LONDON and NEW_YORK — NOT overlap."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON_NY_OVERLAP"
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])

    def test_no_ema_filter(self):
        """SESSION_SWEEP has no ema_alignment filter — only 2 filters checked."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])
        # Only 2 detail entries (trend + session) — no EMA
        self.assertEqual(len(ctx["details"]), 2)

    def test_trend_bearish_fails(self):
        state = MockState()
        state.htf_trend = "BEARISH"
        state.current_session = "LONDON"
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])


# =======================  ORDER_FLOW_DOM  =======================

class TestOrderFlowDomContextFilters(unittest.TestCase):
    """Context filter tests for ORDER_FLOW_DOM strategy."""

    def setUp(self):
        self.strat = TemplateStrategy(ORDER_FLOW_DOM_CONFIG)

    def _make_obs(self, bull_count, bear_count):
        obs = []
        for _ in range(bull_count):
            obs.append({"ob_type": "BULLISH", "top": 100, "bottom": 99, "t_start": 1})
        for _ in range(bear_count):
            obs.append({"ob_type": "BEARISH", "top": 100, "bottom": 99, "t_start": 1})
        return obs

    def test_ob_imbalance_sufficient(self):
        """4 BULL + 1 BEAR → ratio=4.0 ≥ 3.0 → passes."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = self._make_obs(4, 1)
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_ob_imbalance_exactly_at_threshold(self):
        """3 BULL + 1 BEAR → ratio=3.0 ≥ 3.0 → passes."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = self._make_obs(3, 1)
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_ob_imbalance_insufficient(self):
        """2 BULL + 1 BEAR → ratio=2.0 < 3.0 → fails."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = self._make_obs(2, 1)
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])
        self.assertTrue(any("ob_imbalance" in f for f in ctx["failed_filters"]))

    def test_no_obs_fails(self):
        """Empty obs → ratio=0.0 → fails."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        ctx = self.strat._evaluate_context(state)
        self.assertFalse(ctx["passed"])

    def test_all_bullish_obs_passes(self):
        """5 BULL + 0 BEAR → ratio=5.0 ≥ 3.0 → passes."""
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = self._make_obs(5, 0)
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])

    def test_all_filters_pass(self):
        state = MockState()
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = self._make_obs(4, 1)
        ctx = self.strat._evaluate_context(state)
        self.assertTrue(ctx["passed"])
        self.assertEqual(len(ctx["details"]), 3)  # trend + ob_imbalance + session


if __name__ == "__main__":
    unittest.main()
