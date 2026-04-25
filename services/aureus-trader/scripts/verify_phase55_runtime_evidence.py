import argparse
import json
from datetime import datetime, timezone

import asyncpg

REQUIRED_TABLES = [
    "aureus_trade_signal_snapshots",
]
REMOVED_TABLES = [
    "aureus_trade_evaluations",
]

REQUIRED_INDEXES = [
    "uq_trade_snapshot_trade_schema",
    "idx_trade_snapshot_symbol_tf_created_at",
]


async def fetch_runtime_evidence(conn):
    removed_table_rows = await conn.fetch(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename = ANY($1::text[])
        ORDER BY tablename
        """,
        REMOVED_TABLES,
    )
    present_removed_tables = [row["tablename"] for row in removed_table_rows]

    table_rows = await conn.fetch(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename = ANY($1::text[])
        ORDER BY tablename
        """,
        REQUIRED_TABLES,
    )
    present_tables = [row["tablename"] for row in table_rows]

    index_rows = await conn.fetch(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename IN ('aureus_trade_signal_snapshots')
          AND indexname = ANY($1::text[])
        ORDER BY indexname
        """,
        REQUIRED_INDEXES,
    )
    present_indexes = [row["indexname"] for row in index_rows]

    snapshot_stats = await conn.fetchrow(
        """
        SELECT COUNT(*)::bigint AS row_count, MAX(created_at) AS latest_at
        FROM aureus_trade_signal_snapshots
        """
    )

    latest_snapshot_rows = await conn.fetch(
        """
        SELECT trace_id, symbol, timeframe, signal_schema_version, created_at
        FROM aureus_trade_signal_snapshots
        ORDER BY created_at DESC NULLS LAST
        LIMIT 5
        """
    )

    def _iso(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "required_tables": REQUIRED_TABLES,
        "removed_tables": REMOVED_TABLES,
        "present_tables": present_tables,
        "present_removed_tables": present_removed_tables,
        "missing_tables": [t for t in REQUIRED_TABLES if t not in present_tables],
        "required_indexes": REQUIRED_INDEXES,
        "present_indexes": present_indexes,
        "missing_indexes": [i for i in REQUIRED_INDEXES if i not in present_indexes],
        "snapshot_stats": {
            "row_count": int(snapshot_stats["row_count"] or 0),
            "latest_at": _iso(snapshot_stats["latest_at"]),
        },
        "latest_snapshot_rows": [
            {
                "trace_id": row["trace_id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "signal_schema_version": row["signal_schema_version"],
                "created_at": _iso(row["created_at"]),
            }
            for row in latest_snapshot_rows
        ],
    }

    evidence["tables_ok"] = len(evidence["missing_tables"]) == 0 and len(evidence["present_removed_tables"]) == 0
    evidence["indexes_ok"] = len(evidence["missing_indexes"]) == 0
    evidence["latest_rows_ok"] = (
        evidence["snapshot_stats"]["row_count"] > 0
        and len(evidence["latest_snapshot_rows"]) > 0
    )

    return evidence


async def run(args):
    conn = await asyncpg.connect(dsn=args.dsn)
    try:
        evidence = await fetch_runtime_evidence(conn)
    finally:
        await conn.close()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(json.dumps(evidence, ensure_ascii=False))

    if not evidence["tables_ok"]:
        raise SystemExit("Runtime table state invalid: required snapshot table missing or removed evaluations table still present")
    if not evidence["indexes_ok"]:
        raise SystemExit("Missing required runtime indexes")
    if not evidence["latest_rows_ok"]:
        raise SystemExit("Runtime evidence rows are missing")


def build_parser():
    parser = argparse.ArgumentParser(description="Verify Phase 55 runtime DB evidence")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main():
    import asyncio

    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
