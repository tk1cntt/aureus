import unittest
import pandas as pd
import numpy as np
import sys
import os

# Mock necessary for ATRSignal
class MockState:
    def __init__(self):
        self.atr = None
        self.last_candle = None

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.signals.atr import ATRSignal

class TestATROptimization(unittest.TestCase):
    def setUp(self):
        # Create dummy data: 100 candles
        np.random.seed(42)
        data = {
            't': np.arange(100),
            'h': np.random.uniform(2050, 2100, 100),
            'l': np.random.uniform(2000, 2049, 100),
            'c': np.random.uniform(2000, 2100, 100)
        }
        self.df = pd.DataFrame(data)
        self.period = 14
        self.signal = ATRSignal(self.period)

    def test_o1_vs_pandas(self):
        """Verify that O(1) incremental ATR calculation matches Pandas ewm output."""
        state = MockState()
        
        # 1. Initial Warmup (using batch)
        warmup_df = self.df.iloc[:self.period + 1]
        res_warmup = self.signal.calculate(warmup_df, state)
        
        self.assertIsNotNone(res_warmup)
        atr_warmup = state.atr
        
        # 2. Sequential Calculation (Incremental O(1))
        for i in range(self.period + 1, 100):
            current_df = self.df.iloc[:i+1]
            res = self.signal.calculate(current_df, state)
            
            # Ground Truth calculation (Pandas ewm (Wilder RMA) on whole series)
            h = current_df['h']
            l = current_df['l']
            pc = current_df['c'].shift(1)
            tr = pd.concat([h-l, abs(h-pc), abs(l-pc)], axis=1).max(axis=1)
            ground_truth = tr.ewm(alpha=1/self.period, adjust=False).mean().iloc[-1]
            
            incremental_val = state.atr
            
            self.assertAlmostEqual(incremental_val, ground_truth, places=7, 
                                 msg=f"Mismatch at index {i}: Incremental={incremental_val}, Pandas={ground_truth}")

    def test_no_data(self):
        """Verify handling of empty DataFrame."""
        state = MockState()
        res = self.signal.calculate(pd.DataFrame(), state)
        self.assertIsNone(res)

if __name__ == '__main__':
    unittest.main()
