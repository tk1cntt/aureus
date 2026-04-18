import pandas as pd
import numpy as np
import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.structure import StructureSignal
from engine.state import SymbolState

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


class TestStructureArrayPathParity(unittest.TestCase):
    def setUp(self):
        self.signal = StructureSignal()
        self.df = pd.DataFrame(
            {
                "t": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "o": [100, 150, 190, 180, 160, 180, 190, 200, 220, 240],
                "h": [110, 160, 200, 190, 170, 190, 200, 250, 260, 250],
                "l": [90, 140, 180, 150, 150, 170, 180, 190, 210, 160],
                "c": [110, 160, 190, 160, 160, 190, 200, 240, 250, 170],
            }
        )

    def _build_state(self):
        state = SymbolState("EURUSD")
        state.swing_points = [
            {"t": 1, "price": 90.0, "type": "LL", "is_high": False, "index": 0, "is_choch": False},
            {"t": 3, "price": 200.0, "type": "HH", "is_high": True, "index": 1, "is_choch": False},
            {"t": 5, "price": 150.0, "type": "LL", "is_high": False, "index": 2, "is_choch": False},
        ]
        return state

    def test_ob_and_swing_contract_kept_after_array_optimization(self):
        old_state = self._build_state()
        new_state = self._build_state()

        old_result = self.signal._calculate_old_path(self.df, old_state)
        new_result = self.signal._calculate_optimized_path(self.df, new_state)

        self.assertEqual(old_result, new_result)
        self.assertEqual(old_state.obs, new_state.obs)
        self.assertEqual(old_state.swing_points, new_state.swing_points)
        self.assertEqual(old_state.transient_signals.get("ob_state"), new_state.transient_signals.get("ob_state"))


if __name__ == '__main__':
    unittest.main()
