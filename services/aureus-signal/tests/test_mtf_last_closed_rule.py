import pandas as pd

from engine.mtf_snapshot import get_last_closed_candle


def test_get_last_closed_candle_uses_previous_row_for_tf_gt_m1():
    df = pd.DataFrame(
        [
            {"t": 0, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.4},
            {"t": 60, "o": 100.4, "h": 101.4, "l": 99.4, "c": 100.8},
            {"t": 120, "o": 100.8, "h": 101.8, "l": 99.8, "c": 101.2},
            {"t": 180, "o": 101.2, "h": 102.2, "l": 100.2, "c": 101.6},
            {"t": 240, "o": 101.6, "h": 102.6, "l": 100.6, "c": 102.0},
            {"t": 300, "o": 102.0, "h": 103.0, "l": 101.0, "c": 102.4},
            {"t": 360, "o": 102.4, "h": 103.4, "l": 101.4, "c": 102.8},
        ]
    )

    candle = get_last_closed_candle(df, "M5")

    assert candle is not None
    assert candle["t"] == 240


def test_get_last_closed_candle_does_not_wait_for_new_htf_close_every_m1_tick():
    df = pd.DataFrame(
        [
            {"t": 0, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.4},
            {"t": 60, "o": 100.4, "h": 101.4, "l": 99.4, "c": 100.8},
            {"t": 120, "o": 100.8, "h": 101.8, "l": 99.8, "c": 101.2},
            {"t": 180, "o": 101.2, "h": 102.2, "l": 100.2, "c": 101.6},
            {"t": 240, "o": 101.6, "h": 102.6, "l": 100.6, "c": 102.0},
            {"t": 300, "o": 102.0, "h": 103.0, "l": 101.0, "c": 102.4},
            {"t": 360, "o": 102.4, "h": 103.4, "l": 101.4, "c": 102.8},
            {"t": 420, "o": 102.8, "h": 103.8, "l": 101.8, "c": 103.2},
        ]
    )

    candle = get_last_closed_candle(df, "M5")

    assert candle is not None
    assert candle["t"] == 240


def test_get_last_closed_candle_returns_none_when_not_enough_rows_for_closed_htf():
    df = pd.DataFrame(
        [
            {"t": 0, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.4},
            {"t": 60, "o": 100.4, "h": 101.4, "l": 99.4, "c": 100.8},
            {"t": 120, "o": 100.8, "h": 101.8, "l": 99.8, "c": 101.2},
        ]
    )

    candle = get_last_closed_candle(df, "M5")

    assert candle is None
