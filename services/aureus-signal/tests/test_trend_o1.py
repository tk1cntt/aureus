import os
import sys

import pandas as pd
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from engine.signals.trend import TrendSignal


class MockState:
    def __init__(self):
        self.htf_trend = None
        self.obs = []


def _df(close_values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "t": list(range(1, len(close_values) + 1)),
            "c": close_values,
        }
    )


def test_trend_signal_not_enough_data():
    signal = TrendSignal(ema_period=10)
    df = _df([1, 2, 3])
    state = MockState()

    result = signal.calculate(df, state)

    assert result is None
    assert state.htf_trend == "NEUTRAL"


def test_trend_signal_sideways_both_colors():
    signal = TrendSignal(ema_period=5)
    df = _df([100, 100, 100, 100, 100])
    state = MockState()
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BEARISH", "mitigated": False},
        {"ob_type": "BEARISH", "mitigated": False},
    ]

    result = signal.calculate(df, state)

    assert result["tag"] == "htf_trend"
    assert result["value"] == "NEUTRAL"
    assert result["data"]["regime"] == "SIDEWAYS"
    assert result["data"]["green_ob_count"] == 2
    assert result["data"]["red_ob_count"] == 2


def test_trend_signal_bullish_trend():
    signal = TrendSignal(ema_period=5)
    # Price ends at 100, since it's steadily increasing, EMA will be < 100
    df = _df([80, 85, 90, 95, 100])
    state = MockState()
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BULLISH", "mitigated": False},
    ]  # 3 green, 0 red -> diff 3 >= 2

    result = signal.calculate(df, state)

    assert result["value"] == "BULLISH"
    assert result["data"]["regime"] == "TREND_UP"
    assert state.htf_trend == "BULLISH"


def test_trend_signal_bearish_trend():
    signal = TrendSignal(ema_period=5)
    # Price ends at 100, since it's steadily decreasing, EMA will be > 100
    df = _df([120, 115, 110, 105, 100])
    state = MockState()
    state.obs = [
        {"ob_type": "BEARISH", "mitigated": False},
        {"ob_type": "BEARISH", "mitigated": False},
    ]  # 0 green, 2 red -> diff 2 >= 2

    result = signal.calculate(df, state)

    assert result["value"] == "BEARISH"
    assert result["data"]["regime"] == "TREND_DN"


def test_trend_signal_divergence_anti_fomo():
    signal = TrendSignal(ema_period=5)
    # Price < EMA
    df = _df([120, 115, 110, 105, 100])
    state = MockState()
    # But OBs are strongly Bullish! News sweep!
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BULLISH", "mitigated": False},
    ]

    result = signal.calculate(df, state)

    # Should fall back to Neutral because of divergence
    assert result["value"] == "NEUTRAL"
    assert result["data"]["regime"] == "SIDEWAYS"


def test_trend_signal_mitigated_ignored():
    signal = TrendSignal(ema_period=5)
    # Price > EMA
    df = _df([80, 85, 90, 95, 100])
    state = MockState()
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BULLISH", "mitigated": True},  # Ignored
        {"ob_type": "BULLISH", "mitigated": False},
    ]  # 2 active green, 0 red -> diff 2 >= 2

    result = signal.calculate(df, state)

    assert result["value"] == "BULLISH"
    assert result["data"]["green_ob_count"] == 2


def test_trend_signal_weak_trend():
    signal = TrendSignal(ema_period=5)
    # Price > EMA
    df = _df([80, 85, 90, 95, 100])
    state = MockState()
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False},
    ]  # diff 1 < 2 -> weak (NEUTRAL)

    result = signal.calculate(df, state)

    assert result["value"] == "NEUTRAL"


def test_trend_signal_with_precomputed_ema():
    signal = TrendSignal(ema_period=5)
    df = pd.DataFrame(
        {
            "t": [1, 2, 3, 4, 5],
            "c": [100, 100, 100, 100, 100],
            "ema_5": [90, 90, 90, 90, 90],  # Precomputed EMA < Price
        }
    )
    state = MockState()
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False},
        {"ob_type": "BULLISH", "mitigated": False},
    ]

    result = signal.calculate(df, state)
    assert result["value"] == "BULLISH"
