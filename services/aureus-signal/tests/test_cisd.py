"""
Unit tests for CISD (Change in State of Delivery) Signal.

CISD detects when a flip FAILS — price breaks back through the flip candle's open.

Bear→Bull flip + close < flip_open → Bearish CISD
Bull→Bear flip + close > flip_open → Bullish CISD
"""
import os
import sys
import unittest

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.signals.cisd import CISDSignal


class _DummyState:
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.transient_signals = {}


def _df(rows):
    return pd.DataFrame(rows)


def _candle(t, o, h, l, c):
    return {"t": t, "o": o, "h": h, "l": l, "c": c}


def _calculate_streaming(signal, candles, state):
    """Simulate streaming: process candles one by one."""
    for i in range(2, len(candles) + 1):
        window = _df(candles[:i])
        signal.calculate(window, state)
    return state


class TestCISDSignalBasics(unittest.TestCase):
    def test_returns_none_when_fewer_than_2_candles(self):
        state = _DummyState()
        df = _df([_candle(1, 100, 101, 99, 100)])
        self.assertIsNone(CISDSignal().calculate(df, state))

    def test_returns_none_when_data_missing(self):
        state = _DummyState()
        df = _df([{"t": 1, "c": 100}, {"t": 2, "c": 101}])
        self.assertIsNone(CISDSignal().calculate(df, state))


