import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "aureus-db-writer"
MIGRATION_PATH = ROOT / "migrations" / "add_trade_evaluations.sql"


def _sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_signal_snapshot_fk_to_trade_journal_exists():
    sql = _sql()
    assert re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+aureus_trade_signal_snapshots", sql, re.IGNORECASE)
    assert re.search(r"trade_journal_id\s+BIGINT\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"REFERENCES\s+aureus_trade_journal\s*\(\s*id\s*\)", sql, re.IGNORECASE)


def test_signal_snapshot_unique_trade_journal_and_schema_version_exists():
    sql = _sql()
    assert re.search(r"UNIQUE\s*\(\s*trade_journal_id\s*,\s*signal_schema_version\s*\)", sql, re.IGNORECASE)


def test_signal_snapshot_non_empty_json_check_exists():
    sql = _sql()
    assert re.search(r"signal_snapshot\s+JSONB\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"jsonb_typeof\s*\(\s*signal_snapshot\s*\)\s*=\s*'object'", sql, re.IGNORECASE)
    assert re.search(r"jsonb_object_length\s*\(\s*signal_snapshot\s*\)\s*>\s*0", sql, re.IGNORECASE)


def test_signal_snapshot_typed_columns_match_plan_values():
    payload = {
        "signal_schema_version": "sig-v1.0.0",
        "cisd_direction": "bull",
        "ema21": 3345.12,
        "ema55": 3338.40,
        "signal_snapshot": {
            "cisd": {"direction": "bull"},
            "ema": {"ema21": 3345.12, "ema55": 3338.40},
            "candle_context": {"session": "london"},
        },
    }
    assert payload["signal_schema_version"] == "sig-v1.0.0"
    assert payload["cisd_direction"] == "bull"
    assert payload["ema21"] == 3345.12
    assert payload["ema55"] == 3338.40
    assert payload["signal_snapshot"] != {}
