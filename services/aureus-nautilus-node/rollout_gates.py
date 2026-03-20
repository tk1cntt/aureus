from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RolloutGateMetrics:
    # Legacy metrics (kept for compatibility)
    missing_sl_total: int = 0
    missing_tp_total: int = 0
    restart_per_hour: float = 0.0
    duplicate_trace_id_total: int = 0
    load_rejected_ratio: float = 0.0
    shadow_mismatch_total: int = 0

    # Phase 12 metrics (spec-aligned)
    determinism_violations_total: int = 0
    backfill_violation_total: int = 0
    trace_completeness_rate: float = 1.0
    integrity_incident_unresolved_total: int = 0
    validator_state_error_high_total: int = 0
    drawdown_breach_total: int = 0
    operational_readiness_signed: bool = False


@dataclass(frozen=True)
class RolloutGateDecision:
    allow_promotion: bool
    reasons: List[str]
    evidence: Dict[str, float | int | bool | str]


def summarize_rollout_evidence(metrics: RolloutGateMetrics, stage: str) -> Dict[str, float | int | bool | str]:
    return {
        "stage": stage,
        "missing_sl_total": metrics.missing_sl_total,
        "missing_tp_total": metrics.missing_tp_total,
        "restart_per_hour": metrics.restart_per_hour,
        "duplicate_trace_id_total": metrics.duplicate_trace_id_total,
        "load_rejected_ratio": metrics.load_rejected_ratio,
        "shadow_mismatch_total": metrics.shadow_mismatch_total,
        "determinism_violations_total": metrics.determinism_violations_total,
        "backfill_violation_total": metrics.backfill_violation_total,
        "trace_completeness_rate": metrics.trace_completeness_rate,
        "integrity_incident_unresolved_total": metrics.integrity_incident_unresolved_total,
        "validator_state_error_high_total": metrics.validator_state_error_high_total,
        "drawdown_breach_total": metrics.drawdown_breach_total,
        "operational_readiness_signed": metrics.operational_readiness_signed,
    }


def _apply_legacy_checks(metrics: RolloutGateMetrics, reasons: List[str]) -> None:
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


def _apply_universal_checks(metrics: RolloutGateMetrics, reasons: List[str]) -> None:
    if metrics.determinism_violations_total > 0:
        reasons.append("determinism_violations_total must be 0")

    if metrics.backfill_violation_total > 0:
        reasons.append("backfill_violation_total must be 0")

    if metrics.integrity_incident_unresolved_total > 0:
        reasons.append("integrity_incident_unresolved_total must be 0")


def evaluate_rollout_gate(stage_or_metrics, metrics: RolloutGateMetrics | None = None) -> RolloutGateDecision:
    # Backward compatibility: evaluate_rollout_gate(metrics)
    if isinstance(stage_or_metrics, RolloutGateMetrics):
        stage = "SHADOW_TO_PAPER"
        metrics_obj = stage_or_metrics
    else:
        stage = str(stage_or_metrics).upper().strip()
        metrics_obj = metrics if metrics is not None else RolloutGateMetrics()

    reasons: List[str] = []

    if stage not in {"SHADOW_TO_PAPER", "PAPER_TO_LIVE"}:
        reasons.append(f"unknown promotion stage: {stage}")
        return RolloutGateDecision(
            allow_promotion=False,
            reasons=reasons,
            evidence=summarize_rollout_evidence(metrics_obj, stage),
        )

    _apply_legacy_checks(metrics_obj, reasons)
    _apply_universal_checks(metrics_obj, reasons)

    if stage == "SHADOW_TO_PAPER":
        if metrics_obj.trace_completeness_rate < 0.97:
            reasons.append("trace_completeness_rate must be >= 0.97 for SHADOW_TO_PAPER")

    if stage == "PAPER_TO_LIVE":
        if metrics_obj.trace_completeness_rate < 0.99:
            reasons.append("trace_completeness_rate must be >= 0.99 for PAPER_TO_LIVE")
        if metrics_obj.validator_state_error_high_total > 0:
            reasons.append("validator_state_error_high_total must be 0 for PAPER_TO_LIVE")
        if metrics_obj.drawdown_breach_total > 0:
            reasons.append("drawdown_breach_total must be 0 for PAPER_TO_LIVE")
        if metrics_obj.operational_readiness_signed is not True:
            reasons.append("operational_readiness_signed must be true for PAPER_TO_LIVE")

    return RolloutGateDecision(
        allow_promotion=len(reasons) == 0,
        reasons=reasons,
        evidence=summarize_rollout_evidence(metrics_obj, stage),
    )
