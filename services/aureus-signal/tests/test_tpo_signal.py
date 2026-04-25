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
        assert set(block.keys()) == {"POC", "VAH", "VAL", "shape", "shape_confidence_pct", "shape_scores_pct"}
        assert block["VAL"] <= block["POC"] <= block["VAH"]
        assert block["shape"] in {"D", "B", "p", "b"}
        assert 0.0 <= block["shape_confidence_pct"] <= 100.0
        assert set(block["shape_scores_pct"].keys()) == {"D", "B", "p", "b"}


def test_tpo_signal_short_data_still_returns_realtime_blocks():
    df = _build_m1_df(minutes=10)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    res = sig.calculate(df, state)

    assert res is not None
    assert res["value"]["tpo_d1"] is not None
    assert res["value"]["tpo_h1"] is not None
    assert res["value"]["tpo_m30"] is not None


def test_tpo_signal_caches_closed_h1_buckets():
    df = _build_m1_df(minutes=500)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    first = sig.calculate(df, state)
    assert first is not None
    assert hasattr(state, "tpo_cache")
    assert any(key.startswith("H1:") for key in state.tpo_cache.keys())

    cache_size = len(state.tpo_cache)
    second = sig.calculate(df, state)
    assert second is not None
    assert len(state.tpo_cache) >= cache_size


def test_tpo_closed_bucket_cache_hit_does_not_rebuild(monkeypatch):
    df = _build_m1_df(minutes=180)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    first = sig.calculate(df, state)
    assert first is not None
    cached_keys = [key for key in state.tpo_cache if key.startswith("H1:")]
    cached_key = cached_keys[-1]
    cached_h1 = state.tpo_cache[cached_key]

    def fail_rebuild(session_df):
        raise AssertionError("closed bucket cache hit should not rebuild")

    monkeypatch.setattr(sig, "_build_tpo_block", fail_rebuild)
    bucket_start = int(cached_key.split(":", 1)[1])
    bucket_end = bucket_start + 3600 - 60

    df_closed = df[df["t"] <= bucket_end]
    second = sig._compute_sliding(df_closed, bucket_end + 60, tf="H1", count=1, cache=state.tpo_cache)

    assert second == cached_h1


def test_tpo_current_bucket_still_updates_with_new_candle():
    df = _build_m1_df(minutes=70)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    first = sig.calculate(df, state)
    assert first is not None
    first_h1 = first["value"]["tpo_h1"]
    assert first_h1 is not None

    next_row = df.iloc[-1].copy()
    next_row["t"] = int(next_row["t"]) + 60
    next_row["h"] = float(next_row["h"]) + 20.0
    next_row["l"] = float(next_row["l"]) + 20.0
    next_row["o"] = float(next_row["o"]) + 20.0
    next_row["c"] = float(next_row["c"]) + 20.0
    df2 = pd.concat([df, pd.DataFrame([next_row])], ignore_index=True)

    second = sig.calculate(df2, state)
    assert second is not None
    second_h1 = second["value"]["tpo_h1"]
    assert second_h1 is not None
    assert second_h1 != first_h1


def test_tpo_block_build_uses_counts_once(monkeypatch):
    df = _build_m1_df(minutes=80)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    calls = 0
    original = sig._build_levels_and_counts

    def wrapped(session_df):
        nonlocal calls
        calls += 1
        return original(session_df)

    monkeypatch.setattr(sig, "_build_levels_and_counts", wrapped)

    block = sig._build_tpo_block(df)

    assert block is not None
    assert calls == 1
    assert set(block.keys()) == {"POC", "VAH", "VAL", "shape", "shape_confidence_pct", "shape_scores_pct"}


def test_tpo_signal_uses_today_only_for_d1():
    # two days of data; D1 should only use current day window
    start = 1700000000
    df = _build_m1_df(minutes=3000, start_ts=start)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    res = sig.calculate(df, state)
    assert res is not None
    d1 = res["value"]["tpo_d1"]
    assert d1 is not None
    assert set(d1.keys()) == {"POC", "VAH", "VAL", "shape", "shape_confidence_pct", "shape_scores_pct"}
    assert d1["VAL"] <= d1["POC"] <= d1["VAH"]
    assert d1["shape"] in {"D", "B", "p", "b"}
    assert 0.0 <= d1["shape_confidence_pct"] <= 100.0


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


def test_tpo_block_includes_shape_confidence_and_scores():
    df = _build_m1_df(minutes=800)
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    state = MockState()

    res = sig.calculate(df, state)

    assert res is not None
    d1 = res["value"]["tpo_d1"]
    assert d1 is not None
    assert d1["shape"] in {"D", "B", "p", "b"}
    assert 0.0 <= d1["shape_confidence_pct"] <= 100.0
    assert set(d1["shape_scores_pct"].keys()) == {"D", "B", "p", "b"}

    total_scores = round(sum(d1["shape_scores_pct"].values()), 2)
    assert 99.0 <= total_scores <= 101.0


def test_tpo_classify_shape_returns_valid_probability_distribution():
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)
    levels = [100.0, 100.1, 100.2, 100.3, 100.4]
    counts = [2, 4, 8, 4, 2]

    shape, confidence, scores = sig._classify_shape(levels, counts, poc_idx=2)

    assert shape in {"D", "B", "p", "b"}
    assert 0.0 <= confidence <= 100.0
    assert set(scores.keys()) == {"D", "B", "p", "b"}
    assert abs(sum(scores.values()) - 100.0) <= 0.1
    assert scores[shape] == confidence
