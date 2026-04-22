import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "migrations" / "add_trade_evaluations.sql"


def _sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_eval_unique_trade_journal_score_version_exists():
    sql = _sql()
    assert re.search(r"UNIQUE\s*\(\s*trade_journal_id\s*,\s*score_version\s*\)", sql, re.IGNORECASE)


def test_eval_fk_to_trade_journal_exists():
    sql = _sql()
    assert re.search(r"trade_journal_id\s+BIGINT\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"REFERENCES\s+aureus_trade_journal\s*\(\s*id\s*\)", sql, re.IGNORECASE)


def test_eval_score_breakdown_and_missing_data_policy_constraints_exist():
    sql = _sql()
    assert re.search(r"score_breakdown\s+JSONB\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"missing_data_policy\s+TEXT\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"jsonb_typeof\s*\(\s*score_breakdown\s*\)\s*=\s*'object'", sql, re.IGNORECASE)
    assert re.search(r"score_breakdown\s*<>\s*'\{\}'::jsonb", sql, re.IGNORECASE)


def test_eval_weights_snapshot_check_constraint_exists():
    sql = _sql()
    assert re.search(r"weights_snapshot\s+JSONB\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"jsonb_typeof\s*\(\s*weights_snapshot\s*\)\s*=\s*'object'", sql, re.IGNORECASE)
    assert re.search(r"weights_snapshot\s*<>\s*'\{\}'::jsonb", sql, re.IGNORECASE)


def test_eval_indexes_exist_for_runtime_queries():
    sql = _sql()
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_eval_symbol_tf_eval_at", sql, re.IGNORECASE)
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_eval_current_symbol_tf_eval_at", sql, re.IGNORECASE)


def test_eval_static_payload_contract_matches_plan_values():
    payload = {
        "score_version": "scor-v1.0.0",
        "strategy_name": "london_breakout",
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "score_total": 0.7825,
        "missing_data_policy": "impute_neutral_and_flag",
        "score_breakdown": {"signal_quality": 0.78},
        "weights_snapshot": {"signal_quality": 0.4},
    }
    assert payload["score_version"] == "scor-v1.0.0"
    assert payload["strategy_name"] == "london_breakout"
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "M15"
    assert payload["score_total"] == 0.7825
    assert payload["missing_data_policy"] == "impute_neutral_and_flag"
    assert payload["score_breakdown"] != {}
    assert payload["weights_snapshot"] != {}
