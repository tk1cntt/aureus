import os
import sys
import unittest
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.structure import StructureSignal
from engine.state import SymbolState

class TestStructureExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=300)
        self.signals = {
            "structure_processor": StructureSignal() # Must match factory keys
        }

    def _candle(self, idx: int) -> dict:
        candles = [
            {"t": 1705000000 + idx*60, "o": 100.0, "h": 110.0, "l": 90.0, "c": 100.0, "v": 100}
        ]
        candle = dict(candles[0])
        candle.update({"tf": "M1", "symbol": self.symbol})
        return candle

    def _run_until(self, last_idx: int):
        state = None
        for i in range(last_idx + 1):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            state.transient_signals = {}
            state.swing_points = [{"t": 10, "price": 100.0, "type": "HH", "is_high": True}]
            state.obs = []
            execute_signals_for_candle(self.signals, df, state, self.symbol, None)
        self.assertIsNotNone(state)
        return state

    def test_execute_signals_emits_ob_state_traceability(self):
        # We need at least 5 candles for `structure.py` to evaluate
        state = self._run_until(6)

        # Verify Traceability Memory is set
        self.assertIn("ob_state", state.transient_signals)
        self.assertIn("active_obs", state.transient_signals["ob_state"])
        # With default parameters and only 6 candles, no OBs are formed, so active_obs should be empty list, but struct exists
        self.assertEqual(state.transient_signals["ob_state"]["active_obs"], [])

    def test_verify_mitigations_uses_last_event_wins_for_same_candle(self):
        signal = StructureSignal()
        state = SymbolState(self.symbol)
        state.transient_signals = {}

        state.obs = [
            {
                "ob_type": "BULLISH",
                "top": 105.0,
                "bottom": 100.0,
                "t_start": 1,
                "t_breakout": 100,
                "mitigated": False,
            },
            {
                "ob_type": "BULLISH",
                "top": 98.0,
                "bottom": 94.0,
                "t_start": 2,
                "t_breakout": 100,
                "mitigated": False,
            },
        ]

        df = pd.DataFrame([
            {"t": 100, "o": 110.0, "h": 112.0, "l": 109.0, "c": 111.0},
            {"t": 160, "o": 111.0, "h": 113.0, "l": 108.0, "c": 112.0},
            {"t": 220, "o": 112.0, "h": 114.0, "l": 93.0, "c": 99.0},
        ])

        signal._verify_mitigations(df, state)

        self.assertIn("ob_bull_mitigated", state.transient_signals)
        self.assertEqual(state.transient_signals["ob_bull_mitigated"]["t_start"], 2)
        self.assertNotIn("ob_bull_mitigated_events", state.transient_signals)
        self.assertNotIn("ob_bear_mitigated_events", state.transient_signals)
        self.assertEqual(state.ai_trigger_events, [])
if __name__ == "__main__":
    unittest.main()
