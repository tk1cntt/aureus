import os
import sys
import unittest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.live_engine import execute_signals_for_candle
from engine.manager import WindowManager
from engine.signal_factory import create_signal_set
from engine.signals.atr import ATRSignal


class _DummyRedis:
    pass


class TestATREnginePathIntegration(unittest.TestCase):
    def setUp(self):
        self.symbol = "XAUUSD"
        self.cfg = {
            "digits": 2,
            "point": 0.01,
            "pivots": {
                "ext_period": 5,
                "min_amplitude": 100,
                "min_motion": 1,
            },
        }
        self.signals = create_signal_set(self.symbol, self.cfg)
        self.signals["atr_14"] = ATRSignal(14)
        self.window_manager = WindowManager(max_window=300)
        self.redis_client = _DummyRedis()

    def _candle(self, idx: int) -> dict:
        base = 2050 + idx * 0.5
        return {
            "t": 1701000000 + idx * 60,
            "o": base,
            "h": base + 2.0,
            "l": base - 1.7,
            "c": base + 0.6,
            "v": 250 + idx,
            "tf": "M1",
        }

    def test_execute_signals_populates_atr_signal_history(self):
        state = None
        for i in range(40):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            execute_signals_for_candle(
                signals=self.signals,
                df=df,
                state=state,
                redis_client=self.redis_client,
                symbol=self.symbol,
                ts_unix=int(df.iloc[-1]["t"]),
            )

        assert state is not None
        self.assertTrue(
            any(item.get("tag") == "atr_14" for item in state.signal_history),
            msg="Expected ATR signal tag to be logged in state.signal_history",
        )

    def test_atr_state_progresses_after_warmup(self):
        atr_values = []
        state = None

        for i in range(30):
            df, state = self.window_manager.update(self.symbol, self._candle(i))
            execute_signals_for_candle(
                signals=self.signals,
                df=df,
                state=state,
                redis_client=self.redis_client,
                symbol=self.symbol,
                ts_unix=int(df.iloc[-1]["t"]),
            )
            if i >= 14:
                atr_values.append(float(state.atr))

        self.assertGreaterEqual(len(atr_values), 10)
        self.assertNotEqual(atr_values[0], atr_values[-1])


if __name__ == "__main__":
    unittest.main()
