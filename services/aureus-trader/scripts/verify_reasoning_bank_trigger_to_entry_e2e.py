"""DB/runtime E2E for dispatcher-triggered Reasoning Bank entry persistence."""
import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import TraderConfig
from dispatcher import OrderDispatcher
from journal import TradeJournalManager
from config import load_config


class FakeRedis:
    def __init__(self):
        self.published = []

    async def publish(self, channel, payload):
        self.published.append((channel, json.loads(payload)))
        return 1


async def _ensure_schema(conn):
    migrations = Path(__file__).resolve().parents[2] / "aureus-db-writer" / "migrations"
    for name in (
        "add_reasoning_entries.sql",
        "add_reasoning_entries_embeddings.sql",
        "add_reasoning_entries_join_indexes.sql",
        "drop_reasoning_entries_active_signals.sql",
        "drop_reasoning_entries_active_signals.sql",
    ):
        await conn.execute((migrations / name).read_text(encoding="utf-8"))


async def _assert_active_signals_removed(conn):
    column_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = 'aureus_reasoning_entries'
          AND column_name = 'active_signals'
        """
    )
    index_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'aureus_reasoning_entries'
          AND indexname = 'idx_reasoning_entries_active_signals'
        """
    )
    assert column_count == 0
    assert index_count == 0


async def _cleanup(conn, trace_id):
    await conn.execute("DELETE FROM aureus_reasoning_entries WHERE trace_id=$1", trace_id)
    await conn.execute("DELETE FROM aureus_trade_signal_snapshots WHERE trace_id=$1", trace_id)
    await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id=$1", trace_id)
    await conn.execute("DELETE FROM aureus_trades WHERE trace_id=$1", trace_id)


async def run_e2e():
    cfg = load_config()
    dsn = os.getenv(
        "AUREUS_DB_DSN",
        f"postgresql://{cfg.db_user}:{cfg.db_password}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}",
    )
    trace_id = f"e2e-reasoning-trigger-{uuid.uuid4().hex[:12]}"
    cmd_id = f"cmd-{trace_id}"
    ticket = 9600000001
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)

    try:
        async with pool.acquire() as conn:
            await _ensure_schema(conn)
            await _assert_active_signals_removed(conn)
            await _cleanup(conn, trace_id)
            await conn.execute(
                """
                INSERT INTO aureus_trades (trace_id, symbol, direction, entry_type, entry_price, status)
                VALUES ($1, 'XAUUSD', 'BUY', 'MARKET', 2320.5, 'TEST')
                """,
                trace_id,
            )

        fake_redis = FakeRedis()
        dispatcher = OrderDispatcher(
            fake_redis,
            TraderConfig(ack_timeout=0.1, result_timeout=0.1, max_retries=0),
            journal_manager=TradeJournalManager(pool),
        )
        responses = iter((
            {"type": "ACK", "cmd_id": cmd_id, "trace_id": trace_id},
            {
                "type": "ORDER_OPENED",
                "cmd_id": cmd_id,
                "trace_id": trace_id,
                "ticket": ticket,
                "open_price": 2321.0,
                "volume": 0.1,
                "time": 1775642400,
                "timeframe": "M15",
                "signal_schema_version": "sig-v2.0.0",
            },
        ))

        async def fake_wait_for_response(wait_cmd_id, timeout):
            assert wait_cmd_id == cmd_id
            return next(responses)

        dispatcher._wait_for_response = fake_wait_for_response

        active_signals = [{"tag": "cisd_bull", "status": "active", "atr": 2.5, "cisd_m15": "BULL"}]
        context_filters = {"session": "london"}
        signal_snapshot = {
            "active_signals": active_signals,
            "context_filters": context_filters,
            "trend": "bullish",
            "tpo_shape": "D",
            "session": "london",
            "atr": 2.5,
            "cisd_m15": "BULL",
        }
        order = {
            "type": "OPEN_ORDER",
            "cmd_id": cmd_id,
            "trace_id": trace_id,
            "symbol": "XAUUSD",
            "direction": "BUY",
            "order_type": "MARKET",
            "volume": 0.1,
            "price": 2320.5,
            "sl": 2310.0,
            "tp": 2330.0,
            "magic": 26050308,
            "comment": "reasoning-trigger-e2e",
            "signal_schema_version": "sig-v2.0.0",
            "strategy_event": {
                "type": "STRATEGY_MATCH",
                "trace_id": trace_id,
                "data": {
                    "trace_id": trace_id,
                    "strategy_name": "reasoning_trigger_to_entry",
                    "strategy_id": 26050308,
                    "direction": "BUY",
                    "symbol": "XAUUSD",
                    "score": 0.91,
                    "active_signals": active_signals,
                    "context_filters": context_filters,
                    "signal_snapshot": signal_snapshot,
                },
            },
        }

        await dispatcher.dispatch_order(order)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT re.id, re.trace_id, re.trade_journal_id, re.signal_snapshot_id,
                       re.reasoning_text, re.prompt_text, re.context_text,
                       tj.strategy_name, tj.symbol, tj.direction, tj.status, tj.ticket,
                       ts.timeframe, ts.atr, ts.cisd_m15, ts.session, ts.ticket AS snapshot_ticket
                FROM aureus_reasoning_entries re
                JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
                JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
                WHERE re.trace_id=$1
                """,
                trace_id,
            )
            assert len(rows) == 1
            row = rows[0]
            assert row["trade_journal_id"] is not None
            assert row["signal_snapshot_id"] is not None
            assert row["reasoning_text"]
            assert "reasoning_trigger_to_entry" in row["reasoning_text"]
            assert "XAUUSD" in row["reasoning_text"]
            assert "BUY" in row["reasoning_text"]
            assert "london" in row["reasoning_text"]
            assert "cisd_m15=1" in row["reasoning_text"]
            assert "active_signals" not in row["reasoning_text"]
            assert "cisd_bull" not in row["reasoning_text"]
            assert row["prompt_text"] is None
            assert row["context_text"] is None
            assert row["strategy_name"] == "reasoning_trigger_to_entry"
            assert row["symbol"] == "XAUUSD"
            assert row["direction"] == "BUY"
            assert row["status"] == "EXECUTED"
            assert row["ticket"] == ticket
            assert row["snapshot_ticket"] == ticket
            assert row["timeframe"] == "M15"
            assert row["atr"] == 2.5
            assert row["cisd_m15"] == 1
            assert row["session"] == 2

        assert len(fake_redis.published) == 1
        assert fake_redis.published[0][1]["cmd_id"] == cmd_id
        print(f"PASS reasoning bank trigger-to-entry DB E2E trace_id={trace_id}")
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, trace_id)
        await pool.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Verify dispatcher-triggered Reasoning Bank entry persistence")
    parser.add_argument("--dsn", help="Reserved; use AUREUS_DB_DSN for now")
    return parser.parse_args()


def main():
    parse_args()
    asyncio.run(run_e2e())


if __name__ == "__main__":
    main()