class TestBearishCISD(unittest.TestCase):
    """Bear→Bull flip, then price drops below flip open → Bearish CISD."""

    def test_bear_to_bull_flip_starts_tracking(self):
        state = _DummyState()
        df = _df([
            _candle(1, 100, 101, 98, 99),   # bear
            _candle(2, 99, 100, 98, 100),    # bull flip
        ])
        self.assertIsNone(CISDSignal().calculate(df, state))
        self.assertIn("bull_start_bar", state.cisd_tracker)
        self.assertEqual(state.cisd_tracker["bull_track_price"], 99.0)

    def test_bearish_cisd_emits_streaming(self):
        """Streaming mode: bear→bull flip, then later close < flip open."""
        signal = CISDSignal()
        candles = [
            _candle(1, 100, 101, 98, 99),    # bear
            _candle(2, 99, 100, 98, 100),     # bull flip, open=99
            _candle(3, 100, 102, 99, 101),    # bull continues
            _candle(4, 101, 103, 99, 102),    # bull continues
            _candle(5, 102, 103, 98, 97),     # bear flip, close=97 < 99 → Bearish CISD
        ]
        # Streaming: check bar by bar
        state = _DummyState()
        last_result = None
        for i in range(2, len(candles) + 1):
            window = _df(candles[:i])
            last_result = signal.calculate(window, state)

        self.assertIsNotNone(last_result)
        self.assertEqual(last_result["direction"], "BEARISH")
        self.assertEqual(last_result["tag"], "cisd_bear")
        self.assertEqual(last_result["track_price"], 99.0)
        self.assertIn("cisd_bear", state.transient_signals)

    def test_respects_min_length(self):
        signal = CISDSignal(min_length=5, max_length=100)
        candles = [
            _candle(1, 100, 101, 98, 99),
            _candle(2, 99, 100, 98, 100),
            _candle(3, 100, 102, 99, 101),
            _candle(4, 101, 103, 99, 102),
            _candle(5, 102, 103, 98, 97),
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        # Span = 5-2 = 3 < min_length=5 → no emit
        self.assertNotIn("cisd_bear", state.transient_signals)

    def test_respects_max_length(self):
        signal = CISDSignal(min_length=0, max_length=2)
        candles = [
            _candle(1, 100, 101, 98, 99),
            _candle(2, 99, 100, 98, 100),
            _candle(3, 100, 102, 99, 101),
            _candle(4, 101, 103, 99, 102),
            _candle(5, 102, 103, 97, 96),  # span = 5-2=3 > max=2 → expired
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        self.assertNotIn("cisd_bear", state.transient_signals)

    def test_value_is_positive(self):
        signal = CISDSignal()
        candles = [
            _candle(1, 100, 101, 98, 99),
            _candle(2, 99, 100, 98, 100),
            _candle(3, 100, 102, 99, 101),
            _candle(4, 101, 103, 95, 94),  # close=94, track=99, value=5
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        result = state.transient_signals.get("cisd_bear")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"], 99.0 - 94.0)
        self.assertGreater(result["value"], 0)


class TestBullishCISD(unittest.TestCase):
    """Bull→Bear flip, then price rises above flip open → Bullish CISD."""

    def test_bull_to_bear_flip_starts_tracking(self):
        state = _DummyState()
        df = _df([
            _candle(1, 99, 101, 98, 100),   # bull
            _candle(2, 100, 101, 99, 99),    # bear flip
        ])
        self.assertIsNone(CISDSignal().calculate(df, state))
        self.assertIn("bear_start_bar", state.cisd_tracker)
        self.assertEqual(state.cisd_tracker["bear_track_price"], 100.0)

    def test_bullish_cisd_emits_streaming(self):
        signal = CISDSignal()
        candles = [
            _candle(1, 99, 101, 98, 100),    # bull
            _candle(2, 100, 101, 99, 99),     # bear flip, open=100
            _candle(3, 99, 100, 97, 98),      # bear continues
            _candle(4, 98, 100, 96, 97),      # bear continues
            _candle(5, 97, 102, 96, 103),     # bull flip, close=103 > 100 → Bullish CISD
        ]
        state = _DummyState()
        last_result = None
        for i in range(2, len(candles) + 1):
            last_result = signal.calculate(_df(candles[:i]), state)

        self.assertIsNotNone(last_result)
        self.assertEqual(last_result["direction"], "BULLISH")
        self.assertEqual(last_result["tag"], "cisd_bull")
        self.assertEqual(last_result["track_price"], 100.0)
        self.assertIn("cisd_bull", state.transient_signals)

    def test_respects_min_length(self):
        signal = CISDSignal(min_length=5, max_length=100)
        candles = [
            _candle(1, 99, 101, 98, 100),
            _candle(2, 100, 101, 99, 99),
            _candle(3, 99, 100, 97, 98),
            _candle(4, 98, 100, 96, 97),
            _candle(5, 97, 102, 96, 103),
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        self.assertNotIn("cisd_bull", state.transient_signals)

    def test_respects_max_length(self):
        signal = CISDSignal(min_length=0, max_length=2)
        candles = [
            _candle(1, 99, 101, 98, 100),
            _candle(2, 100, 101, 99, 99),
            _candle(3, 99, 100, 97, 98),
            _candle(4, 98, 100, 96, 97),
            _candle(5, 97, 105, 96, 104),  # span=3 > max=2
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        self.assertNotIn("cisd_bull", state.transient_signals)

    def test_value_is_positive(self):
        signal = CISDSignal()
        candles = [
            _candle(1, 99, 101, 98, 100),
            _candle(2, 100, 101, 99, 99),
            _candle(3, 99, 100, 97, 98),
            _candle(4, 98, 106, 96, 105),  # close=105, track=100, value=5
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        result = state.transient_signals.get("cisd_bull")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"], 105.0 - 100.0)
        self.assertGreater(result["value"], 0)


class TestCISDEdgeCases(unittest.TestCase):
    def test_equal_open_close_no_flip(self):
        signal = CISDSignal()
        state = _DummyState()
        df = _df([
            _candle(1, 100, 101, 98, 100),   # doji
            _candle(2, 100, 101, 99, 99),    # bear
        ])
        self.assertIsNone(signal.calculate(df, state))

    def test_flip_candle_does_not_trigger_self(self):
        signal = CISDSignal()
        state = _DummyState()
        df = _df([
            _candle(1, 100, 101, 98, 99),   # bear
            _candle(2, 99, 100, 98, 100),    # bull flip
        ])
        self.assertIsNone(signal.calculate(df, state))

    def test_multiple_cisd_in_sequence(self):
        signal = CISDSignal()
        candles = [
            # Phase 1: Bullish CISD
            _candle(1, 99, 101, 98, 100),      # bull
            _candle(2, 100, 101, 99, 99),       # bear flip, open=100
            _candle(3, 99, 100, 97, 98),        # bear continues
            _candle(4, 98, 100, 96, 97),        # bear continues
            _candle(5, 97, 103, 96, 102),       # close 102>100 → Bullish CISD

            # Phase 2: Bearish CISD (fresh start)
            _candle(6, 102, 103, 98, 97),       # bear
            _candle(7, 97, 99, 96, 98),         # bull flip, open=97
            _candle(8, 98, 100, 97, 99),        # bull continues
            _candle(9, 99, 101, 98, 100),       # bull continues
            _candle(10, 100, 101, 95, 94),      # close 94<97 → Bearish CISD
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)

        self.assertIn("cisd_bull", state.transient_signals)
        self.assertIn("cisd_bear", state.transient_signals)

    def test_new_flip_invalidates_old_tracking(self):
        signal = CISDSignal()
        candles = [
            _candle(1, 99, 101, 98, 100),   # bull
            _candle(2, 100, 101, 99, 99),    # bear flip
            _candle(3, 99, 100, 98, 96),     # bear continues
            _candle(4, 96, 98, 95, 97),      # bear
            _candle(5, 97, 99, 96, 98),      # bull flip → invalidate bear
        ]
        state = _DummyState()
        for i in range(2, len(candles) + 1):
            signal.calculate(_df(candles[:i]), state)
        self.assertNotIn("bear_start_bar", state.cisd_tracker)
        self.assertIn("bull_start_bar", state.cisd_tracker)


class TestCISDSignalType(unittest.TestCase):
    def test_signal_type_is_event(self):
        from engine.signals.base import SignalType
        self.assertEqual(CISDSignal.get_signal_type(), SignalType.EVENT)


if __name__ == "__main__":
    unittest.main()
