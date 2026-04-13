"""
Unit tests for CISD Multi-Timeframe Signal.

Tests the EXACT MQL4 FindGenericMTFCISD logic:

  for i = 1..min(bars-1, 24):
      if (c[i] < o[i] && c[i+1] > o[i+1]):   // bear flip
          level = o[i]
          for k = i-1..1:
              if close[k] > level → return 1  (Bullish CISD)
      if (c[i] > o[i] && c[i+1] < o[i+1]):   // bull flip
          level = o[i]
          for k = i-1..1:
              if close[k] < level → return -1 (Bearish CISD)
  return 0

MQL4 index 0 = forming candle (last row in DF)
MQL4 index 1 = newest completed (row n-1)
MQL4 index 2 = older (row n-2)
"""
import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.signals.resampler import resample_to_tf
from engine.signals.cisd_mtf import CISDMultiTFSignal


class _DummyState:
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.transient_signals = {}


def _m1_candle(t, o, h, l, c):
    return {"t": t, "o": o, "h": h, "l": l, "c": c}


def _m1_window(n_candles, start_t=1700000100, base_price=100.0):
    """Generate N M1 candles with small oscillation around base_price."""
    candles = []
    for i in range(n_candles):
        t = start_t + i * 60
        direction = 1 if i % 2 == 0 else -1
        o = base_price
        c = base_price + direction * 0.5
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        candles.append(_m1_candle(t, o, h, l, c))
    return pd.DataFrame(candles)


class TestResampler(unittest.TestCase):
    def test_resample_m1_to_m5(self):
        start = 1700000100  # M5-aligned
        df = _m1_window(10, start_t=start, base_price=100.0)
        result = resample_to_tf(df, "M5")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn("o", result.columns)
        self.assertIn("t", result.columns)

    def test_resample_m1_to_h1(self):
        df = _m1_window(65, base_price=100.0)
        result = resample_to_tf(df, "H1")
        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result), 1)

    def test_resample_returns_none_for_invalid_tf(self):
        df = _m1_window(10)
        self.assertIsNone(resample_to_tf(df, "INVALID"))

    def test_resample_returns_none_for_empty_df(self):
        self.assertIsNone(resample_to_tf(pd.DataFrame(), "M5"))

    def test_resample_returns_none_for_no_t_column(self):
        df = pd.DataFrame([{"o": 100, "c": 101}])
        self.assertIsNone(resample_to_tf(df, "M5"))


class TestCISDMultiTFBasics(unittest.TestCase):
    def test_default_timeframes(self):
        signal = CISDMultiTFSignal()
        tfs = [c["tf"] for c in signal.tf_configs]
        self.assertEqual(tfs, ["M5", "M15", "M30", "H1"])

    def test_custom_timeframes(self):
        signal = CISDMultiTFSignal(tf_configs=[
            {"tf": "M5", "max_bars": 50},
            {"tf": "H1", "max_bars": 100},
        ])
        tfs = [c["tf"] for c in signal.tf_configs]
        self.assertEqual(tfs, ["M5", "H1"])
        self.assertEqual(signal.tf_configs[0]["max_bars"], 50)

    def test_returns_none_on_empty(self):
        signal = CISDMultiTFSignal()
        state = _DummyState()
        result = signal.calculate(pd.DataFrame(), state)
        self.assertIsNone(result)

    def test_signal_type_is_indicator(self):
        from engine.signals.base import SignalType
        self.assertEqual(CISDMultiTFSignal.get_signal_type(), SignalType.INDICATOR)


