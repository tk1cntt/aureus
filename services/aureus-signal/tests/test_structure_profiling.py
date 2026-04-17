"""
Deep profiling of StructureSignal to identify exact bottlenecks.
Phase 44.4 prep — measure per-section cost.
"""
import sys
import os
import pytest
import time
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_window(n=1500, base_t=1700000000):
    """Create realistic OHLCV data."""
    rng = np.random.default_rng(42)
    prices = 2000.0 + np.cumsum(rng.normal(0, 0.3, n))
    data = {
        "t": [base_t + i * 60 for i in range(n)],
        "o": prices,
        "h": prices + abs(rng.normal(0, 1.0, n)),
        "l": prices - abs(rng.normal(0, 1.0, n)),
        "c": prices + rng.normal(0, 0.5, n),
        "v": rng.integers(500, 5000, n).astype(float),
    }
    return pd.DataFrame(data)


def _make_swing_points(n=20, base_t=1700000000):
    """Create realistic swing points with types."""
    points = []
    for i in range(n):
        t = base_t + i * 600
        is_high = (i % 2 == 0)
        ptype = ["HH", "HL", "LH", "LL"][i % 4]
        points.append({
            "t": t,
            "price": 2000.0 + i * 10.0 if is_high else 1950.0 - i * 5.0,
            "is_high": is_high,
            "type": ptype,
            "is_choch": False,
        })
    return points


class MockState:
    def __init__(self):
        self.symbol = "TEST"
        self.swing_points = []
        self.obs = []
        self.transient_signals = {}
        self.signal_history = []

    def add_ob(self, ob):
        self.obs.append(ob)

    def log_actor(self, t, data):
        pass


