import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.tpo_detectors import VARejectionDetector


def _tf(poc=100.0, vah=105.0, val=95.0, shape="D", distance_to_poc_ticks=0.0):
    return {
        "poc": poc,
        "vah": vah,
        "val": val,
        "shape": shape,
        "shape_confidence_pct": 80.0,
        "price_location": "near_poc" if abs(distance_to_poc_ticks) <= 2.0 else "inside_value_area",
        "distance_to_poc_ticks": distance_to_poc_ticks,
        "distance_to_vah_ticks": 0.0,
        "distance_to_val_ticks": 0.0,
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
        _context(d1_bias="bearish", m30=_tf(poc=101.0, vah=107.0, val=97.0, shape="p")),
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