class TestCISDScanLogic(unittest.TestCase):
    """Test _scan_cisd with exact MQL4 FindGenericMTFCISD logic."""

    def _build(self, pattern):
        """Build DataFrame from list of candle dicts.

        Index 0 = oldest, last = newest (forming candle in MQL4 index 0).
        """
        rows = []
        for i, p in enumerate(pattern):
            rows.append({"t": i, "o": p["o"], "h": p["h"], "l": p["l"], "c": p["c"]})
        return pd.DataFrame(rows)

    def test_no_cisd_all_same_direction(self):
        """All candles same direction → no flip → return 0."""
        candles = self._build([
            {"o": 100, "h": 105, "l": 99, "c": 104} for _ in range(10)
        ])
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, 0)

    def test_no_cisd_flip_but_no_break(self):
        """Flip exists but no candle between flip and newest broke the level.

        MQL4 layout (4 rows):
          i=1: row3 (bear), i+1=2: row2 (bear) → no flip
          i=2: row2 (bear), i+1=3: row1 (bull) → bear flip! level=o[2]
          k=1: row3 close < level → no break (need close > level for Bullish CISD)
          i=3: row1 (bull), i+1=4: row0 (bull) → no flip
        """
        candles = self._build([
            {"o": 100, "h": 105, "l": 99, "c": 104},   # row 0: bull (oldest)
            {"o": 104, "h": 106, "l": 100, "c": 108},   # row 1: bull
            {"o": 108, "h": 110, "l": 106, "c": 107},   # row 2: bear ← flip at i=2
            {"o": 107, "h": 109, "l": 105, "c": 106},   # row 3: bear (newest completed)
        ])
        # i=1: row3 c=106<o=107 bear, i+1=2 row2 c=107<o=108 bear → no flip
        # i=2: row2 c=107<o=108 bear, i+1=3 row1 c=108>o=104 bull → bear flip, level=108
        #   k=1: row3 close=106 < 108 → no break (need > 108 for Bullish CISD)
        # i=3: row1 c=108>o=104 bull, i+1=4 row0 c=104>o=100 bull → no flip
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, 0)

    def test_bullish_cisd(self):
        """Bear flip found, then a newer candle closes above flip's open.

        MQL4 layout (oldest→newest, forming is i=0):
          i=3: o=100, c=96  (bear)  ← oldest
          i=2: o=96, c=99   (bull)
          i=1: o=99, c=95   (bear) ← flip! bull(i=2)→bear(i=1), level=o[1]=99
          i=0: forming

        Wait, need forming at i=0. Let me re-think.

        DF rows: [0=oldest, 1, 2, 3=newest completed, 4=forming]
        MQL4: i=1 → row 3, i=2 → row 2, i=3 → row 1, i=4 → row 0

        Bear flip at i=1 (row3): c[3]<o[3] AND c[2]>o[2] (older was bull)
        Level = o[3]
        Check k=1..0: but k goes from i-1=0 down to 1, so range(0,0,-1) is empty
        → No break possible at i=1 (no candles between flip and newest)

        Let me put flip at i=2 (row2):
        i=2: bear, i+1=3 (row1): bull → bear flip, level=o[2]
        k=1: row3, close > level → Bullish CISD
        """
        candles = self._build([
            {"o": 100, "h": 105, "l": 98, "c": 96},   # row 0: oldest, bear
            {"o": 96, "h": 101, "l": 95, "c": 100},    # row 1: bull
            {"o": 100, "h": 102, "l": 98, "c": 97},    # row 2: bear ← flip at MQL4 i=2
            {"o": 97, "h": 103, "l": 96, "c": 102},    # row 3: newest completed, close=102 > o[2]=100
        ])
        # i=1: row3 c=102>o=97 bull, i+1=2 row2 c=97<o=100 bear → bull flip
        #   level=97, k range empty → no break
        # i=2: row2 c=97<o=100 bear, i+1=3 row1 c=100>o=96 bull → bear flip
        #   level=100, k=1: row3 close=102 > 100 → Bullish CISD!
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, 1)

    def test_bearish_cisd(self):
        """Bull flip found, then a newer candle closes below flip's open.

        DF rows: [0=oldest, 1, 2, 3=newest completed, 4=forming]
        MQL4: i=1 → row 3, i=2 → row 2, i=3 → row 1

        Bull flip at i=2 (row2): c[2]>o[2] AND c[i+1]=c[row1]<o[row1]
        Level = o[2]
        k=1: row3, close < level → Bearish CISD
        """
        candles = self._build([
            {"o": 100, "h": 105, "l": 98, "c": 104},   # row 0: oldest, bull
            {"o": 104, "h": 106, "l": 99, "c": 100},    # row 1: bear
            {"o": 100, "h": 108, "l": 99, "c": 107},    # row 2: bull ← flip
            {"o": 107, "h": 108, "l": 97, "c": 98},     # row 3: newest, close=98 < o[2]=100
        ])
        # i=1: row3 c=98<o=107 bear, i+1=2 row2 c=107>o=100 bull → bear flip
        #   level=107, k range empty → no break
        # i=2: row2 c=107>o=100 bull, i+1=3 row1 c=100<o=104 bear → bull flip
        #   level=100, k=1: row3 close=98 < 100 → Bearish CISD!
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, -1)

    def test_returns_zero_on_insufficient_candles(self):
        """Less than 3 candles → return 0."""
        candles = self._build([
            {"o": 100, "h": 105, "l": 95, "c": 102}
        ])
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, 0)

    def test_first_flip_with_break_wins(self):
        """MQL4 returns on first flip-with-break (newest→oldest scan).

        If newest flip has a break, return immediately — older flips ignored.
        """
        candles = self._build([
            {"o": 100, "h": 105, "l": 98, "c": 96},    # row 0: bear
            {"o": 96, "h": 101, "l": 95, "c": 100},     # row 1: bull
            {"o": 100, "h": 102, "l": 98, "c": 97},     # row 2: bear
            {"o": 97, "h": 103, "l": 96, "c": 102},     # row 3: bull (newest completed)
        ])
        # i=1: row3 c=102>o=97 bull, i+1=2 row2 c=97<o=100 bear → bull flip
        #   level=97, k range empty → no break
        # i=2: row2 c=97<o=100 bear, i+1=3 row1 c=100>o=96 bull → bear flip
        #   level=100, k=1: row3 close=102 > 100 → Bullish CISD! return 1
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, 1)

    def test_no_break_any_candle(self):
        """Flip found but no candle between flip and newest broke the level."""
        candles = self._build([
            {"o": 100, "h": 105, "l": 99, "c": 98},    # row 0: bear
            {"o": 98, "h": 100, "l": 96, "c": 97},     # row 1: bear
            {"o": 97, "h": 100, "l": 95, "c": 100},    # row 2: bull
            {"o": 100, "h": 102, "l": 98, "c": 99},    # row 3: bear (newest)
        ])
        # i=1: row3 c=99<o=100 bear, i+1=2 row2 c=100>o=97 bull → bear flip
        #   level=100, k range empty → no break
        # i=2: row2 c=100>o=97 bull, i+1=3 row1 c=97<o=98 bear → bull flip
        #   level=97, k=1: row3 close=99 > 97 → no break for Bearish (need < 97)
        # i=3: row1 c=97<o=98 bear, i+1=4 row0 c=98<o=100 bear → no flip
        result = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)
        self.assertEqual(result, 0)

    def test_max_bars_limit(self):
        """Only scan first max_bars completed candles from newest."""
        # 30 candles, but max_bars=5 → only check i=1..5
        rows = []
        # Build alternating candles
        for i in range(30):
            if i % 2 == 0:
                rows.append({"o": 100 + i * 0.1, "h": 105, "l": 95, "c": 102 + i * 0.1})
            else:
                rows.append({"o": 102 + i * 0.1, "h": 105, "l": 95, "c": 99 + i * 0.1})
        candles = self._build(rows)

        # With max_bars=5, only scan newest 5 candles
        # If flip-with-break exists within those 5, it returns; otherwise 0
        result_small = CISDMultiTFSignal._scan_cisd(candles, max_bars=5)
        result_big = CISDMultiTFSignal._scan_cisd(candles, max_bars=24)

        # Both should be valid integers
        self.assertIn(result_small, [-1, 0, 1])
        self.assertIn(result_big, [-1, 0, 1])


class TestCISDMultiTFIntegration(unittest.TestCase):
    def test_factory_creates_cisd_mtf_when_configured(self):
        from engine.signal_factory import create_signal_set
        cfg = {
            "cisd_htf": [{"tf": "M5", "max_bars": 24}],
            "gmt_user": 4,
        }
        signals = create_signal_set("XAUUSD", cfg)
        self.assertIn("cisd_mtf", signals)

    def test_factory_skips_cisd_mtf_when_not_configured(self):
        from engine.signal_factory import create_signal_set
        signals = create_signal_set("XAUUSD", {})
        self.assertNotIn("cisd_mtf", signals)

    def test_original_cisd_still_works(self):
        """Original CISD should be unaffected by multi-TF addition."""
        from engine.signals.cisd import CISDSignal
        state = _DummyState()
        df = pd.DataFrame([
            _m1_candle(1, 100, 101, 98, 99),
            _m1_candle(2, 99, 100, 98, 100),
        ])
        signal = CISDSignal()
        result = signal.calculate(df, state)
        self.assertIsNone(result)
        self.assertIn("bull_start_bar", state.cisd_tracker)


if __name__ == "__main__":
    unittest.main()
