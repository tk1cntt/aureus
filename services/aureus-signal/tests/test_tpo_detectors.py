import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.tpo_detectors import TrendPullbackDetector, VABreakoutAcceptanceDetector, VARejectionDetector


def _tf(
    poc=100.0,
    vah=105.0,
    val=95.0,
    shape="D",
    distance_to_poc_ticks=0.0,
    distance_to_vah_ticks=0.0,
    distance_to_val_ticks=0.0,
    poc_shift="flat",
):
    return {
        "poc": poc,
        "vah": vah,
        "val": val,
        "shape": shape,
        "shape_confidence_pct": 80.0,
        "price_location": "near_poc" if abs(distance_to_poc_ticks) <= 2.0 else "inside_value_area",
        "distance_to_poc_ticks": distance_to_poc_ticks,
        "distance_to_vah_ticks": distance_to_vah_ticks,
        "distance_to_val_ticks": distance_to_val_ticks,
        "poc_shift": poc_shift,
        "va_width": vah - val,
    }


def _context(d1_bias="neutral", h1=None, m30=None, d1=None, history_guard=None):
    context = {
        "timeframes": {
            "D1": d1 if d1 is not None else _tf(poc=100.0, vah=110.0, val=90.0),
            "H1": h1 if h1 is not None else _tf(poc=100.0, vah=106.0, val=96.0),
            "M30": m30 if m30 is not None else _tf(poc=101.0, vah=107.0, val=97.0),
        },
        "bias": {"d1": d1_bias},
    }
    if history_guard is not None:
        context["history_guard"] = history_guard
    return context


def test_va_rejection_detects_long_reclaim_from_val():
    candidate = VARejectionDetector().detect(
        _context(d1_bias="bullish", h1=_tf(poc=100.0, vah=106.0, val=96.0, shape="b")),
        previous_close=95.5,
        current_close=98.5,
    )

    assert candidate["setup"] == "va_rejection"
    assert candidate["valid"] is True
    assert candidate["side"] == "long"
    assert candidate["entry_zone"] == [96.0, 98.5]
    assert candidate["invalidation"] == 96.0
    assert candidate["score"] > 0.0
    assert candidate["reasons"]
    assert any("reclaimed VAL" in reason for reason in candidate["reasons"])


def test_va_rejection_detects_short_reject_from_vah():
    candidate = VARejectionDetector().detect(
        _context(
            d1_bias="bearish",
            h1=_tf(poc=100.0, vah=110.0, val=96.0),
            m30=_tf(poc=101.0, vah=107.0, val=97.0, shape="p"),
        ),
        previous_close=108.0,
        current_close=103.0,
    )

    assert candidate["valid"] is True
    assert candidate["side"] == "short"
    assert candidate["entry_zone"] == [103.0, 107.0]
    assert candidate["invalidation"] == 107.0
    assert candidate["reasons"]
    assert any("rejected VAH" in reason for reason in candidate["reasons"])


def test_va_rejection_missing_required_context_is_invalid():
    context = _context()
    context["timeframes"]["M30"] = None

    candidate = VARejectionDetector().detect(context, previous_close=95.0, current_close=98.0)

    assert candidate == {
        "setup": "va_rejection",
        "side": None,
        "valid": False,
        "score": 0.0,
        "entry_zone": None,
        "invalidation": None,
        "reasons": ["missing required TPO context: M30"],
    }


def test_va_rejection_stale_or_missing_history_guard_is_invalid():
    stale = VARejectionDetector().detect(
        _context(history_guard={"is_stale": True, "stale_timeframes": ["H1"], "missing_timeframes": []}),
        previous_close=95.0,
        current_close=98.0,
    )
    missing = VARejectionDetector().detect(
        _context(history_guard={"is_stale": False, "stale_timeframes": [], "missing_timeframes": ["M30"]}),
        previous_close=95.0,
        current_close=98.0,
    )

    assert stale["valid"] is False
    assert stale["side"] is None
    assert stale["reasons"]
    assert "history guard stale" in stale["reasons"][0]
    assert missing["valid"] is False
    assert missing["side"] is None
    assert missing["reasons"]
    assert "history guard missing" in missing["reasons"][0]


