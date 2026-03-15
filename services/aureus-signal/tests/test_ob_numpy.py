import pandas as pd
import numpy as np
import unittest
import sys
import os

# Ensure the engine module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.common.outside_bar import OutsideBarAnalyzer, OrderFormation

class TestOutsideBarNumPy(unittest.TestCase):
    def setUp(self):
        self.analyzer = OutsideBarAnalyzer()
        self.bar_h = 100.0
        self.bar_l = 90.0
        self.candle = pd.Series({
            'h': self.bar_h,
            'l': self.bar_l,
            'o': 95.0,
            'c': 95.0,
            't': 1600000000
        })

    def create_sub_df(self, data):
        return pd.DataFrame(data, columns=['t', 'h', 'l', 'o', 'c'])

    def test_high_first(self):
        # High hit in first candle, Low in second
        df = self.create_sub_df([
            [1600000000, 100.5, 96.0, 97.0, 98.0],
            [1600000060, 98.0, 89.5, 97.0, 92.0]
        ])
        sub_candles = {"M1": df}
        result = self.analyzer.small_tf_logic(self.candle, "H1", "M1", sub_candles)
        self.assertEqual(result, OrderFormation.OFBHighLow)

    def test_low_first(self):
        # Low hit in first candle, High in second
        df = self.create_sub_df([
            [1600000000, 98.0, 89.5, 97.0, 92.0],
            [1600000060, 100.5, 96.0, 97.0, 98.0]
        ])
        sub_candles = {"M1": df}
        result = self.analyzer.small_tf_logic(self.candle, "H1", "M1", sub_candles)
        self.assertEqual(result, OrderFormation.OFBLowHigh)

    def test_both_same_candle(self):
        # Both extremes hit in the same sub-candle
        df = self.create_sub_df([
            [1600000000, 101.0, 89.0, 97.0, 98.0]
        ])
        sub_candles = {"M1": df}
        result = self.analyzer.small_tf_logic(self.candle, "H1", "M1", sub_candles)
        self.assertEqual(result, OrderFormation.OFBErrorFindSmallTF)

    def test_no_hits(self):
        # Neither extreme hit (data gap or error)
        df = self.create_sub_df([
            [1600000000, 99.5, 90.5, 97.0, 98.0]
        ])
        sub_candles = {"M1": df}
        result = self.analyzer.small_tf_logic(self.candle, "H1", "M1", sub_candles)
        self.assertEqual(result, OrderFormation.OFBError)

    def test_multiple_hits_high_wins(self):
        # Multiple candles hit, but first high is earlier than first low
        df = self.create_sub_df([
            [1600000000, 100.5, 96.0, 97.0, 98.0],
            [1600000060, 100.5, 89.5, 97.0, 92.0],
            [1600000120, 98.0, 89.5, 97.0, 92.0]
        ])
        sub_candles = {"M1": df}
        result = self.analyzer.small_tf_logic(self.candle, "H1", "M1", sub_candles)
        self.assertEqual(result, OrderFormation.OFBHighLow)

if __name__ == '__main__':
    unittest.main()
