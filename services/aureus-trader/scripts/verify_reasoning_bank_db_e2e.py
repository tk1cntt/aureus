"""DB E2E verification for Reasoning Bank MVP."""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_config
from journal import TradeJournalManager


async def _ensure_schema(conn):
    migration_path = Path(__file__).resolve().parents[2] / "aureus-db-writer" / "migrations" / "add_reasoning_entries.sql"
    await conn.execute(migration_path.read_text(encoding="utf-8"))


async def main():
    cfg = load_config()
    dsn = os.getenv(
        "AUREUS_DB_DSN",
        f"postgresql://{cfg.db_user}:{cfg.db_password}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}",
    )
    trace_id = f"e2e-reasoning-{uuid.uuid4().hex[:12]}"
    ticket = 9400000001
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    journal = TradeJournalManager(pool)

    try:
        async with pool.acquire() as conn:
            await _ensure_schema(conn)
            await conn.execute(
                """
                INSERT INTO aureus_trades (trace_id, symbol, direction, entry_type, entry_price, status)
                VALUES ($1, 'XAUUSD', 'BUY', 'MARKET', 2320.5, 'TEST')
                ON CONFLICT (trace_id) DO NOTHING
                """,
                trace_id,
            )

        assert await journal.on_strategy_match({
            "type": "STRATEGY_MATCH",
            "trace_id": trace_id,
            "data": {
                "trace_id": trace_id,
                "strategy_name": "reasoning_bank_e2e",
                "strategy_id": 26050201,
                "direction": "BUY",
                "symbol": "XAUUSD",
                "score": 0.88,
                "active_signals": [{"tag": "cisd_bull", "status": "active"}],
                "context_filters": {"session": "london"},
                "reasoning": "E2E strategy rationale",
            },
        })
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_reasoning_entries WHERE trace_id=$1", trace_id)
        assert row is not None
        assert row["strategy_name"] == "reasoning_bank_e2e"
        assert row["confidence"] == 0.88

        assert await journal.on_order_opened({
            "type": "ORDER_OPENED",
            "trace_id": trace_id,
            "ticket": ticket,
            "open_price": 2321.0,
            "volume": 0.1,
            "time": 1775642400,
            "signal_snapshot": {"active_signals": [{"tag": "cisd_bull"}], "context_filters": {"session": "london"}},
        })
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_reasoning_entries WHERE trace_id=$1", trace_id)
        assert row["ticket"] == ticket
        assert row["trade_journal_id"] is not None
        assert row["signal_snapshot_id"] is not None

        assert await journal.on_order_closed({
            "type": "ORDER_CLOSED",
            "ticket": ticket,
            "close_price": 2325.0,
            "profit": 9.5,
            "commission": 0,
            "swap": 0,
            "close_reason": "TP_HIT",
            "close_time": 1775646000,
            "open_price": 2321.0,
        })
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_reasoning_entries WHERE trace_id=$1", trace_id)
        assert row["success"] is True
        assert row["reward"] == 400.0
        assert row["pnl"] == 9.5
        assert row["evaluated_at"] is not None
        print(f"PASS reasoning bank DB E2E trace_id={trace_id}")
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM aureus_reasoning_entries WHERE trace_id=$1", trace_id)
            await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id=$1", trace_id)
            await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id=$1", trace_id)
            await conn.execute("DELETE FROM aureus_trades WHERE trace_id=$1", trace_id)
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
