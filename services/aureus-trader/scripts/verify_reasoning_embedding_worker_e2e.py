"""Strict DB/Redis E2E for Reasoning Bank embedding worker."""
import argparse
import asyncio
import os
import sys

import asyncpg
import redis.asyncio as redis

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from reasoning_embeddings import ReasoningEmbeddingClient, ReasoningEmbeddingWorker, enqueue_reasoning_embedding_job


class StaticEmbeddingClient:
    model = "e2e-static"

    def embed(self, text):
        if not text:
            raise RuntimeError("empty text")
        return [0.1, 0.2, 0.3]


async def run(args):
    dsn = args.db_dsn or os.environ.get("AUREUS_DB_DSN")
    if not dsn:
        raise RuntimeError("AUREUS_DB_DSN is required")
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    redis_client = redis.from_url(args.redis_url, decode_responses=True)
    trace_id = "reasoning-worker-e2e"
    try:
        async with pool.acquire() as conn:
            entry_id = await conn.fetchval(
                """
                INSERT INTO aureus_reasoning_entries (trace_id, strategy_name, symbol, direction, reasoning_text)
                VALUES ($1, 'e2e_strategy', 'XAUUSD', 'BUY', 'worker e2e reasoning')
                RETURNING id
                """,
                trace_id,
            )
        enqueued = await enqueue_reasoning_embedding_job(
            redis_client,
            entry_id,
            {"reasoning_text": "worker e2e reasoning"},
            trace_id,
        )
        if not enqueued:
            raise RuntimeError("enqueue failed")
        client = StaticEmbeddingClient() if args.static_embedding else ReasoningEmbeddingClient()
        worker = ReasoningEmbeddingWorker(pool, redis_client, client=client)
        processed = await worker.process_once(timeout=args.timeout)
        if not processed:
            raise RuntimeError("worker did not process job")
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT reasoning_embedding, embedding_model FROM aureus_reasoning_entries WHERE id = $1",
                entry_id,
            )
        if row is None or row["reasoning_embedding"] is None:
            raise RuntimeError("reasoning_embedding missing after worker run")
        print("PASS reasoning embedding worker E2E")
    finally:
        await redis_client.close()
        await pool.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://127.0.0.1:6380"))
    parser.add_argument("--db-dsn")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--static-embedding", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
