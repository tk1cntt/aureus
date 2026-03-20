import unittest
import pandas as pd
import numpy as np
import sys
import os


# Mock necessary for EMASignal
class MockState:
    def __init__(self):
        self.emas = {}


# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.signals.ema import EMASignal


class TestEMAOptimization(unittest.TestCase):
    def setUp(self):
        # Create deterministic dummy data: 100 candles
        np.random.seed(42)
        data = {
            't': np.arange(100),
            'c': np.random.uniform(2000, 2100, 100)
        }
        self.df = pd.DataFrame(data)
        self.period = 21
        self.signal = EMASignal(self.period)

    def test_o1_vs_pandas(self):
        """Verify that O(1) incremental calculation matches Pandas ewm output."""
        state = MockState()

        # 1. Initial Warmup (using batch ewm)
        # We need at least 'period' candles for the current implementation to start calculating
        warmup_df = self.df.iloc[:self.period + 1]
        res_warmup = self.signal.calculate(warmup_df, state)

        self.assertIsNotNone(res_warmup)
        ema_warmup = state.emas[self.period]['current']
        self.assertIsNotNone(ema_warmup)

        # 2. Sequential Calculation (Incremental O(1))
        for i in range(self.period + 1, 100):
            current_df = self.df.iloc[:i + 1]
            res = self.signal.calculate(current_df, state)
            self.assertIsNotNone(res)

            # Compare with ground truth (Pandas ewm on whole series)
            ground_truth = current_df['c'].ewm(span=self.period, adjust=False).mean().iloc[-1]
            incremental_val = state.emas[self.period]['current']

            self.assertAlmostEqual(
                incremental_val,
                ground_truth,
                places=7,
                msg=f"Mismatch at index {i}: Incremental={incremental_val}, Pandas={ground_truth}",
            )

    def test_fallback_when_cached_state_missing_current_key(self):
        """Malformed cache should trigger deterministic batch fallback instead of crashing."""
        state = MockState()
        state.emas[self.period] = {"prev": 0.0, "slope": 0.0}  # missing 'current'

        current_df = self.df.iloc[:self.period + 2]
        res = self.signal.calculate(current_df, state)

        self.assertIsNotNone(res)
        self.assertIn(self.period, state.emas)
        self.assertIn("current", state.emas[self.period])

        expected = current_df['c'].ewm(span=self.period, adjust=False).mean().iloc[-1]
        self.assertAlmostEqual(state.emas[self.period]["current"], expected, places=7)

    def test_no_data(self):
        """Verify handling of empty DataFrame."""
        state = MockState()
        res = self.signal.calculate(pd.DataFrame(), state)
        self.assertIsNone(res)


if __name__ == '__main__':
    unittest.main()
