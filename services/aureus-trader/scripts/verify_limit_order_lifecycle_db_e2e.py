"""DB E2E verification for pending limit order lifecycle linkage."""
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
    await conn.execute(
        """
        ALTER TABLE aureus_trade_journal
            ADD COLUMN IF NOT EXISTS pending_order_id BIGINT,
            ADD COLUMN IF NOT EXISTS entry_deal_ticket BIGINT,
            ADD COLUMN IF NOT EXISTS cmd_id TEXT,
            ADD COLUMN IF NOT EXISTS mt5_comment TEXT
        """
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_pending_order_id ON aureus_trade_journal(pending_order_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_entry_deal_ticket ON aureus_trade_journal(entry_deal_ticket)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_cmd_id ON aureus_trade_journal(cmd_id)")


async def main():
    cfg = load_config()
    dsn = os.getenv(
        "AUREUS_DB_DSN",
        f"postgresql://{cfg.db_user}:{cfg.db_password}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}",
    )
    trace_id = f"e2e-limit-{uuid.uuid4().hex[:12]}"
    cmd_id = f"ord-e2e-{uuid.uuid4().hex[:8]}"
    pending_order_id = 9100000001
    deal_ticket = 9200000001
    position_ticket = 9300000001
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    journal = TradeJournalManager(pool)

    try:
        async with pool.acquire() as conn:
            await _ensure_schema(conn)
            await conn.execute(
                """
                INSERT INTO aureus_trades (trace_id, symbol, direction, entry_type, entry_price, status)
                VALUES ($1, 'XAUUSD', 'BUY', 'LIMIT', 2320.5, 'TEST')
                ON CONFLICT (trace_id) DO NOTHING
                """,
                trace_id,
            )

        strategy_event = {
            "type": "STRATEGY_MATCH",
            "trace_id": trace_id,
            "data": {
                "trace_id": trace_id,
                "strategy_name": "limit_lifecycle_e2e",
                "strategy_id": 2604298,
                "direction": "BUY",
                "symbol": "XAUUSD",
                "score": 0.91,
                "active_signals": [],
                "context_filters": {},
            },
        }
        assert await journal.on_strategy_match(strategy_event)

        assert await journal.on_order_pending_placed({
            "type": "ORDER_PENDING_PLACED",
            "trace_id": trace_id,
            "cmd_id": cmd_id,
            "pending_order_id": pending_order_id,
            "price": 2320.5,
            "sl": 2310.0,
            "tp": 2340.0,
            "comment": "limit_lifecycle_e2e|e2e",
        })
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_trade_journal WHERE trace_id=$1", trace_id)
        assert row["status"] == "TRIGGERED"
        assert row["pending_order_id"] == pending_order_id
        assert row["ticket"] is None

        assert await journal.on_order_filled({
            "type": "ORDER_FILLED",
            "trace_id": trace_id,
            "cmd_id": cmd_id,
            "pending_order_id": pending_order_id,
            "deal_ticket": deal_ticket,
            "position_ticket": position_ticket,
            "open_price": 2322.0,
            "volume": 0.1,
            "time": 1775642400,
            "comment": "limit_lifecycle_e2e|e2e",
        })
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_trade_journal WHERE trace_id=$1", trace_id)
        assert row["status"] == "EXECUTED"
        assert row["ticket"] == position_ticket
        assert row["position_id"] == position_ticket
        assert row["entry_deal_ticket"] == deal_ticket
        assert row["entry_price"] == 2322.0
        assert row["entry_time"] is not None

        assert await journal.on_order_closed({
            "type": "ORDER_CLOSED",
            "ticket": position_ticket,
            "close_price": 2330.0,
            "profit": 12.5,
            "commission": 0,
            "swap": 0,
            "close_reason": "TP_HIT",
            "close_time": 1775646000,
            "open_price": 2322.0,
        })
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_trade_journal WHERE trace_id=$1", trace_id)
        assert row["status"] == "CLOSED"
        assert row["ticket"] == position_ticket
        print(f"PASS limit lifecycle DB E2E trace_id={trace_id} cmd_id={cmd_id}")
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id=$1", trace_id)
            await conn.execute("DELETE FROM aureus_trades WHERE trace_id=$1", trace_id)
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
