"""Standalone Reasoning Bank embedding worker."""
import argparse
import asyncio
import os

import asyncpg
import redis.asyncio as redis

from reasoning_embeddings import ReasoningEmbeddingClient, ReasoningEmbeddingWorker


async def main_async(args):
    redis_url = args.redis_url or os.environ.get("REDIS_URL", "redis://127.0.0.1:6380")
    db_dsn = args.db_dsn or os.environ.get("AUREUS_DB_DSN")
    if not db_dsn:
        raise SystemExit("AUREUS_DB_DSN is required")

    pool = await asyncpg.create_pool(dsn=db_dsn, min_size=1, max_size=2)
    redis_client = redis.from_url(redis_url, decode_responses=True)
    client = ReasoningEmbeddingClient(
        base_url=os.environ.get("REASONING_EMBEDDING_URL", "http://host.docker.internal:8005"),
        model=os.environ.get("REASONING_EMBEDDING_MODEL"),
        timeout=float(os.environ.get("REASONING_EMBEDDING_TIMEOUT", "10")),
    )
    worker = ReasoningEmbeddingWorker(pool, redis_client, client=client)
    try:
        if args.once:
            return 0 if await worker.process_once(timeout=args.timeout) else 1
        while True:
            try:
                await worker.process_once(timeout=args.timeout)
            except Exception as exc:
                print(f"Reasoning embedding worker loop error: {exc}")
    finally:
        await redis_client.close()
        await pool.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--redis-url")
    parser.add_argument("--db-dsn")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
