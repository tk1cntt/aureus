import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signals.tpo_replay import replay_tpo_calibration


FORBIDDEN_MODULE_PREFIXES = (
    "db",
    "prisma",
    "migrations",
    "engine.strategies",
    "engine.execution",
    "engine.dispatch",
    "engine.mt5",
    "journal",
)


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


def _fixture_rows():
    return [
        {
            "regime": "trend",
            "context": _context(
                d1_bias="bullish",
                h1=_tf(poc=100.0, vah=106.0, val=96.0, shape="b", poc_shift="up"),
                m30=_tf(poc=101.0, vah=107.0, val=97.0, shape="D"),
            ),
            "previous_close": 95.5,
            "current_close": 98.5,
            "acceptance_closes": [98.0],
        },
        {
            "regime": "range",
            "context": _context(
                d1_bias="bullish",
                h1=_tf(poc=104.0, vah=106.0, val=96.0, shape="b", poc_shift="up"),
                m30=_tf(poc=101.0, vah=107.0, val=97.0, shape="D"),
            ),
            "previous_close": 107.5,
            "current_close": 107.0,
            "acceptance_closes": [106.5, 108.0],
        },
        {
            "regime": "high_volatility",
            "context": _context(
                d1_bias="bullish",
                h1=_tf(poc=100.0, vah=106.0, val=96.0, shape="D", distance_to_poc_ticks=3.0, distance_to_val_ticks=3.0),
                m30=_tf(poc=100.0, vah=107.0, val=97.0, shape="D"),
            ),
            "previous_close": 100.1,
            "current_close": 100.5,
            "acceptance_closes": [],
        },
        {
            "regime": "low_volatility",
            "context": _context(d1_bias="bearish"),
            "previous_close": 95.0,
            "current_close": 98.0,
            "acceptance_closes": [],
        },
        {
            "regime": "high_volatility",
            "context": _context(
                d1_bias="bearish",
                h1=_tf(poc=100.0, vah=107.0, val=96.0, shape="neutral", distance_to_poc_ticks=1.0),
                m30=_tf(poc=100.0, vah=104.0, val=97.0, shape="p"),
            ),
            "previous_close": 108.0,
            "current_close": 103.0,
            "acceptance_closes": [],
        },
    ]


def test_replay_report_is_deterministic_and_does_not_mutate_input_rows():
    rows = _fixture_rows()
    original_rows = [dict(row, context={**row["context"], "timeframes": dict(row["context"]["timeframes"])}) for row in rows]

    first = replay_tpo_calibration(rows, thresholds=(0.75, 0.85))
    second = replay_tpo_calibration(rows, thresholds=(0.75, 0.85))

    assert first == second
    assert rows == original_rows
    assert first["rows"] == 5
    assert first["candidate_count"] == 15


def test_replay_report_counts_setups_by_side_and_validity():
    report = replay_tpo_calibration(_fixture_rows(), thresholds=(0.75, 0.85))

    assert report["setup_counts"] == {
        "va_rejection": {"long": {"valid": 1, "invalid": 0}, "short": {"valid": 1, "invalid": 0}, "invalid": 3},
        "va_breakout_acceptance": {"long": {"valid": 1, "invalid": 0}, "short": {"valid": 0, "invalid": 0}, "invalid": 4},
        "trend_pullback": {"long": {"valid": 1, "invalid": 0}, "short": {"valid": 1, "invalid": 0}, "invalid": 3},
    }


def test_replay_report_groups_nested_counts_by_input_regime_labels():
    report = replay_tpo_calibration(_fixture_rows(), thresholds=(0.75,))

    assert set(report["regime_breakdown"]) == {"trend", "range", "high_volatility", "low_volatility"}
    assert report["regime_breakdown"]["trend"]["va_rejection"]["long"]["valid"] == 1
    assert report["regime_breakdown"]["range"]["va_breakout_acceptance"]["long"]["valid"] == 1
    assert report["regime_breakdown"]["high_volatility"]["trend_pullback"]["short"]["valid"] == 1
    assert report["regime_breakdown"]["high_volatility"]["va_rejection"]["short"]["valid"] == 1
    assert report["regime_breakdown"]["low_volatility"]["va_rejection"]["invalid"] == 1


def test_replay_report_threshold_sensitivity_records_tags_and_conflicts():
    report = replay_tpo_calibration(_fixture_rows(), thresholds=(0.75, 0.85))

    assert report["threshold_sensitivity"] == {
        "0.75": {
            "emitted_tag_counts": {
                "tpo_va_breakout_bull": 1,
                "tpo_va_rejection_bull": 1,
                "tpo_va_rejection_bear": 1,
                "tpo_trend_pullback_bull": 1,
                "tpo_trend_pullback_bear": 1,
            },
            "suppressed_conflict_count": 1,
        },
        "0.85": {
            "emitted_tag_counts": {
                "tpo_va_breakout_bull": 1,
                "tpo_va_rejection_bull": 1,
            },
            "suppressed_conflict_count": 1,
        },
    }


def test_replay_import_scope_excludes_production_persistence_and_runtime_modules():
    loaded = set(sys.modules)

    assert all(not module.startswith(FORBIDDEN_MODULE_PREFIXES) for module in loaded)
