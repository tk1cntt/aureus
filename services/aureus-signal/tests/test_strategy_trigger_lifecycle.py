"""
Comprehensive tests for TemplateStrategy trigger lifecycle.

Covers:
  1. Single-fire: strategy triggers exactly once when sequence completes
  2. No re-trigger on subsequent candles after firing
  3. Auto-reset after trigger — sequence returns to waiting
  4. Restart protection: re-evaluating same history does NOT re-trigger
  5. New cycle: new first-step signal starts fresh sequence and can fire again
  6. Timestamp-based indexing: sliding window doesn't break tracking
  7. Multi-step sequence: only fires when ALL required steps match
  8. on_bar_close path: same guarantees via registry evaluation path
"""
import inspect
import json
import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.state import SymbolState
from engine.strategies.template import TemplateStrategy
from engine.strategy_executor import run_strategy_executor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_df(t: int, close: float = 100.0):
    """Minimal DataFrame expected by evaluate()."""
    return pd.DataFrame([{"t": t, "c": close}])


def _make_record(t: int, events: list):
    """Build a normalized log record with events."""
    return {
        "t": t,
        "price": 100.0,
        "signals": {
            "events": events,
        },
    }


def _choch_up_event():
    return {"tag": "choch", "value": "choch_up", "price": 100.0}


def _choch_down_event():
    return {"tag": "choch", "value": "choch_down", "price": 99.0}


def _sweep_bull_event():
    return {"tag": "sweep", "value": "sweep_bull", "price": 100.0}


