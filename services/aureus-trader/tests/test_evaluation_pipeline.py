from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "aureus-db-writer"
MIGRATION_PATH = ROOT / "migrations" / "add_trade_evaluations.sql"


def test_evaluation_pipeline_contract_fields_declared_in_migration():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    required_columns = [
        "trace_id",
        "ticket",
        "score_version",
        "score_total",
        "score_breakdown",
        "weights_snapshot",
        "missing_data_policy",
        "strategy_name",
        "symbol",
        "timeframe",
        "evaluated_at",
        "computed_at",
        "is_current",
    ]
    for col in required_columns:
        assert col in sql


def test_evaluation_pipeline_contract_disallows_empty_breakdown_and_signal_snapshot():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "jsonb_object_length(score_breakdown) > 0" in sql
    assert "jsonb_object_length(signal_snapshot) > 0" in sql


def test_evaluation_pipeline_contract_does_not_define_ema21_above_ema55_column():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "ema21_above_ema55" not in sql
