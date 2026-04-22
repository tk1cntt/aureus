import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

import asyncpg

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
            -- TODO(phase-55 follow-up): replace snapshot timeframe fallback with canonical aureus_trade_journal.timeframe lineage column.
            COALESCE(ss.signal_snapshot->>'timeframe', 'M1') AS timeframe,
            ss.signal_snapshot,
            ss.cisd_direction,
            ss.ema21,
            ss.ema55,
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
            SELECT signal_snapshot, cisd_direction, ema21, ema55
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
            row.get("timeframe") or "",
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

        signal_snapshot = row.get("signal_snapshot") or {}

        sig_insert_result = await conn.execute(
            """
            INSERT INTO aureus_trade_signal_snapshots (
                trade_journal_id, trace_id, ticket, strategy_name, symbol,
                atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200, vol_sma_20,
                session, candle_color_d1, candle_color_h1, candle_color_m30,
                candle_color_m15, candle_color_m5,
                bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn,
                bb_m30_up, bb_m30_dn, bb_h1_up, bb_h1_dn,
                cisd_m5, cisd_m15, cisd_m30, cisd_h1
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17,
                $18, $19,
                $20, $21, $22, $23, $24, $25,
                $26, $27, $28, $29,
                $30, $31, $32, $33
            )
            ON CONFLICT (trade_journal_id) DO NOTHING
            """,
            row["id"],
            row["trace_id"],
            row["ticket"],
            row.get("strategy_name") or "",
            row.get("symbol") or "",
            signal_snapshot.get("atr"),
            signal_snapshot.get("ema_21", signal_snapshot.get("ema21")),
            signal_snapshot.get("ema_34"),
            signal_snapshot.get("ema_55", signal_snapshot.get("ema55")),
            signal_snapshot.get("ema_89"),
            signal_snapshot.get("ema_100"),
            signal_snapshot.get("ema_200"),
            signal_snapshot.get("vol_sma_20"),
            signal_snapshot.get("session"),
            signal_snapshot.get("candle_color_d1"),
            signal_snapshot.get("candle_color_h1"),
            signal_snapshot.get("candle_color_m30"),
            signal_snapshot.get("candle_color_m15"),
            signal_snapshot.get("candle_color_m5"),
            signal_snapshot.get("bb_m1_up"),
            signal_snapshot.get("bb_m1_dn"),
            signal_snapshot.get("bb_m5_up"),
            signal_snapshot.get("bb_m5_dn"),
            signal_snapshot.get("bb_m15_up"),
            signal_snapshot.get("bb_m15_dn"),
            signal_snapshot.get("bb_m30_up"),
            signal_snapshot.get("bb_m30_dn"),
            signal_snapshot.get("bb_h1_up"),
            signal_snapshot.get("bb_h1_dn"),
            signal_snapshot.get("cisd_m5"),
            signal_snapshot.get("cisd_m15"),
            signal_snapshot.get("cisd_m30"),
            signal_snapshot.get("cisd_h1"),
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
