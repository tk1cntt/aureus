import argparse
import asyncio
import json
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


def _load_snapshot(path: Path):
    if not path.exists():
        raise ValueError(f"snapshot_not_found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"snapshot_invalid_json: {exc}")

    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("snapshot_invalid_schema: missing rows[]")

    validated = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"snapshot_invalid_schema: row[{idx}] is not object")
        if "symbol" not in row or "strategy_id" not in row or "is_active" not in row:
            raise ValueError(f"snapshot_invalid_schema: row[{idx}] missing symbol/strategy_id/is_active")
        validated.append(
            {
                "symbol": str(row["symbol"]),
                "strategy_id": int(row["strategy_id"]),
                "is_active": bool(row["is_active"]),
            }
        )

    return validated


async def _fetch_current(conn, keys):
    out = {}
    for symbol, strategy_id in keys:
        row = await conn.fetchrow(
            """
            SELECT is_active
            FROM aureus_symbol_strategies
            WHERE symbol = $1 AND strategy_id = $2
            """,
            symbol,
            strategy_id,
        )
        out[(symbol, strategy_id)] = bool(row["is_active"]) if row else None
    return out


async def _run(snapshot_path: str, apply: bool):
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")

    rows = _load_snapshot(Path(snapshot_path))
    keys = [(row["symbol"], row["strategy_id"]) for row in rows]
    expected = {(row["symbol"], row["strategy_id"]): row["is_active"] for row in rows}

    pool = await asyncpg.create_pool(db_dsn, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            current = await _fetch_current(conn, keys)

            changes = []
            for key in keys:
                before = current.get(key)
                target = expected[key]
                if before != target:
                    changes.append(
                        {
                            "symbol": key[0],
                            "strategy_id": key[1],
                            "before": before,
                            "after": target,
                        }
                    )

            report = {
                "mode": "apply" if apply else "preview",
                "snapshot": str(snapshot_path),
                "changes": changes,
                "count": len(changes),
            }

            if not apply:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0

            async with conn.transaction():
                for row in rows:
                    await conn.execute(
                        """
                        UPDATE aureus_symbol_strategies
                        SET is_active = $3
                        WHERE symbol = $1 AND strategy_id = $2
                        """,
                        row["symbol"],
                        row["strategy_id"],
                        row["is_active"],
                    )

            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Rollback strategy assignment is_active state from a snapshot JSON file."
    )
    parser.add_argument("--snapshot", required=True, help="Path to snapshot JSON file.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply rollback. Without this flag script only previews changes.",
    )
    args = parser.parse_args()

    try:
        code = asyncio.run(_run(args.snapshot, args.apply))
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(2)
    except Exception as exc:
        print(f"rollback_error: {exc}")
        raise SystemExit(1)

    raise SystemExit(code)


if __name__ == "__main__":
    main()
