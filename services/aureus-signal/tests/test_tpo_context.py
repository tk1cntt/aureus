import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.base import SignalType
from engine.signals.tpo import TPOSignal
from engine.signals.tpo_context import TPOContextBuilder


TRADE_TAGS = {
    "tpo_va_rejection_bull",
    "tpo_va_rejection_bear",
    "tpo_va_breakout_bull",
    "tpo_va_breakout_bear",
    "tpo_trend_pullback_bull",
    "tpo_trend_pullback_bear",
}


def _block(poc=100.0, vah=105.0, val=95.0):
    return {
        "POC": poc,
        "VAH": vah,
        "VAL": val,
        "shape": "D",
        "shape_confidence_pct": 76.5,
        "shape_scores_pct": {"D": 76.5, "B": 10.0, "p": 8.0, "b": 5.5},
    }


def _value(**overrides):
    value = {
        "tpo_d1": _block(),
        "tpo_h1": _block(poc=200.0, vah=210.0, val=190.0),
        "tpo_m30": _block(poc=300.0, vah=315.0, val=285.0),
    }
    value.update(overrides)
    return value


def test_tpo_context_price_location_above_vah_and_va_width():
    context = TPOContextBuilder(tick_size=0.1).build(_value(), close=106.0)

    d1 = context["timeframes"]["D1"]
    assert d1["price_location"] == "above_vah"
    assert d1["va_width"] == 10.0


def test_tpo_context_price_location_below_val():
    context = TPOContextBuilder(tick_size=0.1).build(_value(), close=94.0)

    assert context["timeframes"]["D1"]["price_location"] == "below_val"


def test_tpo_context_price_location_near_poc_takes_precedence():
    context = TPOContextBuilder(tick_size=0.1, near_poc_ticks=2.0).build(_value(), close=100.15)

    assert context["timeframes"]["D1"]["price_location"] == "near_poc"


def test_tpo_context_missing_timeframe_blocks_return_none_without_crash():
    context = TPOContextBuilder().build(_value(tpo_d1=None, tpo_h1=None, tpo_m30=None), close=100.0)

    assert context["timeframes"] == {"D1": None, "H1": None, "M30": None}
    assert context["bias"] == {"d1": "neutral"}


def test_tpo_context_keeps_tpo_indicator_invariant_and_emits_no_trade_tags():
    context = TPOContextBuilder().build(_value(), close=100.0)

    assert TPOSignal.signal_type == SignalType.INDICATOR
    assert context.get("tag") is None
    assert TRADE_TAGS.isdisjoint(str(context))
