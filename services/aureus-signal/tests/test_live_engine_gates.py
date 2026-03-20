import os
import sys
import unittest

# Ensure engine module can be imported when running from repository root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import (
    evaluate_backfill_readiness_gate,
    evaluate_closed_candle_gate,
    evaluate_window_integrity_gate,
)
from engine.manager import WindowManager


class TestLiveEngineClosedCandleGate(unittest.TestCase):
    def test_reject_when_candle_flagged_not_closed(self):
        allowed, reason = evaluate_closed_candle_gate(
            msg_type="CANDLE",
            stream_key="aureus:stream:XAUUSD:candle",
            payload={"t": "1710000000", "is_closed": "false"},
        )

        self.assertFalse(allowed)
        self.assertEqual(reason, "BAR_NOT_CLOSED")

    def test_allow_candle_message_without_close_flag(self):
        allowed, reason = evaluate_closed_candle_gate(
            msg_type="CANDLE",
            stream_key="aureus:stream:XAUUSD:candle",
            payload={"t": "1710000000", "o": "1", "h": "2", "l": "0.5", "c": "1.5"},
        )

        self.assertTrue(allowed)
        self.assertEqual(reason, "OK")


class TestLiveEngineBackfillReadinessGate(unittest.TestCase):
    def setUp(self):
        self.window_manager = WindowManager()
        self.symbol = "XAUUSD"

    def test_reject_when_backfill_status_uninitialized(self):
        allowed, reason = evaluate_backfill_readiness_gate(self.symbol, self.window_manager)

        self.assertFalse(allowed)
        self.assertEqual(reason, "BACKFILL_NOT_READY:NOT_READY:UNINITIALIZED")

    def test_reject_when_backfill_explicitly_not_ready(self):
        self.window_manager.set_backfill_status(self.symbol, "NOT_READY", reason="GAP_DETECTED", updated_at=123)
        allowed, reason = evaluate_backfill_readiness_gate(self.symbol, self.window_manager)

        self.assertFalse(allowed)
        self.assertEqual(reason, "BACKFILL_NOT_READY:NOT_READY:GAP_DETECTED")

    def test_allow_when_backfill_ready(self):
        self.window_manager.set_backfill_status(self.symbol, "READY", reason="INIT_WARMUP_COMPLETED", updated_at=123)
        allowed, reason = evaluate_backfill_readiness_gate(self.symbol, self.window_manager)

        self.assertTrue(allowed)
        self.assertEqual(reason, "OK")


class TestLiveEngineWindowIntegrityGate(unittest.TestCase):
    def setUp(self):
        self.window_manager = WindowManager()
        self.symbol = "XAUUSD"

    def test_reject_when_integrity_uninitialized(self):
        allowed, reason = evaluate_window_integrity_gate(self.symbol, self.window_manager)

        self.assertFalse(allowed)
        self.assertEqual(reason, "WINDOW_NOT_CONTIGUOUS:UNINITIALIZED")

    def test_reject_when_integrity_explicitly_invalid(self):
        self.window_manager.set_window_integrity(
            self.symbol,
            is_contiguous_window=False,
            window_start=1710000000,
            window_end=1710000180,
            window_hash="abc",
            reason="GAP_OR_OUT_OF_ORDER",
            updated_at=1710000180,
        )
        allowed, reason = evaluate_window_integrity_gate(self.symbol, self.window_manager)

        self.assertFalse(allowed)
        self.assertEqual(reason, "WINDOW_NOT_CONTIGUOUS:GAP_OR_OUT_OF_ORDER")

    def test_allow_when_integrity_valid(self):
        self.window_manager.set_window_integrity(
            self.symbol,
            is_contiguous_window=True,
            window_start=1710000000,
            window_end=1710000120,
            window_hash="def",
            reason="OK",
            updated_at=1710000120,
        )
        allowed, reason = evaluate_window_integrity_gate(self.symbol, self.window_manager)

        self.assertTrue(allowed)
        self.assertEqual(reason, "OK")

    def test_update_computes_non_contiguous_integrity(self):
        self.window_manager.update(
            self.symbol,
            {"t": "1710000000", "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "10", "tf": "M1"},
        )
        self.window_manager.update(
            self.symbol,
            {"t": "1710000120", "o": "1.1", "h": "2.1", "l": "0.6", "c": "1.6", "v": "11", "tf": "M1"},
        )

        integrity = self.window_manager.get_window_integrity(self.symbol)
        self.assertFalse(integrity["is_contiguous_window"])
        self.assertEqual(integrity["reason"], "GAP_OR_OUT_OF_ORDER")
        self.assertEqual(integrity["window_start"], 1710000000)
        self.assertEqual(integrity["window_end"], 1710000120)
        self.assertIsNotNone(integrity["window_hash"])


if __name__ == "__main__":
    unittest.main()
