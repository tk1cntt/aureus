from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RolloutGateMetrics:
    missing_sl_total: int = 0
    missing_tp_total: int = 0
    restart_per_hour: float = 0.0
    duplicate_trace_id_total: int = 0
    load_rejected_ratio: float = 0.0
    shadow_mismatch_total: int = 0


@dataclass(frozen=True)
class RolloutGateDecision:
    allow_promotion: bool
    reasons: List[str]
    evidence: Dict[str, float | int]


def summarize_rollout_evidence(metrics: RolloutGateMetrics) -> Dict[str, float | int]:
    return {
        "missing_sl_total": metrics.missing_sl_total,
        "missing_tp_total": metrics.missing_tp_total,
        "restart_per_hour": metrics.restart_per_hour,
        "duplicate_trace_id_total": metrics.duplicate_trace_id_total,
        "load_rejected_ratio": metrics.load_rejected_ratio,
        "shadow_mismatch_total": metrics.shadow_mismatch_total,
    }


def evaluate_rollout_gate(metrics: RolloutGateMetrics) -> RolloutGateDecision:
    reasons: List[str] = []

    if metrics.missing_sl_total > 0:
        reasons.append("missing_sl_total must be 0")

    if metrics.missing_tp_total > 0:
        reasons.append("missing_tp_total must be 0")

    if metrics.restart_per_hour > 0:
        reasons.append("restart_per_hour must be 0")

    if metrics.duplicate_trace_id_total > 0:
        reasons.append("duplicate_trace_id_total must be 0")

    if metrics.load_rejected_ratio > 0.05:
        reasons.append("load_rejected_ratio must be <= 0.05")

    if metrics.shadow_mismatch_total > 0:
        reasons.append("shadow_mismatch_total must be 0")

    return RolloutGateDecision(
        allow_promotion=len(reasons) == 0,
        reasons=reasons,
        evidence=summarize_rollout_evidence(metrics),
    )
