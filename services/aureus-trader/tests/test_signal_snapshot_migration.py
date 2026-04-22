import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "aureus-db-writer"
MIGRATION_PATH = ROOT / "migrations" / "add_trade_evaluations.sql"


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


def test_signal_snapshot_fk_to_trade_journal_exists():
    sql = _sql()
    snapshot_sql = _snapshot_table_sql(sql)
    assert re.search(r"trade_journal_id\s+BIGINT\s+NOT\s+NULL", snapshot_sql, re.IGNORECASE)
    assert re.search(r"REFERENCES\s+aureus_trade_journal\s*\(\s*id\s*\)", snapshot_sql, re.IGNORECASE)


def test_signal_snapshot_new_columns_exist():
    sql = _sql()
    snapshot_sql = _snapshot_table_sql(sql)
    required_cols = [
        "atr", "ema_21", "ema_34", "ema_55", "ema_89", "ema_100", "ema_200", "vol_sma_20",
        "session", "candle_color_d1", "candle_color_h1", "candle_color_m30", "candle_color_m15", "candle_color_m5",
        "bb_m1_up", "bb_m1_dn", "bb_m5_up", "bb_m5_dn", "bb_m15_up", "bb_m15_dn",
        "bb_m30_up", "bb_m30_dn", "bb_h1_up", "bb_h1_dn",
        "cisd_m5", "cisd_m15", "cisd_m30", "cisd_h1",
    ]
    for col in required_cols:
        assert re.search(rf"\b{col}\b", snapshot_sql, re.IGNORECASE)


def test_signal_snapshot_old_columns_removed():
    sql = _sql()
    snapshot_sql = _snapshot_table_sql(sql)
    removed_cols = ["timeframe", "signal_schema_version", "signal_snapshot", "cisd_direction", "ema21", "ema55"]
    for col in removed_cols:
        assert not re.search(rf"\b{col}\b", snapshot_sql, re.IGNORECASE)


def test_signal_snapshot_unique_constraint_exists():
    sql = _sql()
    snapshot_sql = _snapshot_table_sql(sql)
    assert re.search(r"CONSTRAINT\s+uq_trade_signal_snapshot_trade\s+UNIQUE\s*\(\s*trade_journal_id\s*\)", snapshot_sql, re.IGNORECASE)


def test_signal_snapshot_indexes_exist_for_runtime_queries():
    sql = _sql()
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_signal_snapshot_symbol_created_at", sql, re.IGNORECASE)
    assert re.search(r"ON\s+aureus_trade_signal_snapshots\s*\(\s*symbol\s*,\s*created_at\s+DESC\s*\)", sql, re.IGNORECASE)
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_signal_snapshot_symbol_session_created_at", sql, re.IGNORECASE)
    assert re.search(r"ON\s+aureus_trade_signal_snapshots\s*\(\s*symbol\s*,\s*session\s*,\s*created_at\s+DESC\s*\)", sql, re.IGNORECASE)
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_signal_snapshot_created_at_brin", sql, re.IGNORECASE)
    assert re.search(r"ON\s+aureus_trade_signal_snapshots\s+USING\s+BRIN\s*\(\s*created_at\s*\)", sql, re.IGNORECASE)


def test_signal_snapshot_phase55_tables_exist_in_migration():
    sql = _sql()
    assert re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+aureus_trade_evaluations", sql, re.IGNORECASE)
    assert re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+aureus_trade_signal_snapshots", sql, re.IGNORECASE)
