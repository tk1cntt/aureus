"""
Tests for Phase 44.2: Incremental Cache ATR/VolSMA with Verification Layer.
"""
import sys
import os
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_df(rows=50, base_t=1700000000):
    """Create a DataFrame with random-ish OHLCV data."""
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


class TestVolSMAIncrementalVsFullCalc:
    def test_vol_sma_incremental_equals_full_calc(self):
        """Run 100 candles, verify incremental == full calc at verification points."""
        from engine.signals.volume_sma import VolumeSMASignal
        from engine.state import SymbolState

        signal = VolumeSMASignal(period=20)
        df = _make_df(50)
        state = SymbolState("TEST")

        # Warmup: run 20 candles to fill buffer
        for i in range(20):
            sub_df = df.iloc[:i+1]
            result = signal.calculate(sub_df, state)

        # Now run 80 more candles (candle 21-100)
        verification_drifts = []
        for i in range(20, 100):
            sub_df = df.iloc[:i+1]
            state._verification_counter = i + 1
            signal.calculate(sub_df, state)

            # At verification points (every 10), check drift
            if (i + 1) % 10 == 0:
                full_calc = float(sub_df['v'].tail(20).fillna(0).mean())
                incremental = state.vol_sma_20
                if full_calc > 0:
                    drift = abs(incremental - full_calc) / full_calc
                    verification_drifts.append((i + 1, drift))

        # All drifts should be corrected to near-zero
        for candle_num, drift in verification_drifts:
            assert drift < 0.0001, f"Candle {candle_num}: drift={drift:.4%} exceeds 0.01% threshold"


class TestVolSMADriftDetectionAndCorrection:
    def test_vol_sma_drift_detection_and_correction(self):
        """Inject drift into buffer, verify detection corrects it."""
        from engine.signals.volume_sma import VolumeSMASignal
        from engine.state import SymbolState

        signal = VolumeSMASignal(period=20)
        df = _make_df(50)
        state = SymbolState("TEST")

        # Warmup
        for i in range(20):
            sub_df = df.iloc[:i+1]
            signal.calculate(sub_df, state)

        # Inject drift: set buffer to wrong values
        state._vol_sma_20_buffer = [0.0] * 20
        state.vol_sma_20 = 50.0  # Way off from actual ~1500

        # Run one more candle with verification
        state._verification_counter = 30  # At a verification point
        sub_df = df.iloc[:21]
        signal.calculate(sub_df, state)

        # Should have been corrected
        full_calc = float(sub_df['v'].tail(20).fillna(0).mean())
        drift = abs(state.vol_sma_20 - full_calc) / full_calc
        assert drift < 0.0001, f"Drift not corrected: {drift:.4%}"


class TestATRVerificationCatchesDrift:
    def test_atr_verification_catches_drift(self):
        """Inject wrong ATR value, verify correction at verification point."""
        from engine.signals.atr import ATRSignal
        from engine.state import SymbolState

        signal = ATRSignal(period=14)
        df = _make_df(30)
        state = SymbolState("TEST")

        # Warmup: run enough candles to establish ATR
        for i in range(15):
            sub_df = df.iloc[:i+1]
            signal.calculate(sub_df, state)

        # Inject drift: set ATR to wrong value
        wrong_atr = state.atr * 2.0
        state.atr = wrong_atr

        # Run at verification point with the SAME sub_df (no new candle)
        state._verification_counter = 30
        sub_df = df.iloc[:15]  # Same data used to compute original ATR
        signal.calculate(sub_df, state)

        # Should have been corrected back to full calculation
        h_series = sub_df['h']
        l_series = sub_df['l']
        pc_series = sub_df['c'].shift(1)
        tr_series = pd.concat(
            [h_series - l_series, abs(h_series - pc_series), abs(l_series - pc_series)],
            axis=1,
        ).max(axis=1)
        atr_full = float(tr_series.ewm(alpha=1/14, adjust=False).mean().iloc[-1])

        drift = abs(state.atr - atr_full) / atr_full
        assert drift < 0.0001, f"ATR drift not corrected: {drift:.4%}"


class TestFullRecalcEvery50Candles:
    def test_atr_full_recalc_every_50_candles(self):
        """Run 100 candles, verify full recalc happens at 50."""
        from engine.signals.atr import ATRSignal
        from engine.state import SymbolState

        signal = ATRSignal(period=14)
        df = _make_df(60)
        state = SymbolState("TEST")

        for i in range(50):
            sub_df = df.iloc[:i+1]
            state._verification_counter = i + 1
            signal.calculate(sub_df, state)

        # At candle 50, should have done full recalc
        # The ATR should match full calculation
        sub_df_50 = df.iloc[:50]
        h_series = sub_df_50['h']
        l_series = sub_df_50['l']
        pc_series = sub_df_50['c'].shift(1)
        tr_series = pd.concat(
            [h_series - l_series, abs(h_series - pc_series), abs(l_series - pc_series)],
            axis=1,
        ).max(axis=1)
        atr_full = float(tr_series.ewm(alpha=1/14, adjust=False).mean().iloc[-1])

        drift = abs(state.atr - atr_full) / atr_full
        assert drift < 0.0001, f"Full recalc at 50 failed: drift={drift:.4%}"

    def test_vol_sma_full_recalc_every_50_candles(self):
        """Run 60 candles, verify full recalc at 50."""
        from engine.signals.volume_sma import VolumeSMASignal
        from engine.state import SymbolState

        signal = VolumeSMASignal(period=20)
        df = _make_df(60)
        state = SymbolState("TEST")

        for i in range(50):
            sub_df = df.iloc[:i+1]
            state._verification_counter = i + 1
            signal.calculate(sub_df, state)

        # At candle 50, should match full calculation
        full_calc = float(df['v'].iloc[30:50].fillna(0).mean())
        drift = abs(state.vol_sma_20 - full_calc) / full_calc
        assert drift < 0.0001, f"Full recalc at 50 failed: drift={drift:.4%}"


