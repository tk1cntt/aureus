import argparse
import asyncio
import os
from datetime import datetime

import asyncpg


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _build_parser():
    parser = argparse.ArgumentParser(description="Backfill canonical signal snapshots with archive-before-prune")
    parser.add_argument("--dsn", default=os.getenv("AUREUS_DB_DSN", "postgresql://aureus:aureus@localhost:5433/aureus"))
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--signal-schema-version", default="sig-v2.0.0")
    return parser


async def run_backfill(conn, start: str, end: str, batch_size: int, signal_schema_version: str):
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    rows = await conn.fetch(
        """
        SELECT
            j.id AS trade_journal_id,
            j.trace_id,
            j.ticket,
            j.strategy_name,
            j.symbol,
            COALESCE(ss.timeframe, 'M15') AS timeframe,
            ss.created_at
        FROM aureus_trade_journal j
        LEFT JOIN LATERAL (
            SELECT timeframe, created_at
            FROM aureus_trade_signal_snapshots ss
            WHERE ss.trade_journal_id = j.id
            ORDER BY ss.created_at DESC
            LIMIT 1
        ) ss ON true
        WHERE j.entry_time >= $1
          AND j.entry_time <= $2
        ORDER BY j.id
        LIMIT $3
        """,
        _parse_iso8601(start),
        _parse_iso8601(end),
        batch_size,
    )

    inserted = 0
    for row in rows:

        result = await conn.execute(
            """
            INSERT INTO aureus_trade_signal_snapshots (
                trade_journal_id, trace_id, ticket, strategy_name, symbol,
                timeframe, signal_schema_version, created_at
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8
            )
            ON CONFLICT (trade_journal_id, signal_schema_version) DO NOTHING
            """,
            row["trade_journal_id"],
            row["trace_id"],
            row["ticket"],
            row.get("strategy_name") or "",
            row.get("symbol") or "",
            row.get("timeframe") or "M15",
            signal_schema_version,
            row.get("created_at") or _parse_iso8601(start),
        )
        if result == "INSERT 0 1":
            inserted += 1

    archived = await conn.fetchval("SELECT aureus_archive_and_prune_trade_signal_snapshots(now(), 5000)")
    return {"processed": len(rows), "inserted": inserted, "archived_pruned": int(archived or 0)}


async def _run(args):
    conn = await asyncpg.connect(args.dsn)
    try:
        stats = await run_backfill(conn, args.start, args.end, args.batch_size, args.signal_schema_version)
        print(json.dumps(stats, ensure_ascii=False))
    finally:
        await conn.close()


def main():
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