def test_va_rejection_conflicting_d1_bias_is_invalid():
    long_conflict = VARejectionDetector().detect(
        _context(d1_bias="bearish"), previous_close=95.0, current_close=98.0
    )
    short_conflict = VARejectionDetector().detect(
        _context(d1_bias="bullish"), previous_close=108.0, current_close=103.0
    )

    assert long_conflict["valid"] is False
    assert long_conflict["side"] is None
    assert any("conflicts with D1 bearish bias" in reason for reason in long_conflict["reasons"])
    assert short_conflict["valid"] is False
    assert short_conflict["side"] is None
    assert any("conflicts with D1 bullish bias" in reason for reason in short_conflict["reasons"])


def test_va_rejection_shape_is_not_sole_gate():
    supportive_shape_without_price_relation = VARejectionDetector().detect(
        _context(d1_bias="neutral", h1=_tf(shape="b")), previous_close=97.0, current_close=98.0
    )
    valid_price_relation_with_neutral_shape = VARejectionDetector().detect(
        _context(d1_bias="neutral", h1=_tf(shape="D")), previous_close=95.0, current_close=98.0
    )

    assert supportive_shape_without_price_relation["valid"] is False
    assert supportive_shape_without_price_relation["side"] is None
    assert supportive_shape_without_price_relation["reasons"]
    assert valid_price_relation_with_neutral_shape["valid"] is True
    assert valid_price_relation_with_neutral_shape["side"] == "long"
    assert valid_price_relation_with_neutral_shape["reasons"]
    assert any("shape" in reason for reason in valid_price_relation_with_neutral_shape["reasons"])


def test_va_breakout_acceptance_detects_long_above_vah():
    candidate = VABreakoutAcceptanceDetector().detect(
        _context(d1_bias="bullish", h1=_tf(poc=104.0, vah=106.0, val=96.0, shape="b", poc_shift="up")),
        current_close=107.0,
        acceptance_closes=[106.5, 108.0],
    )

    assert candidate["setup"] == "va_breakout_acceptance"
    assert candidate["valid"] is True
    assert candidate["side"] == "long"
    assert candidate["entry_zone"] == [106.0, 107.0]
    assert candidate["invalidation"] == 106.0
    assert candidate["reasons"]
    assert any("accepted above VAH" in reason for reason in candidate["reasons"])


def test_va_breakout_acceptance_detects_short_below_val():
    candidate = VABreakoutAcceptanceDetector().detect(
        _context(d1_bias="bearish", m30=_tf(poc=98.0, vah=107.0, val=97.0, shape="p", poc_shift="down")),
        current_close=96.0,
        acceptance_closes=[96.5, 95.5],
    )

    assert candidate["valid"] is True
    assert candidate["side"] == "short"
    assert candidate["entry_zone"] == [96.0, 97.0]
    assert candidate["invalidation"] == 97.0
    assert candidate["reasons"]
    assert any("accepted below VAL" in reason for reason in candidate["reasons"])


def test_va_breakout_acceptance_invalid_context_conflict_and_shape_only():
    missing = _context()
    missing["timeframes"]["D1"] = None
    stale = VABreakoutAcceptanceDetector().detect(
        _context(history_guard={"is_stale": True, "stale_timeframes": ["M30"], "missing_timeframes": []}),
        current_close=108.0,
        acceptance_closes=[108.5],
    )
    long_conflict = VABreakoutAcceptanceDetector().detect(
        _context(d1_bias="bearish", h1=_tf(vah=106.0)), current_close=107.0, acceptance_closes=[107.5]
    )
    poc_conflict = VABreakoutAcceptanceDetector().detect(
        _context(d1_bias="bullish", h1=_tf(vah=106.0, poc_shift="down")),
        current_close=107.0,
        acceptance_closes=[107.5],
    )
    failed_acceptance = VABreakoutAcceptanceDetector().detect(
        _context(d1_bias="bullish", h1=_tf(vah=106.0)), current_close=107.0, acceptance_closes=[105.5]
    )
    shape_only = VABreakoutAcceptanceDetector().detect(
        _context(d1_bias="neutral", h1=_tf(shape="b")), current_close=104.0, acceptance_closes=[104.5]
    )

    assert VABreakoutAcceptanceDetector().detect(missing, current_close=108.0, acceptance_closes=[108.5])["valid"] is False
    assert stale["valid"] is False
    assert long_conflict["valid"] is False
    assert any("conflicts with D1 bearish bias" in reason for reason in long_conflict["reasons"])
    assert poc_conflict["valid"] is False
    assert any("POC shift down conflicts" in reason for reason in poc_conflict["reasons"])
    assert failed_acceptance["valid"] is False
    assert shape_only["valid"] is False
    assert shape_only["reasons"]


