from __future__ import annotations

from rollout_gates import RolloutGateMetrics, evaluate_rollout_gate



def test_rollout_gate_blocks_if_missing_sl_tp_metric_non_zero():
    decision = evaluate_rollout_gate(
        RolloutGateMetrics(missing_sl_total=1, missing_tp_total=0, restart_per_hour=0.0, duplicate_trace_id_total=0)
    )

    assert decision.allow_promotion is False
    assert "missing_sl_total must be 0" in decision.reasons


def test_rollout_gate_blocks_if_restart_rate_exceeds_threshold():
    decision = evaluate_rollout_gate(
        RolloutGateMetrics(missing_sl_total=0, missing_tp_total=0, restart_per_hour=1.0, duplicate_trace_id_total=0)
    )

    assert decision.allow_promotion is False
    assert "restart_per_hour must be 0" in decision.reasons


def test_rollout_gate_blocks_if_load_rejected_ratio_exceeds_threshold():
    decision = evaluate_rollout_gate(RolloutGateMetrics(load_rejected_ratio=0.08))

    assert decision.allow_promotion is False
    assert "load_rejected_ratio must be <= 0.05" in decision.reasons


def test_rollout_gate_blocks_if_shadow_mismatch_detected():
    decision = evaluate_rollout_gate(RolloutGateMetrics(shadow_mismatch_total=2))

    assert decision.allow_promotion is False
    assert "shadow_mismatch_total must be 0" in decision.reasons


def test_rollout_gate_allows_promotion_when_all_slos_pass():
    decision = evaluate_rollout_gate(
        RolloutGateMetrics(
            missing_sl_total=0,
            missing_tp_total=0,
            restart_per_hour=0.0,
            duplicate_trace_id_total=0,
            load_rejected_ratio=0.0,
            shadow_mismatch_total=0,
        )
    )

    assert decision.allow_promotion is True
    assert decision.reasons == []
    assert decision.evidence["load_rejected_ratio"] == 0.0
    assert decision.evidence["shadow_mismatch_total"] == 0
