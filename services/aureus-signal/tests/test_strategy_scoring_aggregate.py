from engine.scoring.aggregate import update_aggregate_score


def test_update_aggregate_score_builds_group_key_three_dimensions():
    records = [
        {"score_total": 0.666666, "score_version": "scor-v1.0.0"},
        {"score_total": 0.333333, "score_version": "scor-v1.0.0"},
    ]

    result = update_aggregate_score(
        records=records,
        strategy_name="template_breakout",
        symbol="XAUUSD",
        timeframe="M15",
        score_version="scor-v1.0.0",
    )

    assert result["group_key"] == "template_breakout|XAUUSD|M15"
    assert result["trade_count"] == 2
    assert result["score_version"] == "scor-v1.0.0"
    assert result["aggregate_score"] == 0.499999


def test_update_aggregate_score_filters_mismatched_score_version():
    records = [
        {"score_total": 0.9, "score_version": "scor-v0.9.0"},
        {"score_total": 0.5, "score_version": "scor-v1.0.0"},
    ]

    result = update_aggregate_score(
        records=records,
        strategy_name="template_breakout",
        symbol="XAUUSD",
        timeframe="M5",
        score_version="scor-v1.0.0",
    )

    assert result["group_key"] == "template_breakout|XAUUSD|M5"
    assert result["trade_count"] == 1
    assert result["aggregate_score"] == 0.5
