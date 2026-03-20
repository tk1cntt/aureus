from rollout_gates import RolloutGateMetrics, evaluate_rollout_gate


def test_shadow_to_paper_balanced_allows_when_minimum_evidence_passes():
    decision = evaluate_rollout_gate(
        "SHADOW_TO_PAPER",
        RolloutGateMetrics(
            determinism_violations_total=0,
            backfill_violation_total=0,
            trace_completeness_rate=0.985,
            integrity_incident_unresolved_total=0,
            validator_state_error_high_total=0,
        ),
    )
    assert decision.allow_promotion is True
    assert decision.reasons == []


def test_shadow_to_paper_balanced_blocks_on_trace_completeness_threshold():
    decision = evaluate_rollout_gate(
        "SHADOW_TO_PAPER",
        RolloutGateMetrics(
            determinism_violations_total=0,
            backfill_violation_total=0,
            trace_completeness_rate=0.969,
            integrity_incident_unresolved_total=0,
            validator_state_error_high_total=0,
        ),
    )
    assert decision.allow_promotion is False
    assert "trace_completeness_rate must be >= 0.97 for SHADOW_TO_PAPER" in decision.reasons


def test_paper_to_live_balanced_blocks_on_any_high_severity_validator_error():
    decision = evaluate_rollout_gate(
        "PAPER_TO_LIVE",
        RolloutGateMetrics(
            determinism_violations_total=0,
            backfill_violation_total=0,
            trace_completeness_rate=0.995,
            integrity_incident_unresolved_total=0,
            validator_state_error_high_total=1,
            drawdown_breach_total=0,
            operational_readiness_signed=True,
        ),
    )
    assert decision.allow_promotion is False
    assert "validator_state_error_high_total must be 0 for PAPER_TO_LIVE" in decision.reasons


def test_paper_to_live_balanced_requires_operational_readiness_signoff():
    decision = evaluate_rollout_gate(
        "PAPER_TO_LIVE",
        RolloutGateMetrics(
            determinism_violations_total=0,
            backfill_violation_total=0,
            trace_completeness_rate=0.995,
            integrity_incident_unresolved_total=0,
            validator_state_error_high_total=0,
            drawdown_breach_total=0,
            operational_readiness_signed=False,
        ),
    )
    assert decision.allow_promotion is False
    assert "operational_readiness_signed must be true for PAPER_TO_LIVE" in decision.reasons


def test_unknown_stage_returns_explicit_rejection_reason():
    decision = evaluate_rollout_gate("INVALID_STAGE", RolloutGateMetrics())
    assert decision.allow_promotion is False
    assert decision.reasons == ["unknown promotion stage: INVALID_STAGE"]