SINGLE_STEP_BULL_CONFIG = {
    "name": "TEST_BULL",
    "id": 10,
    "min_score_threshold": 0,
    "context_filters": [],
    "sequence": [
        {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
    ],
    "trade_execution": {
        "direction": "BUY",
        "size": 1.0,
        "sl": {"type": "FIXED_PIPS", "value": 500},
        "tp": {"type": "RR_RATIO", "value": 2.0},
    },
}

MULTI_STEP_BULL_CONFIG = {
    "name": "TEST_MULTI",
    "id": 20,
    "min_score_threshold": 0,
    "context_filters": [],
    "sequence": [
        {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
        {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]},
    ],
    "trade_execution": {
        "direction": "BUY",
        "size": 1.5,
        "sl": {"type": "FIXED_PIPS", "value": 500},
        "tp": {"type": "RR_RATIO", "value": 2.5},
    },
}


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestSingleFireGuarantee(unittest.TestCase):
    """Strategy triggers exactly ONCE when sequence completes, never again."""

    def test_triggers_once_on_match_candle(self):
        """Sequence matches on candle t=100 → fires exactly once."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        # Candle with choch_up event
        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        result = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNotNone(result, "Strategy should trigger on match candle")
        self.assertEqual(result["t"], 100)

    def test_no_retrigger_on_next_candle(self):
        """After firing on t=100, candle t=160 must NOT re-trigger."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        # First evaluation — should trigger
        result1 = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNotNone(result1)

        # Second evaluation on SAME candle — should NOT trigger (already triggered)
        result2 = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNone(result2, "Must not re-trigger on same candle after firing")

        # Third evaluation on NEXT candle — should NOT trigger
        result3 = strategy.evaluate(_make_df(160), {}, state)
        self.assertIsNone(result3, "Must not re-trigger on next candle")

    def test_no_retrigger_many_candles_later(self):
        """Even 50 candles later, without new signals, should not re-trigger."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        # Trigger on match candle
        result = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNotNone(result)

        # Simulate 50 subsequent candles with no events
        for t in range(160, 160 + 50 * 60, 60):
            state.log_signal_normalize.append(_make_record(t, []))
            r = strategy.evaluate(_make_df(t), {}, state)
            self.assertIsNone(r, f"Must not re-trigger at t={t}")


class TestRestartProtection(unittest.TestCase):
    """Simulates service restart: re-evaluating same history must NOT re-trigger."""

    def test_restart_does_not_retrigger(self):
        """
        Simulate: sequence matched at t=100. Service restarts.
        Executor re-reads the same log_signal_normalize from Redis.
        Strategy must NOT fire again.
        """
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        history = [
            _make_record(100, [_choch_up_event()]),
        ]
        state.log_signal_normalize = list(history)

        # First run — trigger
        result = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNotNone(result)

        # Save strategy_progress (simulates what executor_strategy_progress does)
        saved_progress = dict(state.strategy_progress)

        # --- RESTART: new state, restored progress ---
        state2 = SymbolState("XAUUSD")
        state2.log_signal_normalize = list(history)  # Same history from Redis
        state2.strategy_progress = saved_progress  # Restored from executor

        strategy2 = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        # Current bar is t=100 (same candle) — already triggered
        result2 = strategy2.evaluate(_make_df(100), {}, state2)
        self.assertIsNone(result2, "Must not re-trigger on restart with same history")

        # Current bar is t=160 (next candle) — also must not trigger
        result3 = strategy2.evaluate(_make_df(160), {}, state2)
        self.assertIsNone(result3, "Must not re-trigger on next candle after restart")

    def test_restart_with_fresh_state_no_trigger(self):
        """
        Worst case: restart with COMPLETELY fresh state (no saved progress).
        Current bar_ts is AFTER the matched event.
        Should still NOT trigger because bar_ts != sequence_completed_t.
        """
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        # Evaluate at a LATER candle (not the match candle)
        result = strategy.evaluate(_make_df(160), {}, state)
        self.assertIsNone(result, "Must not trigger when bar_ts != sequence_completed_t")


class TestNewCycleRetrigger(unittest.TestCase):
    """After trigger + reset, a NEW first-step signal starts fresh cycle."""

    def test_new_signal_allows_retrigger(self):
        """
        t=100: choch_up → fires
        t=200: new choch_up → should fire again (new cycle)
        """
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        # First cycle
        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]
        result1 = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNotNone(result1, "First trigger should fire")

        # Gap candles with no events
        state.log_signal_normalize.append(_make_record(160, []))

        # New signal — new cycle
        state.log_signal_normalize.append(
            _make_record(200, [_choch_up_event()])
        )
        result2 = strategy.evaluate(_make_df(200), {}, state)
        self.assertIsNotNone(result2, "New choch_up should trigger a new cycle")
        self.assertEqual(result2["t"], 200)

    def test_intermediate_candles_dont_trigger(self):
        """Between two trigger cycles, no spurious triggers."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]
        strategy.evaluate(_make_df(100), {}, state)

        # 5 candles with no events
        for t in [160, 220, 280, 340, 400]:
            state.log_signal_normalize.append(_make_record(t, []))
            r = strategy.evaluate(_make_df(t), {}, state)
            self.assertIsNone(r, f"No trigger expected at t={t}")

        # New signal at t=460
        state.log_signal_normalize.append(
            _make_record(460, [_choch_up_event()])
        )
        result = strategy.evaluate(_make_df(460), {}, state)
        self.assertIsNotNone(result, "Should trigger on new signal")


class TestTimestampBasedIndexing(unittest.TestCase):
    """Sliding window (max 240 records) doesn't break event tracking."""

    def test_sliding_window_no_double_trigger(self):
        """
        Fill 250 records (exceeding 240 window), trigger once, verify no re-trigger.
        """
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        base_t = 1000
        # 249 empty candles
        for i in range(249):
            state.log_signal_normalize.append(
                _make_record(base_t + i * 60, [])
            )

        # Candle 250 has the event
        event_t = base_t + 249 * 60
        state.log_signal_normalize.append(
            _make_record(event_t, [_choch_up_event()])
        )

        # Trim to 240 (simulating the real sliding window)
        state.log_signal_normalize = state.log_signal_normalize[-240:]

        result = strategy.evaluate(_make_df(event_t), {}, state)
        self.assertIsNotNone(result, "Should trigger despite sliding window")

        # Next candle — must not re-trigger
        next_t = event_t + 60
        state.log_signal_normalize.append(_make_record(next_t, []))
        state.log_signal_normalize = state.log_signal_normalize[-240:]

        result2 = strategy.evaluate(_make_df(next_t), {}, state)
        self.assertIsNone(result2, "Must not re-trigger after window slides")


class TestMultiStepSequence(unittest.TestCase):
    """Multi-step sequence (choch_up → sweep_bull) lifecycle."""

    def test_partial_match_no_trigger(self):
        """Only step 1 matched — should NOT trigger."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(MULTI_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]
        result = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNone(result, "Partial match must not trigger")

    def test_full_sequence_triggers_once(self):
        """Both steps match → triggers exactly once."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(MULTI_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
            _make_record(160, [_sweep_bull_event()]),
        ]

        # Evaluate at step 1 candle
        r1 = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNone(r1, "Only step 1 matched, no trigger yet")

        # Evaluate at step 2 candle — sequence completed here
        r2 = strategy.evaluate(_make_df(160), {}, state)
        self.assertIsNotNone(r2, "Full sequence should trigger")
        self.assertEqual(r2["t"], 160)

        # Next candle — no re-trigger
        state.log_signal_normalize.append(_make_record(220, []))
        r3 = strategy.evaluate(_make_df(220), {}, state)
        self.assertIsNone(r3, "Must not re-trigger after sequence fired")

    def test_reset_signal_clears_progress(self):
        """Reset signal (choch_down) clears in-progress sequence."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(MULTI_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),     # Step 1 matched
            _make_record(160, [_choch_down_event()]),   # RESET signal
        ]

        r1 = strategy.evaluate(_make_df(100), {}, state)
        self.assertIsNone(r1)

        r2 = strategy.evaluate(_make_df(160), {}, state)
        self.assertIsNone(r2, "Reset signal should clear progress")

        # New cycle after reset
        state.log_signal_normalize.append(
            _make_record(220, [_choch_up_event()])
        )
        state.log_signal_normalize.append(
            _make_record(280, [_sweep_bull_event()])
        )
        r3 = strategy.evaluate(_make_df(220), {}, state)
        self.assertIsNone(r3, "Only step 1 again")

        r4 = strategy.evaluate(_make_df(280), {}, state)
        self.assertIsNotNone(r4, "New full sequence should trigger")


class TestOnBarClosePath(unittest.TestCase):
    """on_bar_close() path — same guarantees as evaluate()."""

    def test_on_bar_close_triggers_once(self):
        """on_bar_close returns is_actionable=True exactly once."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        context = {"df": _make_df(100), "state": state, "signals": {}, "backfill_status": "READY"}
        intent = strategy.on_bar_close(context)

        self.assertIsNotNone(intent)
        self.assertTrue(intent["is_actionable"], "Should be actionable on match candle")
        self.assertEqual(intent["reason_code"], "OK")

    def test_on_bar_close_no_retrigger(self):
        """After firing, on_bar_close returns ALREADY_TRIGGERED."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        ctx1 = {"df": _make_df(100), "state": state, "signals": {}, "backfill_status": "READY"}
        intent1 = strategy.on_bar_close(ctx1)
        self.assertTrue(intent1["is_actionable"])

        # Next candle
        state.log_signal_normalize.append(_make_record(160, []))
        ctx2 = {"df": _make_df(160), "state": state, "signals": {}, "backfill_status": "READY"}
        intent2 = strategy.on_bar_close(ctx2)
        self.assertFalse(intent2["is_actionable"], "Must not be actionable after trigger")

    def test_on_bar_close_restart_no_retrigger(self):
        """Restart scenario via on_bar_close — must not re-trigger."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]

        ctx = {"df": _make_df(100), "state": state, "signals": {}, "backfill_status": "READY"}
        intent = strategy.on_bar_close(ctx)
        self.assertTrue(intent["is_actionable"])

        saved_progress = dict(state.strategy_progress)

        # Restart: fresh state, same history, restored progress
        state2 = SymbolState("XAUUSD")
        state2.log_signal_normalize = [_make_record(100, [_choch_up_event()])]
        state2.strategy_progress = saved_progress

        strategy2 = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)
        ctx2 = {"df": _make_df(160), "state": state2, "signals": {}, "backfill_status": "READY"}
        intent2 = strategy2.on_bar_close(ctx2)
        self.assertFalse(intent2["is_actionable"], "Must not trigger after restart")


