from types import SimpleNamespace

import pandas as pd

from engine.snapshot_utils import build_snapshot


def _make_state():
    return SimpleNamespace(
        symbol="XAUUSD",
        atr=1.2,
        emas={21: {"current": 1.0}, 34: {"current": 1.1}, 55: {"current": 1.2}, 89: {"current": 1.3}, 100: {"current": 1.4}, 200: {"current": 1.5}},
        vol_sma_20=1500.0,
        htf_trend="BULLISH",
        market_regime="SIDEWAYS",
        current_session="LONDON",
        transient_signals={},
        obs=[],
        swing_points=[],
        strategy_progress={},
        aci=55,
        sentiment="NEUTRAL",
        narrative="ok",
    )


def test_null_first_when_htf_data_missing():
    state = _make_state()
    candle = {"t": 1700000000, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "symbol": "XAUUSD"}
    small_df = pd.DataFrame(
        [
            {"t": 0, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "v": 1},
            {"t": 60, "o": 100.1, "h": 100.3, "l": 99.9, "c": 100.2, "v": 2},
            {"t": 120, "o": 100.2, "h": 100.4, "l": 100.0, "c": 100.3, "v": 3},
        ]
    )

    snap = build_snapshot(state, candle, m1_df=small_df, digits=2)

    assert snap["candle_color_d1"] is None
    assert snap["candle_color_h1"] is None
    assert snap["candle_color_m30"] is None
    assert snap["candle_color_m15"] is None
    assert snap["candle_color_m5"] is None

    assert snap["bb_m1"] is None
    assert snap["bb_m5"] is None
    assert snap["bb_m15"] is None
    assert snap["bb_m30"] is None
    assert snap["bb_h1"] is None


def test_no_placeholder_values_for_missing_data():
    state = _make_state()
    candle = {"t": 1700000000, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "symbol": "XAUUSD"}
    df = pd.DataFrame([{"t": 0, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "v": 1}])

    snap = build_snapshot(state, candle, m1_df=df, digits=2)

    for key in ["candle_color_d1", "candle_color_h1", "candle_color_m30", "candle_color_m15", "candle_color_m5"]:
        assert snap[key] is None
        assert snap[key] != "UNKNOWN"

    for key in ["bb_m1", "bb_m5", "bb_m15", "bb_m30", "bb_h1"]:
        assert snap[key] is None
        assert snap[key] != 0
