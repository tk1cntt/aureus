"""Tests for CISD Consensus context filter — reads transient_signals directly from CISDMultiTFSignal."""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.strategies.template import TemplateStrategy


class _State:
    """Minimal state object for testing."""
    def __init__(self):
        self.symbol = "EURUSD"
        self.transient_signals = {}


class TestCISDConsensusContextFilter:
    """Test TemplateStrategy context filter type 'cisd_consensus'."""

    def test_passes_when_all_tf_match_bullish(self):
        """M5+M15+M30 all bullish → consensus passes."""
        state = _State()
        state.transient_signals = {
            "cisd_m5_bullish": {"tf": "M5", "status": "bullish", "category": "cisd_mtf"},
            "cisd_m15_bullish": {"tf": "M15", "status": "bullish", "category": "cisd_mtf"},
            "cisd_m30_bullish": {"tf": "M30", "status": "bullish", "category": "cisd_mtf"},
        }

        config = {
            "id": 99,
            "name": "TEST_CISD_CONSENSUS_BULL",
            "context_filters": [
                {
                    "type": "cisd_consensus",
                    "required_direction": "bullish",
                    "required_tfs": ["m30", "m15", "m5"],
                }
            ],
            "sequence": [{"tag": "cisd_bull", "weight": 4.0, "required": True, "max_wait": 20}],
            "trade_execution": {"direction": "BUY", "size": 0.01},
        }
        strategy = TemplateStrategy(config)
        ctx = strategy._evaluate_context(state)

        assert ctx["passed"] is True
        assert len(ctx["failed_filters"]) == 0

    def test_passes_when_all_tf_match_bearish(self):
        """M5+M15+M30 all bearish → consensus passes for bearish."""
        state = _State()
        state.transient_signals = {
            "cisd_m5_bearish": {"tf": "M5", "status": "bearish", "category": "cisd_mtf"},
            "cisd_m15_bearish": {"tf": "M15", "status": "bearish", "category": "cisd_mtf"},
            "cisd_m30_bearish": {"tf": "M30", "status": "bearish", "category": "cisd_mtf"},
        }

        config = {
            "id": 99,
            "name": "TEST_CISD_CONSENSUS_BEAR",
            "context_filters": [
                {
                    "type": "cisd_consensus",
                    "required_direction": "bearish",
                    "required_tfs": ["m30", "m15", "m5"],
                }
            ],
            "sequence": [{"tag": "cisd_bear", "weight": 4.0, "required": True, "max_wait": 20}],
            "trade_execution": {"direction": "SELL", "size": 0.01},
        }
        strategy = TemplateStrategy(config)
        ctx = strategy._evaluate_context(state)

        assert ctx["passed"] is True

    def test_fails_when_one_tf_missing(self):
        """M30 missing → consensus fails."""
        state = _State()
        state.transient_signals = {
            "cisd_m5_bullish": {"tf": "M5", "status": "bullish", "category": "cisd_mtf"},
            "cisd_m15_bullish": {"tf": "M15", "status": "bullish", "category": "cisd_mtf"},
            # m30 missing
        }

        config = {
            "id": 99,
            "name": "TEST",
            "context_filters": [
                {
                    "type": "cisd_consensus",
                    "required_direction": "bullish",
                    "required_tfs": ["m30", "m15", "m5"],
                }
            ],
            "sequence": [{"tag": "cisd_bull", "weight": 4.0, "required": True}],
            "trade_execution": {"direction": "BUY", "size": 0.01},
        }
        strategy = TemplateStrategy(config)
        ctx = strategy._evaluate_context(state)

        assert ctx["passed"] is False
        assert "cisd_consensus:bullish" in ctx["failed_filters"]

    def test_fails_when_direction_mismatch(self):
        """M30 bearish while M5/M15 bullish → consensus fails for bullish."""
        state = _State()
        state.transient_signals = {
            "cisd_m5_bullish": {"tf": "M5", "status": "bullish", "category": "cisd_mtf"},
            "cisd_m15_bullish": {"tf": "M15", "status": "bullish", "category": "cisd_mtf"},
            "cisd_m30_bearish": {"tf": "M30", "status": "bearish", "category": "cisd_mtf"},
        }

        config = {
            "id": 99,
            "name": "TEST",
            "context_filters": [
                {
                    "type": "cisd_consensus",
                    "required_direction": "bullish",
                    "required_tfs": ["m30", "m15", "m5"],
                }
            ],
            "sequence": [{"tag": "cisd_bull", "weight": 4.0, "required": True}],
            "trade_execution": {"direction": "BUY", "size": 0.01},
        }
        strategy = TemplateStrategy(config)
        ctx = strategy._evaluate_context(state)

        assert ctx["passed"] is False

    def test_fails_when_empty_transient_signals(self):
        """No transient signals → consensus fails."""
        state = _State()

        config = {
            "id": 99,
            "name": "TEST",
            "context_filters": [
                {
                    "type": "cisd_consensus",
                    "required_direction": "bullish",
                    "required_tfs": ["m30", "m15", "m5"],
                }
            ],
            "sequence": [{"tag": "cisd_bull", "weight": 4.0, "required": True}],
            "trade_execution": {"direction": "BUY", "size": 0.01},
        }
        strategy = TemplateStrategy(config)
        ctx = strategy._evaluate_context(state)

        assert ctx["passed"] is False

    def test_fails_when_no_transient_signals_attr(self):
        """State without transient_signals → consensus fails."""
        class MinimalState:
            symbol = "EURUSD"

        config = {
            "id": 99,
            "name": "TEST",
            "context_filters": [
                {
                    "type": "cisd_consensus",
                    "required_direction": "bullish",
                    "required_tfs": ["m30", "m15", "m5"],
                }
            ],
            "sequence": [{"tag": "cisd_bull", "weight": 4.0, "required": True}],
            "trade_execution": {"direction": "BUY", "size": 0.01},
        }
        strategy = TemplateStrategy(config)
        ctx = strategy._evaluate_context(MinimalState())

        assert ctx["passed"] is False
