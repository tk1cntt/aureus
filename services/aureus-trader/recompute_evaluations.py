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

def _parse_iso8601(value: str) -> datetime:
    if not value:
        raise ValueError("datetime value is required")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_args(args):
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
            'M1' AS timeframe,
            ss.atr,
            ss.ema_21,
            ss.ema_34,
            ss.ema_55,
            ss.ema_89,
            ss.ema_100,
            ss.ema_200,
            ss.vol_sma_20,
            ss.session,
            ss.candle_color_d1,
            ss.candle_color_h1,
            ss.candle_color_m30,
            ss.candle_color_m15,
            ss.candle_color_m5,
            ss.bb_m1_up,
            ss.bb_m1_dn,
            ss.bb_m5_up,
            ss.bb_m5_dn,
            ss.bb_m15_up,
            ss.bb_m15_dn,
            ss.bb_m30_up,
            ss.bb_m30_dn,
            ss.bb_h1_up,
            ss.bb_h1_dn,
            ss.cisd_m5,
            ss.cisd_m15,
            ss.cisd_m30,
            ss.cisd_h1
        FROM aureus_trade_journal j
        LEFT JOIN LATERAL (
            SELECT atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200, vol_sma_20,
                   session, candle_color_d1, candle_color_h1, candle_color_m30, candle_color_m15, candle_color_m5,
                   bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn, bb_m30_up, bb_m30_dn,
                   bb_h1_up, bb_h1_dn, cisd_m5, cisd_m15, cisd_m30, cisd_h1
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

    sig_inserted = 0
    for row in rows:
        sig_insert_result = await conn.execute(
            """
            INSERT INTO aureus_trade_signal_snapshots (
                trade_journal_id, trace_id, ticket, strategy_name, symbol,
                timeframe, signal_schema_version,
                atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200, vol_sma_20,
                session, candle_color_d1, candle_color_h1, candle_color_m30,
                candle_color_m15, candle_color_m5,
                bb_m1_up, bb_m1_dn, bb_m5_up, bb_m5_dn, bb_m15_up, bb_m15_dn,
                bb_m30_up, bb_m30_dn, bb_h1_up, bb_h1_dn,
                cisd_m5, cisd_m15, cisd_m30, cisd_h1,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7,
                $8, $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19,
                $20, $21,
                $22, $23, $24, $25, $26, $27,
                $28, $29, $30, $31,
                $32, $33, $34, $35,
                now()
            )
            ON CONFLICT (trade_journal_id, signal_schema_version) DO NOTHING
            """,
            row["id"],
            row["trace_id"],
            row["ticket"],
            row.get("strategy_name") or "",
            row.get("symbol") or "",
            row.get("timeframe") or "M1",
            signal_schema_version,
            row.get("atr"),
            row.get("ema_21"),
            row.get("ema_34"),
            row.get("ema_55"),
            row.get("ema_89"),
            row.get("ema_100"),
            row.get("ema_200"),
            row.get("vol_sma_20"),
            row.get("session"),
            row.get("candle_color_d1"),
            row.get("candle_color_h1"),
            row.get("candle_color_m30"),
            row.get("candle_color_m15"),
            row.get("candle_color_m5"),
            row.get("bb_m1_up"),
            row.get("bb_m1_dn"),
            row.get("bb_m5_up"),
            row.get("bb_m5_dn"),
            row.get("bb_m15_up"),
            row.get("bb_m15_dn"),
            row.get("bb_m30_up"),
            row.get("bb_m30_dn"),
            row.get("bb_h1_up"),
            row.get("bb_h1_dn"),
            row.get("cisd_m5"),
            row.get("cisd_m15"),
            row.get("cisd_m30"),
            row.get("cisd_h1"),
        )

        if sig_insert_result == "INSERT 0 1":
            sig_inserted += 1

    return {
        "processed": len(rows),
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
                weights_snapshot=None,
            )
            print(json.dumps(stats, ensure_ascii=False))
    finally:
        await pool.close()


def _build_parser():
    parser = argparse.ArgumentParser(description="Backfill trade signal snapshots")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--score-version", required=False)
    parser.add_argument("--signal-schema-version", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
