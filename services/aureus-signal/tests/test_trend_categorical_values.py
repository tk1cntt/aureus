import os
import sys
from types import SimpleNamespace

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.signals.trend import TrendSignal


def _state():
    return SimpleNamespace(htf_trend="BULLISH", market_regime="TREND_UP", emas={})


def test_latest_categorical_ema_value_does_not_raise():
    signal = TrendSignal(ema_period=3)
    state = _state()
    df = pd.DataFrame(
        {
            "t": [1, 2, 3],
            "c": [100.0, 101.0, 102.0],
            "ema_3": [99.0, 100.0, "LOW"],
            "ema_21": [98.0, 99.0, 100.0],
            "ema_55": [97.0, 98.0, 99.0],
        }
    )

    result = signal.calculate(df, state)

    assert result is None
    assert state.htf_trend == "NEUTRAL"


def test_categorical_ema_is_not_interpreted_as_numeric_trend_data():
    signal = TrendSignal(ema_period=3)
    state = _state()
    df = pd.DataFrame(
        {
            "t": [1, 2, 3],
            "c": [100.0, 101.0, 102.0],
            "ema_3": [99.0, 100.0, "LOW"],
            "ema_21": [98.0, 99.0, 100.0],
            "ema_55": [97.0, 98.0, 99.0],
        }
    )

    result = signal.calculate(df, state)

    assert result is None
    assert state.htf_trend == "NEUTRAL"


def test_numeric_trend_input_keeps_payload_shape():
    signal = TrendSignal(ema_period=3)
    state = _state()
    df = pd.DataFrame(
        {
            "t": [1, 2, 3],
            "c": [100.0, 101.0, 102.0],
            "ema_3": [99.0, 100.0, 101.0],
            "ema_21": [98.0, 99.0, 100.0],
            "ema_55": [97.0, 98.0, 99.0],
        }
    )

    result = signal.calculate(df, state)

    assert result is not None
    assert result["tag"] == "htf_trend"
    assert result["value"] in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert "regime" in result["data"]
    assert "ema_ref" in result["data"]
    assert "ema_score" in result["data"]
