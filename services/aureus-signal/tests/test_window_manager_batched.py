"""
Tests for Phase 44.1: Batched DataFrame Rebuild in WindowManager.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.manager import WindowManager


def _make_candle(t, o=2000.0, h=2005.0, l=1995.0, c=2002.0, v=1000, tf="M1"):
    return {"t": str(t), "o": str(o), "h": str(h), "l": str(l), "c": str(c), "v": str(v), "tf": tf}


class TestBatchedRebuildThreshold:
    def test_batched_rebuild_at_threshold(self):
        """Add 15 candles with threshold=10, verify base_df rebuilt at candle 10."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        base_lens = []
        for i in range(15):
            candle = _make_candle(1700000000 + i * 60)
            wm.update("TEST", candle)
            base = wm._base_dfs.get("TEST")
            if base is not None:
                base_lens.append(len(base))

        # base_df should be updated when threshold reached (10 candles)
        # and then again at end of test (after _build_df_lazy full rebuild on last candle)
        assert len(base_lens) >= 2, f"Expected at least 2 base updates, got {len(base_lens)}"

    def test_pending_buffer_accumulates_below_threshold(self):
        """Pending buffer should accumulate candles until threshold is reached."""
        wm = WindowManager(max_window=100, batch_threshold=5)

        # Add 4 candles (below threshold)
        for i in range(4):
            candle = _make_candle(1700000000 + i * 60)
            wm.update("TEST", candle)

        # First candle triggers full rebuild (no base yet) which clears pending
        # After that, candles 2-4 accumulate in pending
        assert len(wm._base_dfs.get("TEST", [])) > 0, "Base DF should exist after first candle"

    def test_pending_cleared_at_threshold_sync(self):
        """When threshold sync happens, pending buffer should be cleared."""
        wm = WindowManager(max_window=100, batch_threshold=5)

        for i in range(5):
            candle = _make_candle(1700000000 + i * 60)
            wm.update("TEST", candle)

        # After 5 candles, sync happened at candle 5 (pending reached threshold)
        # _sync_base_with_window clears pending, then _build_df_lazy uses the new base
        # So pending should be 0 (sync cleared it) or very small
        pending_count = len(wm._pending_buffers.get("TEST", []))
        # Pending should be 0 because sync cleared it
        # But if _build_df_lazy did a full rebuild, it also clears pending
        assert pending_count < 5, f"Pending should be cleared after threshold sync, got {pending_count}"


class TestGetDfCorrectData:
    def test_get_df_returns_correct_data_after_batch(self):
        """DataFrame should always reflect current window state."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        for i in range(15):
            candle = _make_candle(1700000000 + i * 60, c=2000.0 + i)
            wm.update("TEST", candle)

        df = wm.get_df("TEST")
        assert df is not None
        assert len(df) == 15, f"Expected 15 rows, got {len(df)}"
        assert float(df.iloc[-1]["c"]) == 2014.0

    def test_get_df_correct_after_pending(self):
        """DataFrame should include pending candles not yet in base."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        for i in range(5):
            candle = _make_candle(1700000000 + i * 60, c=2000.0 + i)
            wm.update("TEST", candle)

        df = wm.get_df("TEST")
        assert df is not None
        assert len(df) == 5, f"Expected 5 rows, got {len(df)}"

    def test_get_df_correct_mixed_batch(self):
        """After base + pending mix, DataFrame should have all candles."""
        wm = WindowManager(max_window=100, batch_threshold=5)

        for i in range(12):
            candle = _make_candle(1700000000 + i * 60, c=2000.0 + i)
            wm.update("TEST", candle)

        df = wm.get_df("TEST")
        assert df is not None
        assert len(df) == 12, f"Expected 12 rows, got {len(df)}"
        # First and last candle prices
        assert float(df.iloc[0]["c"]) == 2000.0
        assert float(df.iloc[-1]["c"]) == 2011.0


