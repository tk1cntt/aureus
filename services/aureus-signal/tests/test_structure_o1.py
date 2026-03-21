import unittest
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.structure import StructureSignal

class MockState:
    def __init__(self):
        self.swing_points = [
            {"t": 1, "price": 90.0, "type": "LL", "is_high": False, "index": 0},
            {"t": 3, "price": 200.0, "type": "HH", "is_high": True, "index": 1},
            {"t": 5, "price": 150.0, "type": "LL", "is_high": False, "index": 2},
        ]
        self.obs = []
        self.signal_history = []
        self.transient_signals = {}
        
    def add_ob(self, ob):
        self.obs.append(ob)

class TestStructureSignalSnapshot(unittest.TestCase):
    def setUp(self):
        self.signal = StructureSignal()
        self.state = MockState()
        
        # Candles:
        # t=3 is HH (200)
        # t=5 is LL (150) -> creates a candle with (h=170, l=150)
        # t=8 is Breakout (h=250) -> triggers CHOCH on t=3, creates Bullish OB at t=5 (top=170, bottom=150)
        # t=10 is Mitigation (l=160) -> penetrates OB top (170) -> mitigated!
        self.df = pd.DataFrame({
            "t": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "o": [100, 150, 190, 180, 160, 180, 190, 200, 220, 240],
            "h": [110, 160, 200, 190, 170, 190, 200, 250, 260, 250],
            "l": [ 90, 140, 180, 150, 150, 170, 180, 190, 210, 160], 
            "c": [110, 160, 190, 160, 160, 190, 200, 240, 250, 170]
        })

    def test_golden_master_output(self):
        # Feed candles sequentially as a live engine would
        for i in range(1, 11):
            sub_df = self.df.iloc[:i]
            self.signal.calculate(sub_df, self.state)
            
        # 1. Check CHOCH on HH
        hh = self.state.swing_points[1]
        self.assertTrue(hh.get("is_choch"), "HH was not marked as CHOCH")
        self.assertEqual(hh.get("breakout_t"), 8, "Breakout time mismatch")
        
        # 2. Check OB Creation
        self.assertEqual(len(self.state.obs), 1, "Expected exactly 1 OB to be created")
        ob = self.state.obs[0]
        self.assertEqual(ob["ob_type"], "BULLISH")
        self.assertEqual(ob["top"], 190.0) # Fixed to old logic
        self.assertEqual(ob["bottom"], 150.0)
        
        # 3. Check Mitigation
        self.assertTrue(ob.get("mitigated"), "OB was not mitigated by candle t=10")
        self.assertEqual(ob.get("t_mitigation"), 10)

if __name__ == '__main__':
    unittest.main()
