from engine.strategy_executor import enrich_strategy_decisions_with_contract_metadata
from engine.scoring.aggregate import update_aggregate_score


def test_scoring_e2e_decision_contains_audit_fields_and_precision():
    strategy_results = [
        {
            "strategy": "template_breakout",
            "strategy_version": "v1",
            "profit_outcome": 0.123456789,
            "signal_quality": 0.987654321,
            "timing_quality": 0.333333333,
            "volatility_session": 0.777777777,
        }
    ]

    enriched = enrich_strategy_decisions_with_contract_metadata(
        strategy_results,
        normalized_snapshot={"foo": "bar"},
    )

    assert len(enriched) == 1
    decision = enriched[0]

    assert "score_total" in decision
    assert "score_breakdown" in decision
    assert "score_version" in decision
    assert "weights_snapshot" in decision
    assert "missing_data_policy" in decision

    assert decision["score_version"] == "scor-v1.0.0"
    assert decision["missing_data_policy"] == "impute_neutral_and_flag"

    score_total = decision["score_total"]
    assert isinstance(score_total, float)
    assert score_total == round(score_total, 6)

    criteria = decision["score_breakdown"]["criteria"]
    assert len(criteria) == 4
    for criterion in criteria:
        normalized = criterion["normalized"]
        assert normalized == round(normalized, 6)


def test_scoring_e2e_aggregate_dimensions_strategy_symbol_timeframe():
    strategy_results = [
        {
            "strategy": "template_breakout",
            "strategy_version": "v1",
            "profit_outcome": 0.8,
            "signal_quality": 0.7,
            "timing_quality": 0.6,
            "volatility_session": 0.5,
        },
        {
            "strategy": "template_breakout",
            "strategy_version": "v1",
            "profit_outcome": 0.6,
            "signal_quality": 0.5,
            "timing_quality": 0.4,
            "volatility_session": 0.3,
        },
    ]

    enriched = enrich_strategy_decisions_with_contract_metadata(strategy_results, normalized_snapshot={})
    artifact = update_aggregate_score(
        records=enriched,
        strategy_name="template_breakout",
        symbol="XAUUSD",
        timeframe="M15",
        score_version="scor-v1.0.0",
    )

    assert artifact["group_key"] == "template_breakout|XAUUSD|M15"
    assert artifact["strategy"] == "template_breakout"
    assert artifact["symbol"] == "XAUUSD"
    assert artifact["timeframe"] == "M15"
    assert artifact["score_version"] == "scor-v1.0.0"
    assert artifact["trade_count"] == 2
