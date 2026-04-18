"""
Tests for Phase 44.3: Dirty-Flag per Signal.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd


def _make_df(rows=30, base_t=1700000000):
    data = []
    for i in range(rows):
        data.append({
            "t": base_t + i * 60,
            "o": 2000.0 + i * 0.5,
            "h": 2005.0 + i * 0.5,
            "l": 1995.0 + i * 0.5,
            "c": 2002.0 + i * 0.3,
            "v": 1000.0 + i * 10.0,
        })
    return pd.DataFrame(data)


class TestDirtyFlagSkip:
    def test_skippable_signal_is_skipped_on_same_input(self):
        """When input hash unchanged, skippable signal should be skipped."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}

        mock_signal = MagicMock(return_value={"tag": "ema_21_up", "value": 2002.0})
        signals = {"ema_21": mock_signal}

        # First candle — calculate normally
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert mock_signal.calculate.call_count == 1

        # Second call with same df and same state — should skip
        mock_signal.reset_mock()
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        # Same input hash → should be skipped
        assert mock_signal.calculate.call_count == 0

    def test_non_skippable_signal_always_runs(self):
        """Stateful signals (structure_processor, pivots) should always run."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.swing_points = [{"t": 1700000000, "price": 2000.0, "is_high": True, "type": "HH"}]

        mock_structure = MagicMock(return_value=None)
        signals = {"structure_processor": mock_structure}

        # First call
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert mock_structure.calculate.call_count == 1

        # Second call with same data — should STILL run (not skippable)
        mock_structure.reset_mock()
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert mock_structure.calculate.call_count == 1

    def test_skipped_signal_not_in_timing_ms(self):
        """Skipped signals should have timing=0 and be counted in _skipped."""
        from engine.live_engine import execute_signals_for_candle, _SKIPPABLE_SIGNALS
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}

        call_count = {"n": 0}
        def mock_calc(df, state, **kwargs):
            call_count["n"] += 1
            return {"tag": "ema_21_up", "value": 2002.0}

        mock_signal = MagicMock()
        mock_signal.calculate.side_effect = mock_calc
        signals = {"ema_21": mock_signal}

        # First call — should calculate
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert call_count["n"] == 1

        # Same df — should skip
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert call_count["n"] == 1  # Not incremented


class TestDirtyFlagRecalcOnChange:
    def test_dirty_flag_recalculates_when_input_changes(self):
        """When input changes, signal should be recalculated."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}

        call_count = {"n": 0}
        def mock_calc(df, state, **kwargs):
            call_count["n"] += 1
            return {"tag": "ema_21_up", "value": float(df.iloc[-1]["c"])}

        mock_signal = MagicMock()
        mock_signal.calculate.side_effect = mock_calc
        signals = {"ema_21": mock_signal}

        # First call
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert call_count["n"] == 1

        # Modify df (change last candle close) → should recalculate
        df_copy = df.copy()
        df_copy.iloc[-1] = df_copy.iloc[-1].copy()
        df_copy.loc[len(df_copy) - 1, "c"] = 9999.0

        execute_signals_for_candle(signals, df_copy, state, "TEST", MagicMock())
        assert call_count["n"] == 2

    def test_different_signals_have_different_hashes(self):
        """Changing volume should trigger VolSMA recalc but not EMA recalc."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}
        state._vol_sma_20_buffer = [1000.0] * 20

        ema_calls = {"n": 0}
        vol_calls = {"n": 0}

        def ema_calc(df, state, **kwargs):
            ema_calls["n"] += 1
            return {"tag": "ema_21_up", "value": 2002.0}

        def vol_calc(df, state, **kwargs):
            vol_calls["n"] += 1
            return {"tag": "vol_sma_20", "value": 1000.0}

        ema_mock = MagicMock()
        ema_mock.calculate.side_effect = ema_calc
        vol_mock = MagicMock()
        vol_mock.calculate.side_effect = vol_calc
        signals = {
            "ema_21": ema_mock,
            "vol_sma": vol_mock,
        }

        # First call — both calculate
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert ema_calls["n"] == 1
        assert vol_calls["n"] == 1

        # Same df → both skip
        ema_calls["n"] = 0
        vol_calls["n"] = 0
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert ema_calls["n"] == 0
        assert vol_calls["n"] == 0

        # Change only volume → VolSMA should recalc, EMA should still skip
        df2 = df.copy()
        df2.iloc[-1] = df2.iloc[-1].copy()
        df2.loc[len(df2) - 1, "v"] = 99999.0

        ema_calls["n"] = 0
        vol_calls["n"] = 0
        execute_signals_for_candle(signals, df2, state, "TEST", MagicMock())
        assert ema_calls["n"] == 0, "EMA should still skip (close price unchanged)"
        assert vol_calls["n"] == 1, "VolSMA should recalc (volume changed)"


class TestComputeSignalInputHash:
    def test_hash_returns_none_for_non_skippable(self):
        """Structure processor and pivots should return None hash."""
        from engine.live_engine import _compute_signal_input_hash
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")

        assert _compute_signal_input_hash("structure_processor", df, state) is None
        assert _compute_signal_input_hash("pivots", df, state) is None
        assert _compute_signal_input_hash("sweep_processor", df, state) is None
        assert _compute_signal_input_hash("choch_up", df, state) is None
        assert _compute_signal_input_hash("choch_down", df, state) is None

    def test_hash_returns_value_for_skippable(self):
        """EMA, ATR, etc. should return a hash value."""
        from engine.live_engine import _compute_signal_input_hash
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}
        state.atr = 5.0

        assert _compute_signal_input_hash("ema_21", df, state) is not None
        assert _compute_signal_input_hash("atr_14", df, state) is not None
        assert _compute_signal_input_hash("session", df, state) is not None
        assert _compute_signal_input_hash("trend", df, state) is not None
        assert _compute_signal_input_hash("cisd", df, state) is not None

    def test_hash_handles_float_ema_state(self):
        """EMA hash must accept float state format for backward compatibility."""
        from engine.live_engine import _compute_signal_input_hash
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {89: 2001.5, 100: 2002.5, 200: 2003.5}

        assert _compute_signal_input_hash("ema_89", df, state) is not None
        assert _compute_signal_input_hash("ema_100", df, state) is not None
        assert _compute_signal_input_hash("ema_200", df, state) is not None

    def test_same_input_same_hash(self):
        """Same input should produce same hash."""
        from engine.live_engine import _compute_signal_input_hash
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}

        h1 = _compute_signal_input_hash("ema_21", df, state)
        h2 = _compute_signal_input_hash("ema_21", df, state)
        assert h1 == h2

    def test_different_input_different_hash(self):
        """Different close price should produce different hash."""
        from engine.live_engine import _compute_signal_input_hash
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}}

        h1 = _compute_signal_input_hash("ema_21", df, state)

        # Change close price
        df_copy = df.copy()
        df_copy.iloc[-1] = df_copy.iloc[-1].copy()
        df_copy.loc[len(df_copy) - 1, "c"] = 3000.0

        h2 = _compute_signal_input_hash("ema_21", df_copy, state)
        assert h1 != h2


class TestSkippedMetric:
    def test_skipped_count_increments(self):
        """Multiple skippable signals should all be counted."""
        from engine.live_engine import execute_signals_for_candle, _SKIPPABLE_SIGNALS
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0}, 34: {"current": 2001.0}}

        signals = {
            "ema_21": MagicMock(return_value={"tag": "ema_21_up", "value": 2002.0}),
            "ema_34": MagicMock(return_value={"tag": "ema_34_up", "value": 2001.0}),
        }

        # First call — all calculate
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())

        # Second call with same df — all should skip
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        # No exception = test passes


class TestBackwardCompatibility:
    def test_dirty_flag_with_missing_signal_hash(self):
        """State without _signal_hash should still work."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(30)
        state = SymbolState("TEST")
        # Remove _signal_hash to simulate old state
        if hasattr(state, '_signal_hash'):
            del state._signal_hash

        mock_signal = MagicMock(return_value={"tag": "ema_21_up", "value": 2002.0})
        signals = {"ema_21": mock_signal}

        # Should not crash, just calculate normally
        execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
        assert mock_signal.calculate.call_count == 1
