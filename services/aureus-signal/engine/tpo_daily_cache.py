from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import pandas as pd

SCHEMA_VERSION = "tpo-daily-v1"
REQUIRED_TPO_FIELDS = ("POC", "VAH", "VAL", "OPEN", "HIGH", "LOW", "CLOSE")


def daily_tpo_key(symbol: str, yyyymmdd: str) -> str:
    return f"aureus:tpo:daily:{str(symbol).upper()}:{yyyymmdd}"


def closed_daily_dates(now_ts: int) -> list[str]:
    current_day = datetime.fromtimestamp(int(now_ts), tz=timezone.utc).date()
    return [(current_day - timedelta(days=days_ago)).strftime("%Y%m%d") for days_ago in (1, 2, 3)]


def _utc_day_bounds(yyyymmdd: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _extract_block(payload: Any, symbol: str, yyyymmdd: str) -> Optional[Dict[str, Any]]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if str(payload.get("symbol", "")).upper() != str(symbol).upper():
        return None
    if payload.get("timeframe") != "D1" or payload.get("yyyymmdd") != yyyymmdd:
        return None
    if payload.get("is_closed") is not True:
        return None
    try:
        if int(payload.get("bars_count", 0)) <= 0:
            return None
    except Exception:
        return None
    block = payload.get("tpo")
    if not isinstance(block, dict):
        return None
    for field in REQUIRED_TPO_FIELDS:
        if block.get(field) is None:
            return None
    return block


async def _fetch_daily_rows(db_pool: Any, symbol: str, yyyymmdd: str) -> list[Any]:
    day_start, day_end = _utc_day_bounds(yyyymmdd)
    return list(await db_pool.fetch(
        """
        SELECT time, open, high, low, close, volume
        FROM aureus_candles
        WHERE symbol = $1 AND timeframe = 'M1' AND time >= $2 AND time < $3
        ORDER BY time ASC
        """,
        symbol,
        day_start,
        day_end,
    ))


def _rows_to_df(rows: list[Any]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "t": int(row["time"].timestamp()),
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
            "v": float(row["volume"]),
        }
        for row in rows
    ], columns=["t", "o", "h", "l", "c", "v"])


async def load_daily_tpo_cache_date(db_pool: Any, redis_client: Any, state: Any, symbol: str, yyyymmdd: str, tpo_signal: Any) -> Optional[Dict[str, Any]]:
    if not hasattr(state, "tpo_daily_cache") or not isinstance(getattr(state, "tpo_daily_cache"), dict):
        state.tpo_daily_cache = {}

    key = daily_tpo_key(symbol, yyyymmdd)
    cached = await redis_client.get(key)
    block = _extract_block(cached, symbol, yyyymmdd)
    if block is not None:
        state.tpo_daily_cache[yyyymmdd] = block
        return block

    rows = await _fetch_daily_rows(db_pool, symbol, yyyymmdd)
    if not rows:
        return None

    df = _rows_to_df(rows)
    block = tpo_signal._build_tpo_block(df, symbol=symbol)
    if block is None:
        return None

    payload = {
        "schema_version": SCHEMA_VERSION,
        "symbol": str(symbol).upper(),
        "yyyymmdd": yyyymmdd,
        "timeframe": "D1",
        "is_closed": True,
        "bars_count": len(df),
        "tpo": block,
    }
    await redis_client.set(key, json.dumps(payload, default=str))
    state.tpo_daily_cache[yyyymmdd] = block
    return block


async def preload_tpo_daily_cache(db_pool: Any, redis_client: Any, state: Any, symbol: str, now_ts: int, tpo_signal: Any) -> None:
    for yyyymmdd in closed_daily_dates(now_ts):
        await load_daily_tpo_cache_date(db_pool, redis_client, state, symbol, yyyymmdd, tpo_signal)