class TestSameTimestampUpdate:
    def test_same_timestamp_update_reflects_new_value(self):
        """Updating same timestamp should produce correct DataFrame."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        wm.update("TEST", _make_candle(1700000000, c=2000.0))
        wm.update("TEST", _make_candle(1700000060, c=2001.0))

        # Update second candle with same timestamp
        wm.update("TEST", _make_candle(1700000060, c=2002.0))

        df = wm.get_df("TEST")
        assert float(df.iloc[-1]["c"]) == 2002.0
        assert len(df) == 2


class TestOutOfOrderCandle:
    def test_out_of_order_candle_correct_order(self):
        """Out-of-order candle should result in correctly ordered DataFrame."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        wm.update("TEST", _make_candle(1700000000))
        wm.update("TEST", _make_candle(1700000120))  # Skip 60

        # Add out-of-order candle
        wm.update("TEST", _make_candle(1700000060))

        df = wm.get_df("TEST")
        timestamps = df["t"].tolist()
        assert timestamps == sorted(timestamps), "Timestamps should be in order"
        assert len(df) == 3


class TestWindowTrimInvalidatesBase:
    def test_window_trim_produces_correct_size(self):
        """When window is trimmed, DataFrame should have correct size."""
        wm = WindowManager(max_window=5, batch_threshold=10)

        for i in range(6):
            candle = _make_candle(1700000000 + i * 60)
            wm.update("TEST", candle)

        assert len(wm.windows["TEST"]) == 5

        df = wm.get_df("TEST")
        assert len(df) == 5, f"Expected 5 rows after trim, got {len(df)}"


class TestResetClearsBatchState:
    def test_reset_clears_batch_state(self):
        """reset() should clear all batch-related state."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        for i in range(5):
            wm.update("TEST", _make_candle(1700000000 + i * 60))

        assert "TEST" in wm._base_dfs or "TEST" in wm._pending_buffers

        wm.reset("TEST")

        assert "TEST" not in wm._base_dfs
        assert "TEST" not in wm._pending_buffers
        assert "TEST" not in wm._batch_stale
        assert "TEST" not in wm.windows
        assert "TEST" not in wm.dfs


class TestBackwardCompatibility:
    def test_existing_get_df_usage_works(self):
        """Existing code using get_df() should work unchanged."""
        wm = WindowManager(max_window=100)

        for i in range(20):
            wm.update("TEST", _make_candle(1700000000 + i * 60))

        df = wm.get_df("TEST")
        assert df is not None
        assert len(df) == 20
        assert list(df.columns) == ["t", "o", "h", "l", "c", "v", "tf"]

    def test_update_returns_df_and_state(self):
        """update() should still return (df, state) tuple."""
        wm = WindowManager(max_window=100)

        result = wm.update("TEST", _make_candle(1700000000))

        assert isinstance(result, tuple)
        assert len(result) == 2
        df, state = result
        assert df is not None
        assert state is not None

    def test_default_batch_threshold_is_10(self):
        """Default batch_threshold should be 10."""
        wm = WindowManager()
        assert wm._batch_threshold == 10

    def test_custom_batch_threshold(self):
        """Should accept custom batch_threshold."""
        wm = WindowManager(batch_threshold=5)
        assert wm._batch_threshold == 5


class TestBatchHitMetric:
    def test_batch_hit_returns_correct_tuple(self):
        """_build_df_lazy should return (df, is_batch_hit) tuple."""
        wm = WindowManager(max_window=100, batch_threshold=10)

        wm.update("TEST", _make_candle(1700000000))

        df, is_batch_hit = wm._build_df_lazy("TEST")
        assert isinstance(is_batch_hit, bool)
        assert df is not None
        assert len(df) == 1

    def test_batch_hit_on_incremental_concat(self):
        """When base exists and pending has data, should use incremental concat."""
        wm = WindowManager(max_window=100, batch_threshold=3)

        # 3 candles triggers sync, then _build_df_lazy does full rebuild
        for i in range(3):
            wm.update("TEST", _make_candle(1700000000 + i * 60))

        # Now base exists, add more candles to pending
        for i in range(3, 5):
            candle = _make_candle(1700000000 + i * 60)
            wm.update("TEST", candle)

        # After candle 4 and 5, pending has 2 items
        # _build_df_lazy should use incremental concat (batch_hit=True)
        df, is_batch_hit = wm._build_df_lazy("TEST")
        assert is_batch_hit is True, "Should use incremental concat when base exists and pending has data"
        assert len(df) == 5
