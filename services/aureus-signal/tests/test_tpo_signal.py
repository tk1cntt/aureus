import os
import sys

import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.tpo import TPOSignal


class MockState:
    pass


def _build_m1_df(minutes: int = 3000, start_ts: int = 1700000000) -> pd.DataFrame:
    rows = []
    for i in range(minutes):
        t = start_ts + (i * 60)
        base = 2000.0 + ((i % 200) * 0.1)
        rows.append(
            {
                "t": t,
                "o": base,
                "h": base + 0.3,
                "l": base - 0.3,
                "c": base + (0.05 if i % 2 == 0 else -0.05),
                "v": 100 + i,
            }
        )
    return pd.DataFrame(rows)


def test_tpo_signal_returns_required_blocks_and_fields():
    df = _build_m1_df(minutes=3500)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    res = sig.calculate(df, state)

    assert res is not None
    assert res["tag"] == "tpo"
    for key in ("tpo_d1", "tpo_h1", "tpo_m30"):
        assert key in res["value"]
        block = res["value"][key]
        assert block is not None
        assert set(block.keys()) == {"POC", "VAH", "VAL"}
        assert block["VAL"] <= block["POC"] <= block["VAH"]


def test_tpo_signal_returns_none_blocks_when_data_insufficient():
    # very short window so chưa đủ 2 nến đóng cho D1/H1/M30
    df = _build_m1_df(minutes=10)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    res = sig.calculate(df, state)

    assert res is not None
    assert res["value"]["tpo_d1"] is None
    assert res["value"]["tpo_h1"] is None
    assert res["value"]["tpo_m30"] is None


def test_tpo_poc_tiebreak_is_deterministic():
    # Synthetic session where two bins share max count.
    # Tie-break should be deterministic and stable across calls.
    data = [
        {"t": 1700000000, "o": 100.0, "h": 100.2, "l": 100.0, "c": 100.1, "v": 1},
        {"t": 1700000060, "o": 100.2, "h": 100.4, "l": 100.2, "c": 100.3, "v": 1},
        {"t": 1700000120, "o": 100.0, "h": 100.2, "l": 100.0, "c": 100.1, "v": 1},
        {"t": 1700000180, "o": 100.2, "h": 100.4, "l": 100.2, "c": 100.3, "v": 1},
    ]
    session_df = pd.DataFrame(data)

    sig = TPOSignal(value_area_pct=0.7, tick_size=0.2)

    p1 = sig._build_profile(session_df)
    p2 = sig._build_profile(session_df)

    assert p1 is not None
    assert p2 is not None
    assert p1 == p2