def test_trend_pullback_detects_long_with_h1_pullback_and_m30_reclaim():
    candidate = TrendPullbackDetector().detect(
        _context(
            d1_bias="neutral-up",
            h1=_tf(poc=100.0, vah=106.0, val=96.0, distance_to_val_ticks=1.0),
            m30=_tf(poc=99.0, vah=103.0, val=98.0, shape="b"),
        ),
        previous_close=97.5,
        current_close=99.0,
    )

    assert candidate["setup"] == "trend_pullback"
    assert candidate["valid"] is True
    assert candidate["side"] == "long"
    assert candidate["entry_zone"] == [96.0, 99.0]
    assert candidate["invalidation"] == 96.0
    assert candidate["reasons"]
    assert any("M30 reclaimed VAL" in reason for reason in candidate["reasons"])


def test_trend_pullback_detects_short_with_h1_pullback_and_m30_reject():
    candidate = TrendPullbackDetector().detect(
        _context(
            d1_bias="neutral-down",
            h1=_tf(poc=100.0, vah=106.0, val=96.0, distance_to_vah_ticks=1.0),
            m30=_tf(poc=104.0, vah=103.0, val=98.0, shape="p"),
        ),
        previous_close=104.0,
        current_close=102.0,
    )

    assert candidate["valid"] is True
    assert candidate["side"] == "short"
    assert candidate["entry_zone"] == [102.0, 106.0]
    assert candidate["invalidation"] == 106.0
    assert candidate["reasons"]
    assert any("M30 rejected VAH" in reason for reason in candidate["reasons"])


def test_trend_pullback_invalid_context_conflict_missing_legs_and_shape_only():
    missing = _context()
    missing["timeframes"]["H1"] = None
    stale = TrendPullbackDetector().detect(
        _context(history_guard={"is_stale": False, "stale_timeframes": [], "missing_timeframes": ["H1"]}),
        previous_close=97.0,
        current_close=99.0,
    )
    long_conflict = TrendPullbackDetector().detect(
        _context(d1_bias="bearish", h1=_tf(distance_to_val_ticks=1.0), m30=_tf(val=98.0)),
        previous_close=97.0,
        current_close=99.0,
    )
    missing_pullback = TrendPullbackDetector().detect(
        _context(d1_bias="bullish", h1=_tf(poc=120.0, val=110.0, distance_to_poc_ticks=20.0, distance_to_val_ticks=20.0), m30=_tf(val=98.0)),
        previous_close=97.0,
        current_close=99.0,
    )
    missing_m30 = TrendPullbackDetector().detect(
        _context(d1_bias="bullish", h1=_tf(distance_to_val_ticks=1.0), m30=_tf(val=95.0)),
        previous_close=97.0,
        current_close=99.0,
    )
    shape_only = TrendPullbackDetector().detect(
        _context(d1_bias="neutral", h1=_tf(shape="b"), m30=_tf(shape="b")), previous_close=100.0, current_close=101.0
    )

    assert TrendPullbackDetector().detect(missing, previous_close=97.0, current_close=99.0)["valid"] is False
    assert stale["valid"] is False
    assert long_conflict["valid"] is False
    assert any("conflicts with D1 bearish bias" in reason for reason in long_conflict["reasons"])
    assert missing_pullback["valid"] is False
    assert any("missing H1 pullback" in reason for reason in missing_pullback["reasons"])
    assert missing_m30["valid"] is False
    assert any("missing M30 confirmation" in reason for reason in missing_m30["reasons"])
    assert shape_only["valid"] is False
    assert shape_only["reasons"]