class TestSnapshotSaveRestoreVolSMABuffer:
    def test_snapshot_save_restore_vol_sma_buffer(self):
        """Save snapshot, restore, verify buffer correct."""
        from engine.state import SymbolState
        from engine.state_snapshot import StateSnapshot

        state = SymbolState("TEST")
        state.vol_sma_20 = 1500.0
        state._vol_sma_20_buffer = [1000.0, 1010.0, 1020.0] + [1100.0] * 17

        candle = {"t": "1700000000", "symbol": "TEST"}
        snapshot = StateSnapshot.from_state(state, candle)

        assert snapshot.vol_sma_20 == 1500.0
        assert snapshot.vol_sma_buffer is not None

        # Restore to new state
        new_state = SymbolState("TEST")
        snapshot.restore_to_state(new_state)

        assert new_state.vol_sma_20 == 1500.0
        assert hasattr(new_state, '_vol_sma_20_buffer')
        assert len(new_state._vol_sma_20_buffer) == 20

    def test_snapshot_restore_without_buffer(self):
        """State without buffer should still restore vol_sma_20."""
        from engine.state import SymbolState
        from engine.state_snapshot import StateSnapshot

        state = SymbolState("TEST")
        state.vol_sma_20 = 1200.0

        candle = {"t": "1700000000", "symbol": "TEST"}
        snapshot = StateSnapshot.from_state(state, candle)

        new_state = SymbolState("TEST")
        snapshot.restore_to_state(new_state)

        assert new_state.vol_sma_20 == 1200.0
        # Buffer should not exist (wasn't saved)
        assert not hasattr(new_state, '_vol_sma_20_buffer')


class TestVolSMAFallbackOnMissingBuffer:
    def test_vol_sma_fallback_on_missing_buffer(self):
        """State without buffer should fallback to full calculation."""
        from engine.signals.volume_sma import VolumeSMASignal
        from engine.state import SymbolState

        signal = VolumeSMASignal(period=20)
        df = _make_df(30)
        state = SymbolState("TEST")

        # Run without buffer (first time)
        for i in range(20):
            sub_df = df.iloc[:i+1]
            result = signal.calculate(sub_df, state)

        # Should have full calculation result
        assert state.vol_sma_20 is not None

        # Verify against direct calculation
        expected = float(df['v'].head(20).fillna(0).mean())
        drift = abs(state.vol_sma_20 - expected) / expected
        assert drift < 0.0001


class TestVolSMAPerformance:
    def test_vol_sma_incremental_correctness(self):
        """Incremental results should match manual full calculation (correctness, not speed).

        Note: For VolSMA with small window (20), pandas tail().mean() is already O(k).
        The value of incremental cache is:
        1. Consistent pattern with ATR (O(1) formula)
        2. Verification layer catches drift
        3. Buffer persistence enables accurate restore after restart
        """
        import time
        from engine.signals.volume_sma import VolumeSMASignal
        from engine.state import SymbolState

        signal = VolumeSMASignal(period=20)
        df = _make_df(200)
        state = SymbolState("TEST")

        # Warmup
        for i in range(20):
            sub_df = df.iloc[:i+1]
            signal.calculate(sub_df, state)

        # Run and verify correctness at each candle
        max_drift = 0
        for i in range(20, 200):
            sub_df = df.iloc[:i+1]
            signal.calculate(sub_df, state)

            # Compare against full calc
            full_calc = float(sub_df['v'].tail(20).fillna(0).mean())
            if full_calc > 0:
                drift = abs(state.vol_sma_20 - full_calc) / full_calc
                max_drift = max(max_drift, drift)

        # Max drift should be minimal (incremental formula is exact)
        assert max_drift < 0.0001, f"Max drift {max_drift:.4%} exceeds 0.01%"


class TestVerificationCounterInState:
    def test_verification_counter_increments(self):
        """State should have _verification_counter."""
        from engine.state import SymbolState

        state = SymbolState("TEST")
        assert hasattr(state, '_verification_counter')
        assert state._verification_counter == 0


class TestBackwardCompatibility:
    def test_atr_without_verification_counter(self):
        """ATR should work even if state has no _verification_counter."""
        from engine.signals.atr import ATRSignal
        from engine.state import SymbolState

        signal = ATRSignal(period=14)
        df = _make_df(30)

        # Create state, remove verification counter
        state = SymbolState("TEST")
        if hasattr(state, '_verification_counter'):
            delattr(state, '_verification_counter')

        for i in range(15):
            sub_df = df.iloc[:i+1]
            result = signal.calculate(sub_df, state)

        assert state.atr is not None

    def test_vol_sma_without_verification_counter(self):
        """VolSMA should work even if state has no _verification_counter."""
        from engine.signals.volume_sma import VolumeSMASignal
        from engine.state import SymbolState

        signal = VolumeSMASignal(period=20)
        df = _make_df(30)

        state = SymbolState("TEST")
        if hasattr(state, '_verification_counter'):
            delattr(state, '_verification_counter')

        for i in range(20):
            sub_df = df.iloc[:i+1]
            result = signal.calculate(sub_df, state)

        assert state.vol_sma_20 is not None
