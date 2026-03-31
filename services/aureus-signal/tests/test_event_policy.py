import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.event_policy import evaluate_ai_trigger_events


class TestEventPolicy(unittest.TestCase):
    def test_evaluate_ai_trigger_events_maps_sweep_touched_tags(self):
        transient_signals = {
            "sweep_touched_bull": {"tag": "sweep"},
            "sweep_touched_bear": {"tag": "sweep"},
        }

        events = evaluate_ai_trigger_events(transient_signals)

        self.assertIn("LIQUIDITY_SWEEP_TOUCHED_BULLISH", events)
        self.assertIn("LIQUIDITY_SWEEP_TOUCHED_BEARISH", events)

    def test_evaluate_ai_trigger_events_keeps_priority_order_for_sweep_tags(self):
        transient_signals = {
            "clean_breakout_bear": {"tag": "sweep"},
            "sweep_touched_bull": {"tag": "sweep"},
            "sweep_bull": {"tag": "sweep"},
            "stop_hunt_bull": {"tag": "sweep"},
        }

        events = evaluate_ai_trigger_events(transient_signals)

        self.assertEqual(
            events,
            [
                "LIQUIDITY_STOP_HUNT_BULLISH",
                "LIQUIDITY_SWEEP_BULLISH",
                "LIQUIDITY_SWEEP_TOUCHED_BULLISH",
                "CLEAN_BREAKOUT_BEARISH",
            ],
        )


if __name__ == "__main__":
    unittest.main()
