import unittest
import pandas as pd
import sys
import os

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.common.zigzag_pro2 import ZigZagPro
from engine.signals.pivots import PivotSignal

class MockState:
    def __init__(self):
        self.zigzag_engine = None
        self.swing_points = []
        self.tracking_vars = {}

class TestDynamicAmplitude(unittest.TestCase):
    def test_zigzag_update_params(self):
        engine = ZigZagPro(min_amplitude=100, point=0.01, digits=2)
        initial_mp = engine.mp
        self.assertEqual(initial_mp, 1.0)
        
        # Increase amplitude to 200 points
        engine.update_params(min_amplitude=200)
        self.assertEqual(engine.mp, 2.0)
        
        # Decrease amplitude to 50 points
        engine.update_params(min_amplitude=50)
        self.assertEqual(engine.mp, 0.5)

    def test_pivot_signal_dynamic_calculation(self):
        # 0.5% amplitude on price 1000.0 with 0.01 point should be 500 points
        # Calculation: (1000.0 * 0.5 / 100) / 0.01 = 5 / 0.01 = 500
        sig = PivotSignal(min_amplitude_pct=0.5, point=0.01, digits=2)
        state = MockState()
        
        # Mock DataFrame
        df = pd.DataFrame({
            't': [1, 2, 3, 4, 5],
            'o': [1000.0] * 5,
            'h': [1001.0] * 5,
            'l': [999.0] * 5,
            'c': [1000.0] * 5
        })
        
        sig.calculate(df, state)
        self.assertIsNotNone(state.zigzag_engine)
        self.assertEqual(state.zigzag_engine.mp, 5.0) # 500 points * 0.01
        
        # Double the price -> Amplitude should double in points
        df2 = pd.DataFrame({
            't': [6],
            'o': [2000.0],
            'h': [2001.0],
            'l': [1999.0],
            'c': [2000.0]
        })
        # Note: PivotSignal expects a window of data
        df_combined = pd.concat([df, df2]).reset_index(drop=True)
        
        sig.calculate(df_combined, state)
        # Calculation: (2000.0 * 0.5 / 100) / 0.01 = 10 / 0.01 = 1000 points
        self.assertEqual(state.zigzag_engine.mp, 10.0) # 1000 points * 0.01

if __name__ == '__main__':
    unittest.main()
