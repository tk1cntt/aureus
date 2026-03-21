import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signals.sweep import SweepSignal
from engine.signals.sweep_bear import SweepBearSignal
from engine.signals.sweep_bull import SweepBullSignal


class TestSweepExecuteSignalsForCandleIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.window_manager = WindowManager(max_window=50)
        self.signals = {
            "sweep_processor": SweepSignal(),
            "sweep_bull": SweepBullSignal(),
            "sweep_bear": SweepBearSignal(),
        }

    def _push_candle(self, candle: dict):
        df, state = self.window_manager.update(self.symbol, candle)
        state.transient_signals = {}
        return df, state

    def test_execute_signals_emits_sweep_bull_and_transient_key(self):
        candle = {
            "t": 1702000000,
            "o": 2001.0,
            "h": 2002.0,
            "l": 1998.7,
            "c": 2000.8,
            "v": 250,
            "tf": "M1",
            "symbol": self.symbol,
        }
        df, state = self._push_candle(candle)
        state.market_regime = "SIDEWAYS"
        state.sweep_targets = [
            {
                "side": "BULLISH",
                "price": 1999.0,
                "type": "liquidity_low",
                "t_source": 1701999940,
                "fidelity": 0.7,
            }
        ]

        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        tags = [item.get("tag") for item in state.signal_history]
        self.assertIn("sweep_bull", tags)
        self.assertIn("sweep_bull", state.transient_signals)

    def test_execute_signals_dedup_prevents_duplicate_history_same_candle(self):
        candle = {
            "t": 1702000060,
            "o": 2001.2,
            "h": 2002.1,
            "l": 1998.6,
            "c": 2000.7,
            "v": 251,
            "tf": "M1",
            "symbol": self.symbol,
        }
        df, state = self._push_candle(candle)
        state.market_regime = "SIDEWAYS"
        state.sweep_targets = [{"side": "BULLISH", "price": 1999.0, "type": "liquidity_low"}]

        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        # Seed canonical sweep history shape so processor dedup guard can match.
        state.signal_history.append(
            {
                "tag": "sweep_bull",
                "t": int(candle["t"]),
                "price_swept": 1999.0,
            }
        )

        before_second_run = len([s for s in state.signal_history if s.get("tag") == "sweep_bull"])

        # Re-seed same target in the same candle: dedup should suppress processor emission.
        state.transient_signals = {}
        state.sweep_targets = [{"side": "BULLISH", "price": 1999.0, "type": "liquidity_low"}]
        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        after_second_run = len([s for s in state.signal_history if s.get("tag") == "sweep_bull"])
        self.assertEqual(before_second_run, after_second_run)

    def test_execute_signals_emits_sweep_bear_with_bearish_target(self):
        candle = {
            "t": 1702000120,
            "o": 2007.0,
            "h": 2012.4,
            "l": 2006.2,
            "c": 2007.9,
            "v": 252,
            "tf": "M1",
            "symbol": self.symbol,
        }
        df, state = self._push_candle(candle)
        state.market_regime = "TREND_DN"
        state.sweep_targets = [{"side": "BEARISH", "price": 2011.0, "type": "liquidity_high"}]

        execute_signals_for_candle(self.signals, df, state, self.symbol, None)

        tags = [item.get("tag") for item in state.signal_history]
        self.assertIn("sweep_bear", tags)
        self.assertIn("sweep_bear", state.transient_signals)


if __name__ == "__main__":
    unittest.main()
