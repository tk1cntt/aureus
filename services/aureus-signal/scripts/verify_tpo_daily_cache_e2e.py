import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SIGNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIGNAL_ROOT))

from engine.state import SymbolState
from engine.signals.tpo import TPOSignal
from engine.tpo_daily_cache import closed_daily_dates, daily_tpo_key, preload_tpo_daily_cache


async def _ensure_rows(pool, symbol, yyyymmdd):
    start = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=timezone.utc)
    existing = await pool.fetchval(
        "SELECT COUNT(*) FROM aureus_candles WHERE symbol=$1 AND timeframe='M1' AND time >= $2 AND time < $3",
        symbol,
        start,
        start + timedelta(days=1),
    )
    if int(existing or 0) > 0:
        return
    rows = []
    for i in range(60):
        price = 3300.0 + (i * 0.1)
        rows.append((start + timedelta(minutes=i), symbol, price, price + 1.0, price - 1.0, price + 0.2, 100 + i, "M1"))
    await pool.executemany(
        """
        INSERT INTO aureus_candles (time, symbol, open, high, low, close, volume, timeframe)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE
        SET open=$3, high=$4, low=$5, close=$6, volume=$7
        """,
        rows,
    )


def _live_df(now_ts):
    return pd.DataFrame([
        {"t": now_ts - (9 - i) * 60, "o": 3400 + i, "h": 3402 + i, "l": 3399 + i, "c": 3401 + i, "v": 200 + i}
        for i in range(10)
    ])


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--dsn", required=True)
    args = parser.parse_args()

    import asyncpg
    import redis.asyncio as redis

    now_ts = int(datetime.now(timezone.utc).timestamp())
    dates = closed_daily_dates(now_ts)
    pool = await asyncpg.create_pool(args.dsn, min_size=1, max_size=2)
    redis_client = redis.from_url(args.redis_url, decode_responses=True)
    try:
        for yyyymmdd in dates:
            await _ensure_rows(pool, args.symbol, yyyymmdd)
            await redis_client.delete(daily_tpo_key(args.symbol, yyyymmdd))

        state = SymbolState(args.symbol)
        tpo = TPOSignal(symbol=args.symbol)
        await preload_tpo_daily_cache(pool, redis_client, state, args.symbol, now_ts, tpo)

        for yyyymmdd in dates:
            key = daily_tpo_key(args.symbol, yyyymmdd)
            raw = await redis_client.get(key)
            assert raw, f"missing redis key {key}"
            payload = json.loads(raw)
            assert payload["schema_version"] == "tpo-daily-v1"
            assert yyyymmdd in state.tpo_daily_cache

        output = tpo.calculate(_live_df(now_ts), state, symbol=args.symbol)["value"]
        assert output["tpo_d1"] is not None
        assert output["tpo_d2"] is not None
        assert output["tpo_d3"] is not None
        print(json.dumps({"ok": True, "symbol": args.symbol, "dates": dates}, ensure_ascii=False))
    finally:
        await redis_client.aclose()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
