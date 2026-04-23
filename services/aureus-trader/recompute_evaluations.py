import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(__file__)
SIGNAL_ENGINE_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "aureus-signal", "engine", "scoring"))
if SIGNAL_ENGINE_PATH not in sys.path:
    sys.path.insert(0, SIGNAL_ENGINE_PATH)

from compute import compute_trade_score


def _parse_iso8601(value: str) -> datetime:
    if not value:
        raise ValueError("datetime value is required")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_args(args):
    if not args.score_version:
        raise ValueError("--score-version is required")
    if not args.signal_schema_version:
        raise ValueError("--signal-schema-version is required")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    start_dt = _parse_iso8601(args.start)
    end_dt = _parse_iso8601(args.end)
    if start_dt > end_dt:
        raise ValueError("--start must be <= --end")


def _normalize_timeframe(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _select_timeframe_with_lineage(row):
    lineage_timeframe = _normalize_timeframe(row.get("lineage_timeframe"))
    if lineage_timeframe:
        return lineage_timeframe, "lineage_timeframe"

    journal_timeframe = _normalize_timeframe(row.get("journal_timeframe"))
    if journal_timeframe:
        return journal_timeframe, "journal_timeframe"

    snapshot_timeframe = _normalize_timeframe(row.get("snapshot_timeframe"))
    if snapshot_timeframe:
        return snapshot_timeframe, "snapshot_timeframe"

    logger.warning(
        "TIMEFRAME_LINEAGE_FALLBACK: trace_id=%s trade_journal_id=%s fallback_source=default_M1",
        row.get("trace_id"),
        row.get("id"),
    )
    return "M1", "default_M1"


async def recompute_batch(conn, score_version, signal_schema_version, start, end, batch_size=500, weights_snapshot=None):
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if not score_version:
        raise ValueError("score_version is required")
    if not signal_schema_version:
        raise ValueError("signal_schema_version is required")

    rows = await conn.fetch(
        """
        SELECT
            j.id,
            j.trace_id,
            j.ticket,
            j.strategy_name,
            j.symbol,
            j.timeframe AS journal_timeframe,
            ss.timeframe AS snapshot_timeframe,
            ss.signal_snapshot,
            ss.cisd_direction,
            ss.ema21,
            ss.ema55,
            ss.created_at,
            ev.timeframe AS lineage_timeframe,
            ev.score_breakdown
        FROM aureus_trade_journal j
        LEFT JOIN LATERAL (
            SELECT score_breakdown
            FROM aureus_trade_evaluations
            WHERE trade_journal_id = j.id
            ORDER BY evaluated_at DESC
            LIMIT 1
        ) ev ON true
        LEFT JOIN LATERAL (
            SELECT timeframe, signal_snapshot, cisd_direction, ema21, ema55, created_at
            FROM aureus_trade_signal_snapshots
            WHERE trade_journal_id = j.id
            ORDER BY created_at DESC
            LIMIT 1
        ) ss ON true
        WHERE j.status IN ('EXECUTED', 'CLOSED')
          AND j.entry_time >= $1
          AND j.entry_time <= $2
        ORDER BY j.id
        LIMIT $3
        """,
        _parse_iso8601(start),
        _parse_iso8601(end),
        batch_size,
    )

    eval_inserted = 0
    sig_inserted = 0
    immutable_weights = dict(weights_snapshot or {})

    for row in rows:
        timeframe, _timeframe_source = _select_timeframe_with_lineage(row)

        score_input = {
            "quality_gate_passed": True,
            "criteria": row.get("score_breakdown") or {},
        }
        score_result = compute_trade_score(score_input, score_version, immutable_weights)

        eval_insert_result = await conn.execute(
            """
            INSERT INTO aureus_trade_evaluations (
                trade_journal_id, trace_id, ticket, score_version, score_total,
                score_breakdown, weights_snapshot, missing_data_policy,
                strategy_name, symbol, timeframe, computed_at, evaluated_at, is_current
            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10, $11, now(), now(), TRUE)
            ON CONFLICT (trade_journal_id, score_version) DO NOTHING
            """,
            row["id"],
            row["trace_id"],
            row["ticket"],
            score_version,
            float(score_result.get("score_total") or 0.0),
            json.dumps(score_result),
            json.dumps(score_result.get("weights_snapshot") or immutable_weights),
            score_result.get("missing_data_policy") or "impute_neutral_and_flag",
            row.get("strategy_name") or "",
            row.get("symbol") or "",
            timeframe,
        )

        if eval_insert_result == "INSERT 0 1":
            eval_inserted += 1
            await conn.execute(
                """
                UPDATE aureus_trade_evaluations
                SET is_current = FALSE
                WHERE trade_journal_id = $1
                  AND score_version <> $2
                """,
                row["id"],
                score_version,
            )
            await conn.execute(
                """
                UPDATE aureus_trade_evaluations
                SET is_current = TRUE
                WHERE trade_journal_id = $1
                  AND score_version = $2
                """,
                row["id"],
                score_version,
            )

        sig_insert_result = await conn.execute(
            """
            INSERT INTO aureus_trade_signal_snapshots (
                trade_journal_id, trace_id, ticket, strategy_name, symbol,
                timeframe, signal_schema_version, signal_snapshot,
                cisd_direction, ema21, ema55, created_at
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8::jsonb,
                $9, $10, $11, $12
            )
            ON CONFLICT (trade_journal_id, signal_schema_version) DO NOTHING
            """,
            row["id"],
            row["trace_id"],
            row["ticket"],
            row.get("strategy_name") or "",
            row.get("symbol") or "",
            timeframe,
            signal_schema_version,
            json.dumps(row.get("signal_snapshot") or {}),
            row.get("cisd_direction"),
            row.get("ema21"),
            row.get("ema55"),
            row.get("created_at") or _parse_iso8601(start),
        )

        if sig_insert_result == "INSERT 0 1":
            sig_inserted += 1

    return {
        "processed": len(rows),
        "evaluation_inserted": eval_inserted,
        "signal_snapshot_inserted": sig_inserted,
    }


async def _run(args):
    _validate_args(args)
    pool = await asyncpg.create_pool(dsn=args.dsn)
    try:
        async with pool.acquire() as conn:
            stats = await recompute_batch(
                conn=conn,
                score_version=args.score_version,
                signal_schema_version=args.signal_schema_version,
                start=args.start,
                end=args.end,
                batch_size=args.batch_size,
                weights_snapshot=json.loads(args.weights_snapshot),
            )
            print(json.dumps(stats, ensure_ascii=False))
    finally:
        await pool.close()


def _build_parser():
    parser = argparse.ArgumentParser(description="Recompute trade evaluations and signal snapshots")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--score-version", required=True)
    parser.add_argument("--signal-schema-version", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--weights-snapshot",
        default='{"profit_outcome":0.30,"signal_quality":0.35,"timing_quality":0.20,"volatility_session":0.15}',
    )
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
