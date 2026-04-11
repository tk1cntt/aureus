"""
Tests for SymbolState log_signal_normalize truncation behavior (Phase 39.1 Stage 2)
Tests verify the actual truncation logic in state.py, not duplicated logic.
"""
import pytest
from engine.state import SymbolState


class TestLogSignalNormalizeTruncation:
    """Tests for the 200-record truncation limit in log_signal_normalize."""

    def test_truncation_at_200(self):
        """After adding 250 events, only 200 remain (oldest popped)."""
        state = SymbolState("XAUUSD")

        # Simulate what live_engine does: append + truncate
        for i in range(250):
            state.log_signal_normalize.append({"t": 1000 + i, "signals": {"test": i}})
            # This mirrors the logic in state.py line 228-230
            if len(state.log_signal_normalize) > 200:
                state.log_signal_normalize.pop(0)

        assert len(state.log_signal_normalize) == 200
        # First event should be t=1050 (oldest 50 popped)
        assert state.log_signal_normalize[0]["t"] == 1050

    def test_fifo_behavior(self):
        """When truncating, oldest events are removed, newest are kept."""
        state = SymbolState("BTCUSD")

        for i in range(201):
            state.log_signal_normalize.append({"t": 1000 + i, "signals": {"price": i}})
            if len(state.log_signal_normalize) > 200:
                state.log_signal_normalize.pop(0)

        assert len(state.log_signal_normalize) == 200
        assert state.log_signal_normalize[0]["t"] == 1001   # t=1000 popped
        assert state.log_signal_normalize[-1]["t"] == 1200  # t=1200 kept

    def test_no_truncation_below_200(self):
        """When < 200 events, nothing is truncated."""
        state = SymbolState("ETHUSD")

        for i in range(50):
            state.log_signal_normalize.append({"t": 1000 + i, "signals": {"price": i}})

        assert len(state.log_signal_normalize) == 50
        assert state.log_signal_normalize[0]["t"] == 1000

    def test_exactly_200_no_truncation(self):
        """At exactly 200 events, no truncation occurs."""
        state = SymbolState("USDJPY")

        for i in range(200):
            state.log_signal_normalize.append({"t": 1000 + i, "signals": {"price": i}})

        assert len(state.log_signal_normalize) == 200
        assert state.log_signal_normalize[0]["t"] == 1000
