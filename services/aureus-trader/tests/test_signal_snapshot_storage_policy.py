import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "aureus-db-writer" / "migrations" / "optimize_trade_signal_snapshots_storage.sql"


def _sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _snapshot_table_sql(sql: str) -> str:
    match = re.search(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+aureus_trade_signal_snapshots\s*\((.*?)\);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_storage_policy_hybrid_contract_columns_exist():
    sql = _sql()
    snapshot_sql = _snapshot_table_sql(sql)
    required_cols = [
        "trade_journal_id", "trace_id", "ticket", "strategy_name", "symbol",
        "timeframe", "signal_schema_version", "signal_snapshot", "cisd_direction",
        "ema21", "ema55", "created_at",
    ]
    for col in required_cols:
        assert re.search(rf"\b{col}\b", snapshot_sql, re.IGNORECASE)


def test_storage_policy_reject_debug_legacy_derived_typed_columns():
    sql = _sql()
    snapshot_sql = _snapshot_table_sql(sql)
    forbidden_cols = ["ema21_above_ema55", "debug_payload", "raw_reasoning"]
    for col in forbidden_cols:
        assert not re.search(rf"\b{col}\b", snapshot_sql, re.IGNORECASE)


def test_storage_policy_ttl_and_archive_before_prune_present():
    sql = _sql()
    assert re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+aureus_trade_signal_snapshots_archive", sql, re.IGNORECASE)
    assert re.search(r"interval\s+'90\s+days'", sql, re.IGNORECASE)
    assert re.search(r"INSERT\s+INTO\s+aureus_trade_signal_snapshots_archive", sql, re.IGNORECASE)
    assert re.search(r"DELETE\s+FROM\s+aureus_trade_signal_snapshots", sql, re.IGNORECASE)
    assert re.search(r"LIMIT\s+5000", sql, re.IGNORECASE)
