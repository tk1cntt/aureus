"""DB/runtime E2E for Reasoning Bank joined journal/snapshot reuse."""
import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_config
from journal import TradeJournalManager
from reasoning_embeddings import fetch_strategy_reasoning_insights, semantic_search_reasoning_entries


class StaticEmbeddingClient:
    model = "static-e2e"

    def embed(self, text):
        return [0.1, 0.2, 0.3]


async def _ensure_schema(conn):
    migrations = Path(__file__).resolve().parents[2] / "aureus-db-writer" / "migrations"
    for name in (
        "add_reasoning_entries.sql",
        "add_reasoning_entries_embeddings.sql",
        "add_reasoning_entries_join_indexes.sql",
    ):
        await conn.execute((migrations / name).read_text(encoding="utf-8"))


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
    trace_id = f"e2e-reasoning-reuse-{uuid.uuid4().hex[:12]}"
    ticket = 9500000001
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    journal = TradeJournalManager(pool)

    try:
        async with pool.acquire() as conn:
            await _ensure_schema(conn)
            await _cleanup(conn, trace_id)
            await conn.execute(
                """
                INSERT INTO aureus_trades (trace_id, symbol, direction, entry_type, entry_price, status)
                VALUES ($1, 'XAUUSD', 'BUY', 'MARKET', 2320.5, 'TEST')
                """,
                trace_id,
            )

        assert await journal.on_strategy_match({
            "type": "STRATEGY_MATCH",
            "trace_id": trace_id,
            "data": {
                "trace_id": trace_id,
                "strategy_name": "reasoning_reuse_joined",
                "strategy_id": 26050306,
                "direction": "BUY",
                "symbol": "XAUUSD",
                "score": 0.93,
                "active_signals": [{"tag": "cisd_bull", "status": "active", "atr": 2.5}],
                "context_filters": {"session": "london"},
            },
        })

        assert await journal.on_order_opened({
            "type": "ORDER_OPENED",
            "trace_id": trace_id,
            "ticket": ticket,
            "open_price": 2321.0,
            "volume": 0.1,
            "time": 1775642400,
            "timeframe": "M15",
            "signal_schema_version": "sig-v2.0.0",
            "signal_snapshot": {
                "active_signals": [{"tag": "cisd_bull", "atr": 2.5}],
                "context_filters": {"session": "london"},
                "trend": "bullish",
                "tpo_shape": "D",
                "session": "london",
                "atr": 2.5,
                "cisd_m15": "BULL",
            },
        })

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE aureus_reasoning_entries
                SET strategy_name='divergent_reasoning_strategy',
                    symbol='DIVERGENT',
                    direction='SELL',
                    success=false,
                    reward=-999,
                    pnl=-999,
                    pnl_pips=-999,
                    result='LOSS',
                    reasoning_embedding='[0.1,0.2,0.3]'::vector,
                    embedding_model='static-e2e',
                    embedded_at=now()
                WHERE trace_id=$1
                """,
                trace_id,
            )

        assert await journal.on_order_closed({
            "type": "ORDER_CLOSED",
            "trace_id": trace_id,
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
            rows = await conn.fetch(
                """
                SELECT re.id, re.trace_id, re.trade_journal_id, re.signal_snapshot_id,
                       re.reasoning_text, re.prompt_text, re.context_text, re.evaluated_at,
                       tj.strategy_name, tj.symbol, tj.direction, tj.result, tj.pnl, tj.pnl_pips,
                       ts.timeframe, ts.atr, ts.cisd_m15
                FROM aureus_reasoning_entries re
                LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
                LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id
                WHERE re.trace_id=$1
                """,
                trace_id,
            )
            assert len(rows) == 1
            row = rows[0]
            assert row["trade_journal_id"] is not None
            assert row["signal_snapshot_id"] is not None
            assert row["reasoning_text"]
            assert "reasoning_reuse_joined" in row["reasoning_text"]
            assert "XAUUSD" in row["reasoning_text"]
            assert "BUY" in row["reasoning_text"]
            assert "london" in row["reasoning_text"]
            assert "cisd_m15=1" in row["reasoning_text"]
            assert row["prompt_text"] is None
            assert row["context_text"] is None
            assert row["evaluated_at"] is not None
            assert row["strategy_name"] == "reasoning_reuse_joined"
            assert row["symbol"] == "XAUUSD"
            assert row["direction"] == "BUY"
            assert row["result"] == "WIN"
            assert row["pnl"] == 9.5
            assert row["pnl_pips"] == 400.0
            assert row["timeframe"] == "M15"
            assert row["atr"] == 2.5
            assert row["cisd_m15"] == 1

            insights = await fetch_strategy_reasoning_insights(
                conn,
                "reasoning_reuse_joined",
                symbol="XAUUSD",
                direction="BUY",
                query_text="joined source truth",
                client=StaticEmbeddingClient(),
            )
            assert insights["sample_size"] == 1
            assert insights["success_rate"] == 1.0
            assert insights["avg_reward"] == 400.0
            assert insights["avg_pnl_pips"] == 400.0
            assert insights["recent_lessons"]
            assert "raw prompt" not in str(insights)
            assert "raw context" not in str(insights)

            results = await semantic_search_reasoning_entries(
                conn,
                "joined source truth",
                limit=5,
                client=StaticEmbeddingClient(),
            )
            match = next((item for item in results if item["trace_id"] == trace_id), None)
            assert match is not None
            assert match["strategy_name"] == "reasoning_reuse_joined"
            assert match["symbol"] == "XAUUSD"
            assert match["timeframe"] == "M15"
            assert "prompt_text" not in match
            assert "context_text" not in match

        print(f"PASS reasoning bank reuse DB E2E trace_id={trace_id}")
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, trace_id)
        await pool.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Verify Reasoning Bank joined journal/snapshot reuse")
    parser.add_argument("--dsn", help="Reserved; use AUREUS_DB_DSN for now")
    return parser.parse_args()


def main():
    parse_args()
    asyncio.run(run_e2e())


if __name__ == "__main__":
    main()
