import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.tpo_strategy import tpo_strategy_tags_from_candidates


def _candidate(setup, side, valid=True, score=0.75):
    return {
        "setup": setup,
        "side": side,
        "valid": valid,
        "score": score,
        "entry_zone": [100.0, 101.0],
        "invalidation": 99.0,
        "reasons": [f"{setup} {side} reason"],
    }


def test_valid_tpo_candidates_emit_approved_tags():
    cases = [
        ("va_rejection", "long", "tpo_va_rejection_bull"),
        ("va_rejection", "short", "tpo_va_rejection_bear"),
        ("va_breakout_acceptance", "long", "tpo_va_breakout_bull"),
        ("va_breakout_acceptance", "short", "tpo_va_breakout_bear"),
        ("trend_pullback", "long", "tpo_trend_pullback_bull"),
        ("trend_pullback", "short", "tpo_trend_pullback_bear"),
    ]

    for setup, side, expected_tag in cases:
        result = tpo_strategy_tags_from_candidates([_candidate(setup, side)])

        assert result["tags"] == [expected_tag]
        assert result["suppressed"] is False
        assert result["debug"][0]["tag"] == expected_tag
        assert result["debug"][0]["reasons"] == [f"{setup} {side} reason"]


def test_invalid_unknown_missing_side_and_low_score_emit_no_tags():
    candidates = [
        _candidate("va_rejection", "long", valid=False),
        _candidate("va_rejection", None),
        _candidate("unknown", "long"),
        _candidate("trend_pullback", "sideways"),
        _candidate("va_breakout_acceptance", "short", score=0.74),
    ]

    result = tpo_strategy_tags_from_candidates(candidates, min_score=0.75)

    assert result["tags"] == []
    assert result["suppressed"] is False
    assert [item["status"] for item in result["debug"]] == [
        "invalid",
        "missing_side",
        "unknown_mapping",
        "unknown_mapping",
        "below_min_score",
    ]


def test_conflicting_bull_and_bear_batch_suppresses_tags():
    result = tpo_strategy_tags_from_candidates([
        _candidate("va_rejection", "long", score=0.9),
        _candidate("trend_pullback", "short", score=0.8),
    ])

    assert result["tags"] == []
    assert result["suppressed"] is True
    assert result["reasons"] == ["conflicting_tpo_sides"]
    assert [item["tag"] for item in result["debug"]] == [
        "tpo_va_rejection_bull",
        "tpo_trend_pullback_bear",
    ]
