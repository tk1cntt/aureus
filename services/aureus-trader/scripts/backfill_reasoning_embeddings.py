"""Backfill Reasoning Bank embeddings from real text fields only."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_config
from reasoning_embeddings import ReasoningEmbeddingClient, embed_reasoning_entry, select_embedding_sources, verify_embedding_service


async def _ensure_schema(conn):
    base = Path(__file__).resolve().parents[2] / "aureus-db-writer" / "migrations"
    await conn.execute((base / "add_reasoning_entries.sql").read_text(encoding="utf-8"))
    await conn.execute((base / "add_reasoning_entries_embeddings.sql").read_text(encoding="utf-8"))


def _dsn():
    cfg = load_config()
    return os.getenv(
        "AUREUS_DB_DSN",
        f"postgresql://{cfg.db_user}:{cfg.db_password}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}",
    )


async def backfill(limit=100, base_url="http://localhost:8005"):
    client = verify_embedding_service(base_url)
    pool = await asyncpg.create_pool(dsn=_dsn(), min_size=1, max_size=2)
    stats = {"updated_rows": 0, "updated_embeddings": 0, "skipped_rows": 0, "unavailable_raw_prompt_context": 0}
    try:
        async with pool.acquire() as conn:
            await _ensure_schema(conn)
            rows = await conn.fetch(
                """
                SELECT id, reasoning_text, prompt_text, context_text,
                       prompt_digest, decision_digest, input_context_hash
                FROM aureus_reasoning_entries
                WHERE reasoning_embedding IS NULL
                   OR (prompt_text IS NOT NULL AND prompt_embedding IS NULL)
                   OR (context_text IS NOT NULL AND context_embedding IS NULL)
                ORDER BY id
                LIMIT $1
                """,
                int(limit),
            )
            for row in rows:
                data = dict(row)
                sources = select_embedding_sources(data)
                if not data.get("prompt_text") and not data.get("context_text") and (data.get("prompt_digest") or data.get("input_context_hash")):
                    stats["unavailable_raw_prompt_context"] += 1
                if not sources:
                    stats["skipped_rows"] += 1
                    continue
                updated = await embed_reasoning_entry(conn, data["id"], sources, client)
                if updated:
                    stats["updated_rows"] += 1
                    stats["updated_embeddings"] += updated
    finally:
        await pool.close()
    return stats


async def main_async(args):
    stats = await backfill(limit=args.limit, base_url=args.base_url)
    print(
        "PASS reasoning embedding backfill "
        f"updated_rows={stats['updated_rows']} "
        f"updated_embeddings={stats['updated_embeddings']} "
        f"skipped_rows={stats['skipped_rows']} "
        f"unavailable_raw_prompt_context={stats['unavailable_raw_prompt_context']}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--base-url", default="http://localhost:8005")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
