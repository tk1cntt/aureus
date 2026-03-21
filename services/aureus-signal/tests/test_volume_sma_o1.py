import unittest
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.volume_sma import VolumeSMASignal

class MockState:
    pass

class TestVolumeSMASignalO1(unittest.TestCase):
    def setUp(self):
        self.signal = VolumeSMASignal(period=5, spike_threshold=1.5)

    def test_calculate_missing_volume_imputation(self):
        # 5 rows. 3 have volume, 2 have NaN.
        # Vol: 100, NaN, 100, NaN, 100.
        # With fillna(0), it becomes 100, 0, 100, 0, 100. Mean = 60.
        # Last vol is 100. 100 > 60 * 1.5 (90) -> True, should trigger spike.
        df = pd.DataFrame({
            "t": [1, 2, 3, 4, 5],
            "v": [100, np.nan, 100, np.nan, 100]
        })
        state = MockState()
        res = self.signal.calculate(df, state, symbol="TEST")
        
        self.assertTrue(hasattr(state, "vol_sma_5"))
        self.assertEqual(state.vol_sma_5, 60.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["tag"], "vol_sma_5")
        self.assertEqual(res["value"], 60.0)
        self.assertEqual(res["current_vol"], 100.0)

    def test_calculate_no_spike_returns_none(self):
        # Vol: 100, 100, 100, 100, 100. Mean = 100.
        # Last vol = 100. 100 > 100 * 1.5 is False. Should return None.
        df = pd.DataFrame({
            "t": [1, 2, 3, 4, 5],
            "v": [100, 100, 100, 100, 100]
        })
        state = MockState()
        res = self.signal.calculate(df, state, symbol="TEST")
        
        self.assertTrue(hasattr(state, "vol_sma_5"))
        self.assertEqual(state.vol_sma_5, 100.0)
        self.assertIsNone(res)

if __name__ == '__main__':
    unittest.main()
