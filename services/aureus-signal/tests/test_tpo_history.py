import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.tpo_history import TPOHistoryStore


TRADE_TAGS = {
    "tpo_va_rejection_bull",
    "tpo_va_rejection_bear",
    "tpo_va_breakout_bull",
    "tpo_va_breakout_bear",
    "tpo_trend_pullback_bull",
    "tpo_trend_pullback_bear",
}


def _block(t, poc=100.0, vah=105.0, val=95.0):
    return {
        "t": t,
        "POC": poc,
        "VAH": vah,
        "VAL": val,
        "shape": "D",
        "shape_confidence_pct": 80.0,
    }


def test_tpo_history_append_dedup_and_bounds_per_timeframe():
    history = TPOHistoryStore(max_length=2)

    assert history.append("d1", _block(1, poc=100.0)) is True
    assert history.append("D1", _block(1, poc=101.0)) is False
    assert history.append("D1", _block(2, poc=102.0)) is True
    assert history.append("D1", _block(3, poc=103.0)) is True

    snapshots = history.snapshots("D1")
    assert [item["t"] for item in snapshots] == [2, 3]
    assert snapshots[-1]["va_width"] == 10.0


def test_tpo_history_ignores_invalid_blocks_without_mutating():
    history = TPOHistoryStore(max_length=2)

    assert history.append("H1", {"t": 1, "POC": 100.0}) is False
    assert history.append("H4", _block(1)) is False
    assert history.append("H1", _block(1)) is True

    assert len(history.snapshots("H1")) == 1
    assert history.snapshots("H4") == []


def test_tpo_history_poc_shift_uses_latest_two_snapshots_with_tolerance():
    history = TPOHistoryStore(max_length=5, tick_size=0.1)

    assert history.poc_shift("M30") == "unknown"
    history.append("M30", _block(1, poc=100.0))
    assert history.poc_shift("M30") == "unknown"
    history.append("M30", _block(2, poc=100.04))
    assert history.poc_shift("M30") == "flat"
    history.append("M30", _block(3, poc=100.2))
    assert history.poc_shift("M30") == "up"
    history.append("M30", _block(4, poc=99.8))
    assert history.poc_shift("M30") == "down"


def test_tpo_history_va_width_change_returns_latest_minus_previous():
    history = TPOHistoryStore(max_length=5)

    assert history.va_width_change("H1") is None
    history.append("H1", _block(1, vah=105.0, val=95.0))
    assert history.va_width_change("H1") is None
    history.append("H1", _block(2, vah=108.0, val=96.0))

    assert history.va_width_change("H1") == 2.0


def test_tpo_history_freshness_guard_flags_missing_and_stale_timeframes():
    history = TPOHistoryStore(max_length=5)
    history.append("D1", _block(100))
    history.append("H1", _block(95))

    status = history.freshness_status(now=120, max_age=10)

    assert status["is_stale"] is True
    assert status["stale_timeframes"] == ["D1", "H1", "M30"]
    assert status["missing_timeframes"] == ["M30"]

    history.append("D1", _block(120))
    history.append("H1", _block(120))
    history.append("M30", _block(120))

    assert history.freshness_status(now=120, max_age=10) == {
        "is_stale": False,
        "stale_timeframes": [],
        "missing_timeframes": [],
    }


def test_tpo_history_does_not_create_trade_tags():
    history = TPOHistoryStore(max_length=2)
    history.append("D1", _block(1))

    assert TRADE_TAGS.isdisjoint(str(history.snapshots("D1")))
