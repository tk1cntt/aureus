import pandas as pd

from engine.mtf_snapshot import compute_candle_color, build_mtf_candle_color_map


def test_compute_candle_color_returns_bullish_uppercase():
    row = {"o": 100.0, "c": 101.0}
    assert compute_candle_color(row, digits=2) == "BULLISH"


def test_compute_candle_color_returns_bearish_uppercase():
    row = {"o": 101.0, "c": 100.0}
    assert compute_candle_color(row, digits=2) == "BEARISH"


def test_compute_candle_color_returns_doji_after_digits_normalize():
    row = {"o": 100.0041, "c": 100.0049}
    assert compute_candle_color(row, digits=2) == "DOJI"


def test_build_mtf_candle_color_map_contains_required_keys():
    m1_df = pd.DataFrame(
        [
            {"t": 0, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.2},
            {"t": 60, "o": 100.2, "h": 101.2, "l": 99.2, "c": 100.6},
            {"t": 120, "o": 100.6, "h": 101.6, "l": 99.6, "c": 100.9},
            {"t": 180, "o": 100.9, "h": 101.9, "l": 99.9, "c": 101.3},
            {"t": 240, "o": 101.3, "h": 102.3, "l": 100.3, "c": 101.6},
            {"t": 300, "o": 101.6, "h": 102.6, "l": 100.6, "c": 101.9},
            {"t": 360, "o": 101.9, "h": 102.9, "l": 100.9, "c": 102.3},
        ]
    )

    result = build_mtf_candle_color_map(m1_df, digits=2)

    assert "candle_color_d1" in result
    assert "candle_color_h1" in result
    assert "candle_color_m30" in result
    assert "candle_color_m15" in result
    assert "candle_color_m5" in result


def test_build_mtf_candle_color_map_null_first_for_missing_tf_data():
    m1_df = pd.DataFrame(
        [
            {"t": 0, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.2},
            {"t": 60, "o": 100.2, "h": 101.2, "l": 99.2, "c": 100.6},
            {"t": 120, "o": 100.6, "h": 101.6, "l": 99.6, "c": 100.9},
        ]
    )

    result = build_mtf_candle_color_map(m1_df, digits=2)

    assert result["candle_color_d1"] is None
    assert result["candle_color_h1"] is None
    assert result["candle_color_m30"] is None
    assert result["candle_color_m15"] is None
    assert result["candle_color_m5"] is None
