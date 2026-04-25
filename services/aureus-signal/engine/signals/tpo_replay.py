from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable

from engine.signals.tpo_detectors import TrendPullbackDetector, VABreakoutAcceptanceDetector, VARejectionDetector
from engine.signals.tpo_strategy import tpo_strategy_tags_from_candidates


SETUPS = ("va_rejection", "va_breakout_acceptance", "trend_pullback")


def replay_tpo_calibration(rows: Iterable[Dict[str, Any]], thresholds=(0.75,)) -> Dict[str, Any]:
    row_list = list(rows)
    candidates_by_row = [_detect_row_candidates(row) for row in row_list]
    all_candidates = [candidate for row_candidates in candidates_by_row for candidate in row_candidates]

    report = {
        "rows": len(row_list),
        "candidate_count": len(all_candidates),
        "setup_counts": _empty_setup_counts(),
        "regime_breakdown": {},
        "threshold_sensitivity": {},
    }

    for row, row_candidates in zip(row_list, candidates_by_row):
        regime = row.get("regime") or "unknown"
        if regime not in report["regime_breakdown"]:
            report["regime_breakdown"][regime] = _empty_setup_counts()
        _add_candidates(report["setup_counts"], row_candidates)
        _add_candidates(report["regime_breakdown"][regime], row_candidates)

    for threshold in thresholds:
        emitted_tags = []
        suppressed_conflicts = 0
        for row_candidates in candidates_by_row:
            result = tpo_strategy_tags_from_candidates(row_candidates, min_score=threshold)
            if result["suppressed"]:
                suppressed_conflicts += 1
                emitted_tags.extend(item["tag"] for item in result["debug"])
                continue
            emitted_tags.extend(result["tags"])
            if _has_conflicting_valid_sides(row_candidates):
                suppressed_conflicts += 1
        report["threshold_sensitivity"][_threshold_key(threshold)] = {
            "emitted_tag_counts": dict(sorted(Counter(emitted_tags).items())),
            "suppressed_conflict_count": suppressed_conflicts,
        }

    return report


def _detect_row_candidates(row: Dict[str, Any]) -> list[Dict[str, Any]]:
    context = row["context"]
    previous_close = row["previous_close"]
    current_close = row["current_close"]
    acceptance_closes = row.get("acceptance_closes") or []

    return [
        VARejectionDetector().detect(context, previous_close, current_close),
        VABreakoutAcceptanceDetector().detect(context, current_close, acceptance_closes),
        TrendPullbackDetector().detect(context, previous_close, current_close),
    ]


def _empty_setup_counts() -> Dict[str, Dict[str, Any]]:
    return {
        setup: {
            "long": {"valid": 0, "invalid": 0},
            "short": {"valid": 0, "invalid": 0},
            "invalid": 0,
        }
        for setup in SETUPS
    }


def _add_candidates(counts: Dict[str, Dict[str, Any]], candidates: list[Dict[str, Any]]) -> None:
    for candidate in candidates:
        setup = candidate.get("setup")
        if setup not in counts:
            continue
        side = candidate.get("side")
        if candidate.get("valid") and side in ("long", "short"):
            counts[setup][side]["valid"] += 1
        elif side in ("long", "short"):
            counts[setup][side]["invalid"] += 1
        else:
            counts[setup]["invalid"] += 1


def _has_conflicting_valid_sides(candidates: list[Dict[str, Any]]) -> bool:
    sides = {candidate.get("side") for candidate in candidates if candidate.get("valid") and candidate.get("side")}
    if len(sides) > 1:
        return True
    valid_candidates = [candidate for candidate in candidates if candidate.get("valid")]
    invalid_reasons = [reason for candidate in candidates if not candidate.get("valid") for reason in candidate.get("reasons", [])]
    return bool(valid_candidates) and any("conflicts with D1" in reason for reason in invalid_reasons)


def _threshold_key(threshold: float) -> str:
    return f"{threshold:g}"
