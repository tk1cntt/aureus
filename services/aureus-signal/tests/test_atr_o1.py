import unittest
import pandas as pd
import numpy as np
import sys
import os
from typing import cast


class MockState:
    def __init__(self):
        self.atr = None
        self.last_candle = None


# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.signals.atr import ATRSignal


def _build_tr_series(df: pd.DataFrame) -> pd.Series:
    h = df['h']
    l = df['l']
    pc = df['c'].shift(1)
    return pd.concat([h - l, abs(h - pc), abs(l - pc)], axis=1).max(axis=1)


class TestATROptimization(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        data = {
            't': np.arange(100),
            'h': np.random.uniform(2050, 2100, 100),
            'l': np.random.uniform(2000, 2049, 100),
            'c': np.random.uniform(2000, 2100, 100),
        }
        self.df = pd.DataFrame(data)
        self.period = 14
        self.signal = ATRSignal(self.period)

    def test_o1_vs_pandas(self):
        """Verify O(1) incremental ATR matches full-series Wilder (ewm) output."""
        state = MockState()

        warmup_df = self.df.iloc[: self.period + 1]
        res_warmup = self.signal.calculate(warmup_df, state)

        self.assertIsNotNone(res_warmup)
        self.assertIsNotNone(state.atr)

        for i in range(self.period + 1, len(self.df)):
            current_df = self.df.iloc[: i + 1]
            res = self.signal.calculate(current_df, state)
            self.assertIsNotNone(res)
            self.assertIsNotNone(state.atr)

            ground_truth = _build_tr_series(current_df).ewm(alpha=1 / self.period, adjust=False).mean().iloc[-1]
            self.assertAlmostEqual(
                cast(float, state.atr),
                float(ground_truth),
                places=7,
                msg=f"Mismatch at index {i}: incremental={state.atr}, pandas={ground_truth}",
            )

    def test_insufficient_candles_returns_none(self):
        state = MockState()

        for n in [0, 1, self.period - 1, self.period]:
            subset = self.df.iloc[:n]
            res = self.signal.calculate(subset, state)
            self.assertIsNone(res, msg=f"Expected None for len(df)={n}")

    def test_deterministic_repeatability_for_same_series(self):
        subset = self.df.iloc[: self.period + 10]

        state_a = MockState()
        state_b = MockState()
        sig_a = ATRSignal(self.period)
        sig_b = ATRSignal(self.period)

        outputs_a = []
        outputs_b = []

        for i in range(self.period + 1, len(subset) + 1):
            curr = subset.iloc[:i]
            out_a = sig_a.calculate(curr, state_a)
            out_b = sig_b.calculate(curr, state_b)
            outputs_a.append(None if out_a is None else out_a['value'])
            outputs_b.append(None if out_b is None else out_b['value'])

        self.assertEqual(outputs_a, outputs_b)
        self.assertIsNotNone(state_a.atr)
        self.assertIsNotNone(state_b.atr)
        self.assertAlmostEqual(cast(float, state_a.atr), cast(float, state_b.atr), places=12)

    def test_state_carry_incremental_formula_parity(self):
        state = MockState()
        warmup_df = self.df.iloc[: self.period + 1]
        self.signal.calculate(warmup_df, state)

        self.assertIsNotNone(state.atr)
        prev_atr = cast(float, state.atr)
        next_df = self.df.iloc[: self.period + 2]
        next_candle = next_df.iloc[-1]
        prev_close = float(next_df.iloc[-2]['c'])
        tr_now = max(
            float(next_candle['h']) - float(next_candle['l']),
            abs(float(next_candle['h']) - prev_close),
            abs(float(next_candle['l']) - prev_close),
        )
        expected_next = (prev_atr * (self.period - 1) + tr_now) / self.period

        res = self.signal.calculate(next_df, state)

        self.assertIsNotNone(res)
        self.assertIsNotNone(state.atr)
        self.assertAlmostEqual(cast(float, state.atr), expected_next, places=12)

    def test_output_contract_contains_expected_fields(self):
        state = MockState()
        curr_df = self.df.iloc[: self.period + 1]
        res = self.signal.calculate(curr_df, state)

        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res['tag'], f'atr_{self.period}')
        self.assertIn('value', res)
        self.assertEqual(res['t'], int(curr_df.iloc[-1]['t']))


if __name__ == '__main__':
    unittest.main()
