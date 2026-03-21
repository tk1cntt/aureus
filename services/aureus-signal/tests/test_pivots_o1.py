import unittest
import pandas as pd
import sys
import os
import numpy as np

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.pivots import PivotSignal

class MockState:
    def __init__(self):
        self.swing_points = []
        self.tracking_vars = {}
        self.zigzag_engine = None

class TestPivotSignalDefensive(unittest.TestCase):
    def setUp(self):
        self.signal = PivotSignal(ext_period=3, min_amplitude=10, min_motion=1, point=1.0, digits=0)

    def test_calculate_with_nan_values(self):
        # Create dataset with NaN
        df = pd.DataFrame({
            "t": [1, 2, 3, 4],
            "o": [100, 100, 100, 100],
            "h": [110, np.nan, 120, 130],
            "l": [90, 85, np.nan, 70],
            "c": [100, 100, 100, 100]
        })
        state = MockState()
        # Should gracefully drop NaN and not crash
        res = self.signal.calculate(df, state, symbol="TEST")
        # Should return None because dropped rows mean len < ext_period (likely won't find confirmed pivot)
        self.assertIsNone(res)

    def test_calculate_with_duplicate_and_unsorted_times(self):
        # Create dirty dataset: out of order and duplicates
        df = pd.DataFrame({
            "t": [4, 1, 3, 2, 4],
            "o": [100, 100, 100, 100, 100],
            "h": [110, 150, 120, 130, 200],
            "l": [90, 85, 95, 70, 80],
            "c": [100, 140, 110, 120, 190]
        })
        state = MockState()
        res = self.signal.calculate(df, state, symbol="TEST")
        # Ensure it doesn't crash. Result might be None or valid pivot.
        self.assertTrue(res is None or isinstance(res, dict))

    def test_state_integrity_fallback(self):
        # Simulate malformed existing state. Fallback handles this inside calculate if valid pivots exist.
        state = MockState()
        state.swing_points = [
            {"t": 10, "price": 100.0, "type": "HH"}, # Missing is_high
            {"t": 20, "price": 120.0}, # Missing type and is_high
            "TRASH STRING" # Total trash
        ]
        
        # Give enough data to create confirmed pivots so execution passes the None returns
        # Using t > 20 so the old points are retained during merge!
        df = pd.DataFrame({
            "t": [30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140],
            "o": [100] * 12,
            "h": [100, 200, 120, 200, 120, 200, 120, 200, 120, 200, 120, 200],
            "l": [90, 50, 90, 50, 90, 50, 90, 50, 90, 50, 90, 50],
            "c": [100] * 12
        })
        
        res = self.signal.calculate(df, state, symbol="TEST")
        
        # In batch mode it might return None. We just assert it processed without crashing.
        self.assertTrue(res is None or isinstance(res, dict))

if __name__ == '__main__':
    unittest.main()
