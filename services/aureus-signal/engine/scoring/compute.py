from __future__ import annotations

from copy import deepcopy

_CRITERIA = (
    "profit_outcome",
    "signal_quality",
    "timing_quality",
    "volatility_session",
)


def _round6(value: float) -> float:
    return round(float(value), 6)


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def compute_trade_score(input_payload: dict, score_version: str, weights_snapshot: dict) -> dict:
    gate_passed = bool(input_payload.get("quality_gate_passed", True))
    immutable_weights = deepcopy(weights_snapshot or {})

    result = {
        "gate": {
            "passed": gate_passed,
            "reason_code": None if gate_passed else "QUALITY_GATE_FAILED",
        },
        "score_version": score_version,
        "weights_snapshot": immutable_weights,
        "criteria": [],
        "missing_data_policy": "impute_neutral_and_flag",
        "score_total": None,
    }

    if not gate_passed:
        return result

    criteria_payload = input_payload.get("criteria") if isinstance(input_payload.get("criteria"), dict) else {}
    score_total = 0.0

    for criterion in _CRITERIA:
        if criterion in criteria_payload:
            raw_value = criteria_payload[criterion]
            missing = False
        elif criterion in input_payload:
            raw_value = input_payload[criterion]
            missing = False
        else:
            raw_value = 0.5
            missing = True

        normalized = _round6(_clamp01(float(raw_value)))
        weight = float(immutable_weights.get(criterion, 0.0))
        score_total += normalized * weight

        result["criteria"].append(
            {
                "name": criterion,
                "raw": float(raw_value),
                "normalized": normalized,
                "weight": weight,
                "normalization_method": "clamp_0_1",
                "imputed": missing,
            }
        )

    result["score_total"] = _round6(score_total)
    return result