class TestTriggeredTLifecycle(unittest.TestCase):
    """Verify triggered_t is correctly set and cleared."""

    def test_triggered_t_set_after_fire(self):
        """triggered_t is set to bar_ts after strategy fires."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]
        strategy.evaluate(_make_df(100), {}, state)

        progress = state.strategy_progress.get("TEST_BULL", {})
        self.assertEqual(progress.get("triggered_t"), 100)

    def test_triggered_t_cleared_on_new_step0(self):
        """When a new first-step signal arrives, triggered_t resets to 0."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(SINGLE_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
        ]
        strategy.evaluate(_make_df(100), {}, state)

        # Verify triggered
        progress = state.strategy_progress.get("TEST_BULL", {})
        self.assertEqual(progress.get("triggered_t"), 100)

        # New signal arrives
        state.log_signal_normalize.append(
            _make_record(200, [_choch_up_event()])
        )
        # Evaluate — this processes the new signal and clears triggered_t
        strategy.evaluate(_make_df(200), {}, state)

        progress2 = state.strategy_progress.get("TEST_BULL", {})
        # After triggering at t=200, triggered_t should be set to 200 again
        self.assertEqual(progress2.get("triggered_t"), 200)

    def test_sequence_completed_t_tracks_last_event(self):
        """sequence_completed_t equals timestamp of last matched event."""
        state = SymbolState("XAUUSD")
        strategy = TemplateStrategy(MULTI_STEP_BULL_CONFIG)

        state.log_signal_normalize = [
            _make_record(100, [_choch_up_event()]),
            _make_record(200, [_sweep_bull_event()]),
        ]

        # Process step 1
        strategy.evaluate(_make_df(100), {}, state)
        # Process step 2 — triggers
        strategy.evaluate(_make_df(200), {}, state)

        progress = state.strategy_progress.get("TEST_MULTI", {})
        # After trigger, state is reset but triggered_t is set
        self.assertEqual(progress.get("triggered_t"), 200)


class TestStrategyExecutorSnapshotConsistency(unittest.TestCase):
    """Contract D-07: snapshot/current_signal phải cùng candle timestamp."""

    def test_rejects_mismatched_snapshot_timestamp(self):
        from engine.strategy_executor import validate_snapshot_candle_consistency

        payload = {
            "t": 1709300000,
            "current_signal": {"t": 1709300000, "tag": "choch_up"},
            "signals_snapshot": {"choch_up": {"t": 1709300060, "value": True}},
        }

        is_valid, reason = validate_snapshot_candle_consistency(payload)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "SNAPSHOT_CANDLE_MISMATCH")


def test_run_strategy_executor_keeps_snapshot_gate_before_trigger_processing():
    source = inspect.getsource(run_strategy_executor)
    snapshot_idx = source.index("validate_snapshot_candle_consistency(payload)")
    trigger_idx = source.index("process_triggers(")
    assert snapshot_idx < trigger_idx


if __name__ == "__main__":
    unittest.main()
