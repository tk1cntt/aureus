import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "migrations" / "add_trade_evaluations.sql"


def _sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_evaluation_table_is_not_created():
    sql = _sql()
    assert "aureus_trade_evaluations" not in sql


def test_signal_snapshot_table_remains_in_migration():
    sql = _sql()
    assert re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+aureus_trade_signal_snapshots", sql, re.IGNORECASE)
    assert re.search(r"trade_journal_id\s+BIGINT\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert re.search(r"REFERENCES\s+aureus_trade_journal\s*\(\s*id\s*\)", sql, re.IGNORECASE)
    assert re.search(r"CONSTRAINT\s+uq_trade_signal_snapshot_trade\s+UNIQUE\s*\(\s*trade_journal_id\s*\)", sql, re.IGNORECASE)


def test_signal_snapshot_runtime_indexes_remain():
    sql = _sql()
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_signal_snapshot_symbol_created_at", sql, re.IGNORECASE)
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_signal_snapshot_symbol_session_created_at", sql, re.IGNORECASE)
    assert re.search(r"CREATE\s+INDEX\s+idx_trade_signal_snapshot_created_at_brin", sql, re.IGNORECASE)


def test_signal_snapshot_indicator_columns_remain():
    sql = _sql()
    for column in (
        "atr",
        "ema_21",
        "ema_34",
        "ema_55",
        "ema_89",
        "ema_100",
        "ema_200",
        "vol_sma_20",
        "session",
        "bb_m1_up",
        "bb_m1_dn",
        "cisd_m5",
        "cisd_m15",
        "cisd_m30",
        "cisd_h1",
    ):
        assert re.search(rf"\b{column}\b", sql, re.IGNORECASE)
