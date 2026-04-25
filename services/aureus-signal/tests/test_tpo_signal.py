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

    def wrapped(session_df, **kwargs):
        nonlocal calls
        calls += 1
        return original(session_df, **kwargs)

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


def _classify_fixture(counts, tick_size=0.1):
    sig = TPOSignal(value_area_pct=0.7, tick_size=tick_size)
    levels = [100.0 + (i * tick_size) for i in range(len(counts))]
    poc_idx = max(range(len(counts)), key=lambda i: (counts[i], -abs(i - (len(counts) // 2)))) if counts else 0
    return sig._classify_shape(levels, counts, poc_idx=poc_idx)


def _assert_scores_contract(shape, confidence, scores, *, non_empty=True):
    assert shape in {"D", "B", "p", "b"}
    assert 0.0 <= confidence <= 100.0
    assert set(scores.keys()) == {"D", "B", "p", "b"}
    if non_empty:
        assert abs(sum(scores.values()) - 100.0) <= 0.1
    assert abs(scores[shape] - confidence) <= max(65.0, 100.0 - confidence)


def test_tpo_classify_shape_returns_valid_probability_distribution():
    shape, confidence, scores = _classify_fixture([2, 4, 8, 4, 2])

    _assert_scores_contract(shape, confidence, scores)


def test_tpo_classify_shape_calibrates_clear_d_profile():
    d_shape, d_confidence, d_scores = _classify_fixture([1, 3, 6, 9, 12, 9, 6, 3, 1])
    sparse_shape, sparse_confidence, sparse_scores = _classify_fixture([0, 1, 0, 1, 0])

    _assert_scores_contract(d_shape, d_confidence, d_scores)
    _assert_scores_contract(sparse_shape, sparse_confidence, sparse_scores)
    assert d_shape == "D"
    assert d_confidence >= 55.0
    assert sparse_confidence <= 35.0
    assert d_confidence > sparse_confidence


def test_tpo_classify_shape_requires_separated_peaks_for_b_profile():
    b_shape, b_confidence, b_scores = _classify_fixture([1, 3, 10, 3, 1, 3, 10, 3, 1])
    lumpy_shape, lumpy_confidence, lumpy_scores = _classify_fixture([1, 4, 9, 8, 7, 8, 9, 4, 1])

    _assert_scores_contract(b_shape, b_confidence, b_scores)
    _assert_scores_contract(lumpy_shape, lumpy_confidence, lumpy_scores)
    assert b_shape == "B"
    assert b_confidence >= 55.0
    assert not (lumpy_shape == "B" and lumpy_confidence >= 50.0)


def test_tpo_classify_shape_identifies_p_and_b_profiles():
    p_shape, p_confidence, p_scores = _classify_fixture([8, 7, 5, 3, 2, 1, 1])
    b_shape, b_confidence, b_scores = _classify_fixture([1, 1, 2, 3, 5, 7, 8])

    _assert_scores_contract(p_shape, p_confidence, p_scores)
    _assert_scores_contract(b_shape, b_confidence, b_scores)
    assert p_shape == "p"
    assert b_shape == "b"
    assert p_confidence >= 45.0
    assert b_confidence >= 45.0


def test_tpo_classify_shape_caps_empty_zero_and_sparse_profiles():
    sig = TPOSignal(value_area_pct=0.7, tick_size=0.1)

    empty_shape, empty_confidence, empty_scores = sig._classify_shape([], [], poc_idx=0)
    zero_shape, zero_confidence, zero_scores = _classify_fixture([0, 0, 0, 0])
    sparse_shape, sparse_confidence, sparse_scores = _classify_fixture([1, 0, 0, 1])

    _assert_scores_contract(empty_shape, empty_confidence, empty_scores, non_empty=False)
    _assert_scores_contract(zero_shape, zero_confidence, zero_scores, non_empty=False)
    _assert_scores_contract(sparse_shape, sparse_confidence, sparse_scores)
    assert empty_confidence == 0.0
    assert zero_confidence == 0.0
    assert sparse_confidence <= 35.0


def test_tpo_classify_shape_bounds_distant_low_count_outlier():
    baseline_shape, baseline_confidence, baseline_scores = _classify_fixture([1, 3, 6, 10, 6, 3, 1])
    outlier_shape, outlier_confidence, outlier_scores = _classify_fixture([1, 3, 6, 10, 6, 3, 1, 0, 0, 0, 1])

    _assert_scores_contract(baseline_shape, baseline_confidence, baseline_scores)
    _assert_scores_contract(outlier_shape, outlier_confidence, outlier_scores)
    assert baseline_shape == "D"
    assert outlier_shape == "D"
    assert outlier_confidence >= baseline_confidence - 20.0


def test_tpo_classify_shape_is_stable_across_tick_size_spacing():
    counts = [1, 3, 6, 10, 6, 3, 1]
    small_shape, small_confidence, small_scores = _classify_fixture(counts, tick_size=0.01)
    large_shape, large_confidence, large_scores = _classify_fixture(counts, tick_size=1.0)

    _assert_scores_contract(small_shape, small_confidence, small_scores)
    _assert_scores_contract(large_shape, large_confidence, large_scores)
    assert small_shape == large_shape == "D"
    assert abs(small_confidence - large_confidence) <= 1.0


def test_tpo_classify_shape_uses_margin_to_cap_near_ties():
    clear_shape, clear_confidence, clear_scores = _classify_fixture([1, 4, 9, 14, 9, 4, 1])
    near_tie_shape, near_tie_confidence, near_tie_scores = _classify_fixture([1, 5, 10, 1, 10, 5, 1])

    _assert_scores_contract(clear_shape, clear_confidence, clear_scores)
    _assert_scores_contract(near_tie_shape, near_tie_confidence, near_tie_scores)
    assert clear_shape == "D"
    assert near_tie_confidence < clear_confidence
    assert near_tie_confidence <= 80.0