class TestStructureSignalProfiling:
    def test_profile_structure_sections(self):
        """Profile each section of StructureSignal.calculate() separately."""
        from engine.signals.structure import StructureSignal
        from engine.state import SymbolState

        df = _make_window(1500)
        state = MockState()
        state.swing_points = _make_swing_points(30)

        signal = StructureSignal()

        # Warmup
        for _ in range(3):
            signal.calculate(df, state)

        # Profile 100 runs
        n_runs = 100
        total_time = 0

        # Section-level profiling
        sections = {"t_map_build": 0, "main_loop": 0, "verify_mitigations": 0, "ob_state_export": 0, "total": 0}

        for _ in range(n_runs):
            # We can't easily profile internal sections without modifying code,
            # so we profile the full calculate() call
            t0 = time.perf_counter_ns()
            signal.calculate(df, state)
            total_time += time.perf_counter_ns() - t0

        avg_us = (total_time / n_runs) / 1000
        print(f"\n[PROF] StructureSignal.calculate() avg: {avg_us:.1f}us per call ({n_runs} runs)")

        # Also test the hot inner functions
        # Profile t_map build
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            t_map = {int(t): i for i, t in enumerate(df['t'].values)}
        t_map_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] t_map build: {t_map_us:.1f}us")

        # Profile _verify_mitigations with 5 OBs
        state2 = MockState()
        state2.swing_points = _make_swing_points(30)
        # Add 5 unmitigated OBs
        for i in range(5):
            state2.obs.append({
                "ob_type": "BULLISH" if i % 2 == 0 else "BEARISH",
                "top": 2050.0 + i * 5.0,
                "bottom": 2040.0 + i * 5.0,
                "t_start": 1700000000 + i * 600,
                "t_breakout": 1700000060,
                "mitigated": False,
            })
        signal.calculate(df, state2)  # Reset state

        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            signal._verify_mitigations(df, state2)
        verify_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] _verify_mitigations (5 OBs): {verify_us:.1f}us")

        # Profile main loop (iterating swing points)
        t0 = time.perf_counter_ns()
        points = state.swing_points
        for _ in range(n_runs):
            for i in range(len(points)):
                p = points[i]
                if p.get('is_choch'):
                    continue
                if p.get('type') not in ["HH", "LL"]:
                    continue
                # Simulate forward scan (just accessing iloc, not full scan)
                for k in range(len(df)):
                    _ = df.iloc[k]['h']
                    break  # Only first candle
        loop_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] Main loop skeleton (no scan): {loop_us:.1f}us")

        # Profile DataFrame filtering (the df[df['t'] > t_breakout] pattern)
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            search_df = df[df['t'] > 1700000060]
            if not search_df.empty:
                for _, candle in search_df.iterrows():
                    _ = candle['h']
                    break
        filter_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] df.filter + iterrows: {filter_us:.1f}us")

        # Profile numpy alternative
        t_arr = df['t'].values
        h_arr = df['h'].values
        l_arr = df['l'].values
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            mask = t_arr > 1700000060
            indices = np.where(mask)[0]
            if len(indices) > 0:
                idx = indices[0]
                _ = h_arr[idx]
        numpy_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] numpy vectorized alt: {numpy_us:.1f}us")

        # Profile incremental scan (only last candle)
        t0 = time.perf_counter_ns()
        last_candle = df.iloc[-1]
        last_t = int(last_candle['t'])
        last_h = float(last_candle['h'])
        last_l = float(last_candle['l'])
        for _ in range(n_runs):
            for p in points:
                if p.get('is_choch'):
                    continue
                if p.get('type') not in ["HH", "LL"]:
                    continue
                is_bullish = p['is_high']
                if is_bullish and last_h > p['price']:
                    pass  # Breakout
                elif not is_bullish and last_l < p['price']:
                    pass  # Breakout
        incr_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] Incremental scan (last candle only): {incr_us:.1f}us")

        # Profile OB mitigation with numpy
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            t_vals = df['t'].values
            h_vals = df['h'].values
            l_vals = df['l'].values
            for ob in state2.obs:
                if ob.get('mitigated'):
                    continue
                t_breakout = ob.get('t_breakout', 0)
                mask = t_vals > t_breakout
                indices = np.where(mask)[0]
                if len(indices) == 0:
                    continue
                is_bullish = ob['ob_type'] == 'BULLISH'
                for idx in indices:
                    if is_bullish and l_vals[idx] <= ob['top']:
                        break
                    elif not is_bullish and h_vals[idx] >= ob['bottom']:
                        break
        ob_numpy_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000
        print(f"[PROF] OB mitigation (numpy indices): {ob_numpy_us:.1f}us")

        assert True  # All profiling completed

    def test_compare_iterrows_vs_numpy_iteration(self):
        """Direct comparison: df.iterrows() vs numpy array access."""
        df = _make_window(1500)
        n_runs = 100

        # iterrows
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            for _, candle in df.iterrows():
                _ = float(candle['h']) + float(candle['l'])
        iterrows_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000

        # numpy
        h = df['h'].values
        l = df['l'].values
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            for i in range(len(h)):
                _ = h[i] + l[i]
        numpy_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000

        # iloc
        t0 = time.perf_counter_ns()
        for _ in range(n_runs):
            for i in range(len(df)):
                _ = float(df.iloc[i]['h']) + float(df.iloc[i]['l'])
        iloc_us = ((time.perf_counter_ns() - t0) / n_runs) / 1000

        speedup_iterrows = iterrows_us / numpy_us if numpy_us > 0 else 0
        speedup_iloc = iloc_us / numpy_us if numpy_us > 0 else 0

        print(f"\n[PROF] iterrows: {iterrows_us:.1f}us")
        print(f"[PROF] numpy arrays: {numpy_us:.1f}us ({speedup_iterrows:.1f}x faster than iterrows)")
        print(f"[PROF] df.iloc: {iloc_us:.1f}us ({speedup_iloc:.1f}x faster than iloc)")

        assert numpy_us < iterrows_us, "numpy should be faster than iterrows"
