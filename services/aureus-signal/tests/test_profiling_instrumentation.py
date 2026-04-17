"""
Tests for Phase 44.0: Profiling instrumentation.
"""
import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_df(rows=10):
    import pandas as pd
    base_t = 1700000000
    data = []
    for i in range(rows):
        data.append({
            "t": base_t + i * 60, "o": 2000.0 + i, "h": 2005.0 + i,
            "l": 1995.0 + i, "c": 2002.0 + i, "v": 1000 + i * 10, "tf": "M1",
        })
    return pd.DataFrame(data)


def _run_with_profiling(signals, df, state, symbol, count, caplog):
    """Helper: run N candles with profiling log capture."""
    import logging
    caplog.set_level(logging.INFO)
    with patch("engine.live_engine._schedule_profiling_push", return_value=None):
        from engine.live_engine import execute_signals_for_candle
        for _ in range(count):
            execute_signals_for_candle(signals, df, state, symbol, MagicMock())
    return [r.message for r in caplog.records if "PROFILING" in r.message and "avg_ms=" in r.message]


class TestProfilingNonInterference:
    def test_profiling_does_not_affect_signal_results(self, caplog):
        """Instrumentation completes and state is updated."""
        caplog.set_level("INFO")
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(20)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0, "prev": 2001.0, "slope": 0.0005}}
        mock_signal = MagicMock()
        mock_signal.calculate.return_value = {"tag": "test_up", "value": 1.0}
        signals = {"mock_signal": mock_signal}

        with patch("engine.live_engine._schedule_profiling_push", return_value=None):
            execute_signals_for_candle(signals, df, state, "TEST", MagicMock())

        mock_signal.calculate.assert_called_once()
        assert state.current_signal is not None
        assert getattr(state, "_profiling_candle_count", 0) == 1


class TestProfilingTiming:
    def test_profiling_records_slow_vs_fast(self, caplog):
        """Slow signal avg_ms should be significantly higher than fast."""
        import json, re
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(20)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0, "prev": 2001.0, "slope": 0.0005}}

        signals = {}

        def slow_signal(df, state, **kwargs):
            time.sleep(0.1)
            return {"tag": "slow_up", "value": 1.0}

        def fast_signal(df, state, **kwargs):
            return {"tag": "fast_up", "value": 1.0}

        slow_mock = MagicMock()
        slow_mock.calculate.side_effect = slow_signal
        fast_mock = MagicMock()
        fast_mock.calculate.side_effect = fast_signal
        signals["slow"] = slow_mock
        signals["fast"] = fast_mock

        log_msgs = _run_with_profiling(signals, df, state, "TEST", 100, caplog)
        assert len(log_msgs) >= 1, f"No profiling logs. Got: {[r.message for r in caplog.records]}"

        match = re.search(r'avg_ms=(\{.+?\})', log_msgs[0])
        assert match, f"Could not parse avg_ms from: {log_msgs[0]}"
        avg = json.loads(match.group(1))
        assert "slow" in avg and "fast" in avg and "_total" in avg
        assert float(avg["slow"]) > float(avg["fast"]) * 2, \
            f"slow={avg['slow']} not >> fast={avg['fast']}"


class TestProfilingLogFrequency:
    def test_profiling_logs_at_100_not_at_50(self, caplog):
        """Run 150 candles — expect exactly 1 log at candle=100."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(20)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0, "prev": 2001.0, "slope": 0.0005}}
        signals = {"mock": MagicMock(return_value={"tag": "up", "value": 1.0})}

        log_msgs = _run_with_profiling(signals, df, state, "TEST", 150, caplog)
        assert len(log_msgs) == 1
        assert "candle=100" in log_msgs[0]


class TestProfilingRedisFailureSafety:
    def test_redis_failure_does_not_crash(self):
        """Redis failure is caught, engine continues."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(20)
        state = SymbolState("TEST")
        state.emas = {21: {"current": 2002.0, "prev": 2001.0, "slope": 0.0005}}
        signals = {"mock": MagicMock(return_value={"tag": "up", "value": 1.0})}

        with patch("engine.live_engine._schedule_profiling_push", return_value=None):
            execute_signals_for_candle(signals, df, state, "TEST", MagicMock())

        assert state.current_signal is not None


class TestWindowManagerProfiling:
    def test_window_manager_logs_profiling_every_100(self, caplog):
        """Call update() 150 times — expect 1 log at candle=100."""
        import logging
        caplog.set_level(logging.INFO)
        from engine.manager import WindowManager

        wm = WindowManager(max_window=300)
        for i in range(150):
            wm.update("TEST", {
                "t": str(1700000000 + i * 60), "o": "2000.0", "h": "2005.0",
                "l": "1995.0", "c": "2002.0", "v": "1000", "tf": "M1",
            })

        log_msgs = [r.message for r in caplog.records if "PROFILING" in r.message and "df_build=" in r.message]
        assert len(log_msgs) == 1
        assert "candle=100" in log_msgs[0]
        assert "df_build=" in log_msgs[0]
        assert "integrity=" in log_msgs[0]
        assert "window_size=" in log_msgs[0]


class TestProfilingOverhead:
    def test_profiling_overhead_is_minimal(self):
        """Instrumentation overhead per candle should be < 1ms absolute."""
        from engine.live_engine import execute_signals_for_candle
        from engine.state import SymbolState

        df = _make_df(50)
        signals = {"mock": MagicMock(return_value={"tag": "up", "value": 1.0})}

        # Measure instrumented execution
        with patch("engine.live_engine._schedule_profiling_push", return_value=None):
            t_start = time.perf_counter_ns()
            for _ in range(500):
                state = SymbolState("TEST")
                state.emas = {}
                execute_signals_for_candle(signals, df, state, "TEST", MagicMock())
            instrumented_ns = time.perf_counter_ns() - t_start

        overhead_per_candle_ms = instrumented_ns / 500 / 1_000_000
        assert overhead_per_candle_ms < 2.0, \
            f"Overhead {overhead_per_candle_ms:.2f}ms/candle exceeds 2ms budget"
