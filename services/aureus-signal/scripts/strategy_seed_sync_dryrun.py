import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

CURRENT_DIR = Path(__file__).resolve().parent
APP_ROOT = CURRENT_DIR.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from engine.strategies.seed_strategies import seed_system_strategies


class _DryRunRollback(Exception):
    pass


async def _fetch_assignments(conn):
    rows = await conn.fetch(
        """
        SELECT symbol, strategy_id, is_active
        FROM aureus_symbol_strategies
        ORDER BY symbol, strategy_id
        """
    )
    return [
        {
            "symbol": row["symbol"],
            "strategy_id": int(row["strategy_id"]),
            "is_active": bool(row["is_active"]),
        }
        for row in rows
    ]


def _index(items):
    return {(item["symbol"], item["strategy_id"]): bool(item["is_active"]) for item in items}


def _compute_diff(before, after):
    before_map = _index(before)
    after_map = _index(after)
    keys = sorted(set(before_map.keys()) | set(after_map.keys()))

    activate = []
    deactivate = []
    unchanged = []
    for symbol, strategy_id in keys:
        prev = before_map.get((symbol, strategy_id))
        nxt = after_map.get((symbol, strategy_id))
        if nxt is True and prev is not True:
            activate.append({"symbol": symbol, "strategy_id": strategy_id, "before": prev, "after": True})
        elif prev is True and nxt is not True:
            deactivate.append({"symbol": symbol, "strategy_id": strategy_id, "before": True, "after": nxt})
        else:
            unchanged.append({"symbol": symbol, "strategy_id": strategy_id, "before": prev, "after": nxt})

    return {
        "counts": {
            "activate": len(activate),
            "deactivate": len(deactivate),
            "unchanged": len(unchanged),
        },
        "activate": activate,
        "deactivate": deactivate,
        "unchanged": unchanged,
    }


def _snapshot_path(base_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return base_dir / f"seed-sync-{ts}.json"


async def _run(output_path: str | None):
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")

    snapshots_dir = Path(__file__).resolve().parent / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = _snapshot_path(snapshots_dir)

    pool = await asyncpg.create_pool(db_dsn, min_size=1, max_size=2)
    before = []
    after = []
    try:
        async with pool.acquire() as conn:
            tx = conn.transaction()
            await tx.start()
            try:
                before = await _fetch_assignments(conn)
                await seed_system_strategies(conn=conn)
                after = await _fetch_assignments(conn)
                raise _DryRunRollback()
            except _DryRunRollback:
                await tx.rollback()

        diff = _compute_diff(before, after)
        snapshot_payload = {
            "snapshot_type": "seed_sync_precheck",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rows": before,
        }
        snapshot_file.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        report = {
            "mode": "dry-run",
            "snapshot": str(snapshot_file),
            "diff": diff,
        }

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Preview strategy seed sync diff without mutating database."
    )
    parser.add_argument("--output", help="Optional path to write dry-run diff JSON report.")
    args = parser.parse_args()

    try:
        code = asyncio.run(_run(args.output))
    except Exception as exc:
        print(f"dryrun_error: {exc}")
        raise SystemExit(1)

    raise SystemExit(code)


if __name__ == "__main__":
    main()
