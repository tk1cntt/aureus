from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RolloutGateMetrics:
    missing_sl_total: int = 0
    missing_tp_total: int = 0
    restart_per_hour: float = 0.0
    duplicate_trace_id_total: int = 0


@dataclass(frozen=True)
class RolloutGateDecision:
    allow_promotion: bool
    reasons: List[str]


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

    return RolloutGateDecision(allow_promotion=len(reasons) == 0, reasons=reasons)
