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
        self.emas = {}
        self.swing_points = []


def _df(close_values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "t": list(range(1, len(close_values) + 1)),
            "c": close_values,
        }
    )


def test_trend_signal_not_enough_data_without_scoring_sources():
    signal = TrendSignal(ema_period=10)
    df = _df([1])
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


def test_hybrid_bullish_turns_without_ema200_fixture():
    signal = TrendSignal(ema_period=200)
    df = pd.DataFrame(
        {
            "t": [1, 2, 3, 4, 5, 6],
            "c": [95, 96, 97, 98, 99, 100],
            "ema_21": [94, 95, 96, 97, 98, 99],
            "ema_55": [92, 93, 94, 95, 96, 97],
        }
    )
    state = MockState()
    state.swing_points = [{"label": "HH"}, {"label": "HL"}]
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False, "quality": 0.9, "body_ratio": 0.8, "status": "CLEAN_BREAKOUT", "t_breakout": 6},
        {"ob_type": "BULLISH", "mitigated": False, "quality": 0.8, "body_ratio": 0.7, "status": "ACTIVE", "t_breakout": 6},
    ]

    result = signal.calculate(df, state, choch_up=True)

    assert result["tag"] == "htf_trend"
    assert result["value"] == "BULLISH"
    assert result["data"]["regime"] == "TREND_UP"
    assert "ema_ref" not in result["data"]
    assert "ema200_penalty" not in result["data"]
    assert result["data"]["structure_score"] > 0
    assert result["data"]["ema_score"] > 0
    assert result["data"]["ob_score"] > 0
    assert state.htf_trend == "BULLISH"


def test_hybrid_bearish_turns_without_ema200_alignment():
    signal = TrendSignal(ema_period=200)
    df = pd.DataFrame(
        {
            "t": [1, 2, 3, 4, 5, 6],
            "c": [105, 104, 103, 102, 101, 100],
            "ema_21": [106, 105, 104, 103, 102, 101],
            "ema_55": [108, 107, 106, 105, 104, 103],
        }
    )
    state = MockState()
    state.swing_points = [{"label": "LH"}, {"label": "LL"}]
    state.obs = [
        {"ob_type": "BEARISH", "mitigated": False, "quality": 0.9, "body_ratio": 0.8, "status": "CLEAN_BREAKOUT", "t_breakout": 6},
        {"ob_type": "BEARISH", "mitigated": False, "quality": 0.7, "body_ratio": 0.7, "status": "ACTIVE", "t_breakout": 6},
    ]

    result = signal.calculate(df, state, choch_down=True, stop_hunt_bear=True)

    assert result["value"] == "BEARISH"
    assert result["data"]["regime"] == "TREND_DN"
    assert "ema_ref" not in result["data"]
    assert "ema200_penalty" not in result["data"]
    assert result["data"]["structure_score"] < 0
    assert result["data"]["ema_score"] < 0
    assert result["data"]["ob_score"] < 0


def test_hybrid_opposing_stop_hunt_keeps_false_break_neutral():
    signal = TrendSignal(ema_period=200)
    df = pd.DataFrame(
        {
            "t": [1, 2, 3, 4, 5],
            "c": [96, 97, 98, 99, 100],
            "ema_21": [95, 96, 97, 98, 99],
            "ema_55": [94, 95, 96, 97, 98],
        }
    )
    state = MockState()
    state.swing_points = [{"label": "HH"}, {"label": "HL"}]
    state.obs = [
        {"ob_type": "BULLISH", "mitigated": False, "quality": 0.5, "status": "TOUCHED", "t_breakout": 5},
        {"ob_type": "BEARISH", "mitigated": False, "status": "STOP_HUNT", "t_breakout": 5},
    ]

    result = signal.calculate(df, state, choch_up=True, stop_hunt_bear=True)

    assert result["value"] == "NEUTRAL"
    assert result["data"]["regime"] == "SIDEWAYS"
    assert result["data"]["sweep_score"] < 0


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
    assert result["value"] in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert result["data"]["regime"] in {"TREND_UP", "TREND_DN", "SIDEWAYS"}
    assert result["tag"] == "htf_trend"
    assert result["value"] == "NEUTRAL"
