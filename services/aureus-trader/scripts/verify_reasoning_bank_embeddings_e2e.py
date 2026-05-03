"""DB/runtime E2E verification for Reasoning Bank embeddings."""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backfill_reasoning_embeddings import _ensure_schema
from config import load_config
from journal import TradeJournalManager
from reasoning_embeddings import semantic_search_reasoning_entries, verify_embedding_service


async def main():
    cfg = load_config()
    dsn = os.getenv(
        "AUREUS_DB_DSN",
        f"postgresql://{cfg.db_user}:{cfg.db_password}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}",
    )
    embedding_base_url = os.getenv("AUREUS_EMBEDDING_BASE_URL", "http://localhost:8005")
    client = verify_embedding_service(embedding_base_url)
    trace_id = f"e2e-reasoning-embedding-{uuid.uuid4().hex[:12]}"
    legacy_trace_id = f"e2e-reasoning-legacy-{uuid.uuid4().hex[:12]}"
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    journal = TradeJournalManager(pool)

    try:
        async with pool.acquire() as conn:
            await _ensure_schema(conn)
            await conn.execute(
                """
                INSERT INTO aureus_trades (trace_id, symbol, direction, entry_type, entry_price, status)
                VALUES ($1, 'XAUUSD', 'BUY', 'MARKET', 2320.5, 'TEST'),
                       ($2, 'XAUUSD', 'BUY', 'MARKET', 2320.5, 'TEST')
                ON CONFLICT (trace_id) DO NOTHING
                """,
                trace_id,
                legacy_trace_id,
            )
            await conn.execute(
                """
                INSERT INTO aureus_reasoning_entries (
                    trace_id, strategy_name, symbol, direction, prompt_digest, input_context_hash
                ) VALUES ($1, 'legacy_hash_only', 'XAUUSD', 'BUY', 'digest-only', 'hash-only')
                """,
                legacy_trace_id,
            )

        assert await journal.on_strategy_match({
            "type": "STRATEGY_MATCH",
            "trace_id": trace_id,
            "data": {
                "trace_id": trace_id,
                "strategy_name": "reasoning_embedding_e2e",
                "strategy_id": 26050301,
                "direction": "BUY",
                "symbol": "XAUUSD",
                "score": 0.91,
                "active_signals": [{"tag": "cisd_bull", "status": "active"}],
                "context_filters": {"session": "london"},
                "reasoning": "CISD sweep bullish continuation setup",
                "prompt_text": "Evaluate bullish continuation after liquidity sweep",
                "context_text": "XAUUSD London session with CISD bullish confirmation",
                "prompt_digest": "must-not-embed",
                "input_context_hash": "must-not-embed",
            },
        })

        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM aureus_reasoning_entries WHERE trace_id=$1", trace_id)
            assert row["prompt_text"] == "Evaluate bullish continuation after liquidity sweep"
            assert row["context_text"] == "XAUUSD London session with CISD bullish confirmation"
            assert row["reasoning_embedding"] is not None
            legacy = await conn.fetchrow("SELECT prompt_embedding, context_embedding FROM aureus_reasoning_entries WHERE trace_id=$1", legacy_trace_id)
            assert legacy["prompt_embedding"] is None
            assert legacy["context_embedding"] is None
            rows = await semantic_search_reasoning_entries(conn, "bullish CISD liquidity sweep", limit=5, client=client)
            assert any(result["trace_id"] == trace_id for result in rows)

        print(f"PASS reasoning bank embeddings DB E2E trace_id={trace_id} legacy_trace_id={legacy_trace_id}")
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM aureus_reasoning_entries WHERE trace_id IN ($1, $2)", trace_id, legacy_trace_id)
            await conn.execute("DELETE FROM aureus_trade_journal WHERE trace_id IN ($1, $2)", trace_id, legacy_trace_id)
            await conn.execute("DELETE FROM aureus_trades WHERE trace_id IN ($1, $2)", trace_id, legacy_trace_id)
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
