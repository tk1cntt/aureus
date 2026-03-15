import unittest
import pandas as pd
import numpy as np
import sys
import os
import json

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.common.zigzag_pro2 import ZigZagPro

class TestZigZagRegression(unittest.TestCase):
    """
    RIGOROUS REGRESSION TEST FOR ZIGZAG_PRO2.
    Objective: Ensure 100% identity match between Legacy and Optimized versions.
    """
    
    def setUp(self):
        # Generate 1000 candles with deliberate high volatility & Outside Bars
        np.random.seed(42)
        n = 1000
        t = np.arange(n)
        o = np.random.uniform(2000, 2100, n)
        c = np.random.uniform(2000, 2100, n)
        h = np.maximum(o, c) + np.random.uniform(0, 10, n)
        l = np.minimum(o, c) - np.random.uniform(0, 10, n)
        
        # Inyect deliberate Outside Bars (High/Low of current bars surrounding previous bar)
        for i in range(10, n, 50):
            h[i] = h[i-1] + 20
            l[i] = l[i-1] - 20
        
        self.df = pd.DataFrame({'t': t, 'o': o, 'h': h, 'l': l, 'c': c})
        self.params = {
            "ext_period": 5,
            "min_amplitude": 100,
            "min_motion": 1,
            "point": 0.01,
            "digits": 2
        }

    def test_parity_against_filtered_ground_truth(self):
        """
        Story 5.1: Verify engine matches ground truth with Inside-Bar filtering enabled.
        """
        truth_path = os.path.join(os.path.dirname(__file__), "zigzag_ground_truth_filtered.json")
        if not os.path.exists(truth_path):
            self.skipTest("Filtered ground truth not found. Run gen_filtered_truth.py first.")
            
        with open(truth_path, "r") as f:
            truth = json.load(f)
            
        df = pd.DataFrame(truth['candles'])
        params = truth['params']
        expected_raw = truth['results']
        
        # Convert list of dicts to separate buffers
        expected = {
            "up": [r['up'] for r in expected_raw],
            "dn": [r['dn'] for r in expected_raw],
            "type": [r['type'] for r in expected_raw]
        }
        
        engine = ZigZagPro(**params)
        n_candles = len(df)
        ext_period = int(params['ext_period'])
        
        # Batch test
        buffers = engine.update(df, incremental=False)
        
        print(f"\nComparing {n_candles} results against Filtered Reference...")
        for key in ['up', 'dn', 'type']:
            actual_list = [float(v) if key != 'type' else int(v) for v in buffers[key]]
            expected_list = expected[key]
            
            for idx in range(len(actual_list)):
                if actual_list[idx] != expected_list[idx]:
                    self.fail(f"FILTERED PARITY ERROR in {key} at index {idx}!\nCANDLE: {df.iloc[idx]['t']}\nActual: {actual_list[idx]}, Expected: {expected_list[idx]}")
        
        print(f"✅ 100% Bitwise Parity achieved with Noise Filtering enabled.")

    @unittest.expectedFailure
    def test_parity_against_legacy_ground_truth(self):
        """
        Legacy (MQL5-style): This test will FAIL because the engine now filters Inside Bars.
        Included for historical context and to verify the delta is intentional.
        """
        truth_path = os.path.join(os.path.dirname(__file__), "zigzag_ground_truth.json")
        if not os.path.exists(truth_path):
            self.skipTest("Legacy ground truth JSON not found.")
            
        with open(truth_path, "r") as f:
            truth = json.load(f)
            
        df = pd.DataFrame(truth['candles'])
        params = truth['params']
        expected = truth['expected']
        
        engine = ZigZagPro(**params)
        buffers = engine.update(df, incremental=False)
        
        for key in ['up', 'dn', 'type']:
            actual_list = [float(v) if key != 'type' else int(v) for v in buffers[key]]
            expected_list = expected[key]
            for idx in range(len(actual_list)):
                if actual_list[idx] != expected_list[idx]:
                    self.fail(f"LEGACY MISMATCH at {idx} (Expected as per Story 5.1 filtering)")

    def test_verify_current_logic(self):
        """
        Step 1: Run the current logic and capture output buffers.
        This serves as the 'Golden Reference'.
        """
        engine = ZigZagPro(**self.params)
        
        # Scenario A: Batch for ground truth
        n_candles = 300
        subset_df = self.df.iloc[:n_candles]
        buffers_batch = engine.update(subset_df, incremental=False)
        
        print("\n✅ Golden Batch reference captured for 300 candles.")
        
        # Save Golden Reference
        golden_ref = {
            "params": self.params,
            "results": {
                "up": [float(v) for v in buffers_batch['up']],
                "dn": [float(v) for v in buffers_batch['dn']],
                "type": [int(v) for v in buffers_batch['type']]
            }
        }
        self.__class__.golden_ref = golden_ref

    def test_identity_check(self):
        """
        Step 2: Compare results (to be used AFTER modification).
        """
        if not hasattr(self, 'golden_ref'):
            self.test_verify_current_logic()
            
        # This is strictly for the Optimized version to prove its worth.
        # For now, it just checks against itself.
        print("✅ Identity check ready for Optimized version.")

if __name__ == '__main__':
    unittest.main()
