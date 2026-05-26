import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.state import SymbolState
from engine.signals.tpo import TPOSignal
from engine.tpo_daily_cache import daily_tpo_key, load_daily_tpo_cache_date, preload_tpo_daily_cache


class _Row(dict):
    def __getattr__(self, item):
        return self[item]


class _FakeRedis:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.set_calls = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value
        self.set_calls.append((key, value))


class _FakeDB:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.fetch_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows


def _rows_for_day(yyyymmdd="20260525", count=12):
    start = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        price = 3300.0 + i
        rows.append(_Row(time=start + timedelta(minutes=i), open=price, high=price + 2, low=price - 1, close=price + 0.5, volume=100 + i))
    return rows


def _valid_payload(symbol="XAUUSD", yyyymmdd="20260525"):
    return {
        "schema_version": "tpo-daily-v1",
        "symbol": symbol,
        "yyyymmdd": yyyymmdd,
        "timeframe": "D1",
        "is_closed": True,
        "bars_count": 12,
        "tpo": {"POC": 3301.0, "VAH": 3302.0, "VAL": 3300.0, "OPEN": 3300.0, "HIGH": 3314.0, "LOW": 3299.0, "CLOSE": 3311.5},
    }


def test_daily_tpo_key_schema_is_only_daily_key():
    assert daily_tpo_key("xauusd", "20260525") == "aureus:tpo:daily:XAUUSD:20260525"


@pytest.mark.asyncio
async def test_valid_redis_json_populates_state_without_db_query():
    key = daily_tpo_key("XAUUSD", "20260525")
    redis = _FakeRedis({key: json.dumps(_valid_payload())})
    db = _FakeDB(_rows_for_day())
    state = SymbolState("XAUUSD")

    block = await load_daily_tpo_cache_date(db, redis, state, "XAUUSD", "20260525", TPOSignal(symbol="XAUUSD"))

    assert block == _valid_payload()["tpo"]
    assert state.tpo_daily_cache["20260525"] == block
    assert db.fetch_calls == []
    assert redis.set_calls == []


@pytest.mark.asyncio
async def test_invalid_redis_json_refills_from_db_and_sets_same_key():
    key = daily_tpo_key("XAUUSD", "20260525")
    redis = _FakeRedis({key: json.dumps({"schema_version": "bad"})})
    db = _FakeDB(_rows_for_day())
    state = SymbolState("XAUUSD")

    block = await load_daily_tpo_cache_date(db, redis, state, "XAUUSD", "20260525", TPOSignal(symbol="XAUUSD"))

    assert block is not None
    assert state.tpo_daily_cache["20260525"] == block
    assert len(db.fetch_calls) == 1
    assert "FROM aureus_candles" in db.fetch_calls[0][0]
    assert redis.set_calls[0][0] == key
    assert list(redis.values.keys()) == [key]


@pytest.mark.asyncio
async def test_missing_db_rows_do_not_write_fake_redis_data():
    redis = _FakeRedis()
    db = _FakeDB([])
    state = SymbolState("XAUUSD")

    block = await load_daily_tpo_cache_date(db, redis, state, "XAUUSD", "20260525", TPOSignal(symbol="XAUUSD"))

    assert block is None
    assert "20260525" not in state.tpo_daily_cache
    assert redis.set_calls == []


def _df_from(start_ts, count):
    rows = []
    for i in range(count):
        price = 3000.0 + (i % 20)
        rows.append({"t": start_ts + i * 60, "o": price, "h": price + 1.0, "l": price - 1.0, "c": price + 0.2, "v": 100 + i})
    return pd.DataFrame(rows)


def test_tpo_signal_prefers_cache_for_d1_d3_and_keeps_d0_live():
    now = int(datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc).timestamp())
    df = _df_from(now - (1499 * 60), 1500)
    state = SymbolState("XAUUSD")
    state.tpo_daily_cache = {
        "20260525": {"POC": 1, "VAH": 2, "VAL": 0, "OPEN": 1, "HIGH": 3, "LOW": 0, "CLOSE": 2},
        "20260524": {"POC": 4, "VAH": 5, "VAL": 3, "OPEN": 4, "HIGH": 6, "LOW": 3, "CLOSE": 5},
        "20260523": {"POC": 7, "VAH": 8, "VAL": 6, "OPEN": 7, "HIGH": 9, "LOW": 6, "CLOSE": 8},
    }

    result = TPOSignal(symbol="XAUUSD").calculate(df, state, symbol="XAUUSD")
    value = result["value"]

    assert value["tpo_d0"] is not None
    assert value["tpo_d0"] != state.tpo_daily_cache["20260525"]
    assert value["tpo_d1"] == state.tpo_daily_cache["20260525"]
    assert value["tpo_d2"] == state.tpo_daily_cache["20260524"]
    assert value["tpo_d3"] == state.tpo_daily_cache["20260523"]
    assert value["tpo_h1"] is not None
    assert value["tpo_m30"] is not None


def test_tpo_signal_fallback_for_missing_cache_date():
    now = int(datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc).timestamp())
    df = _df_from(now - (1499 * 60), 1500)
    state = SymbolState("XAUUSD")
    state.tpo_daily_cache = {"20260525": {"POC": 1, "VAH": 2, "VAL": 0, "OPEN": 1, "HIGH": 3, "LOW": 0, "CLOSE": 2}}

    value = TPOSignal(symbol="XAUUSD").calculate(df, state, symbol="XAUUSD")["value"]

    assert value["tpo_d1"] == state.tpo_daily_cache["20260525"]
    assert value["tpo_d2"] is None
    assert value["tpo_d3"] is None


@pytest.mark.asyncio
async def test_preload_loads_three_closed_dates():
    now = int(datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc).timestamp())
    redis = _FakeRedis()
    db = _FakeDB(_rows_for_day())
    state = SymbolState("XAUUSD")

    await preload_tpo_daily_cache(db, redis, state, "XAUUSD", now, TPOSignal(symbol="XAUUSD"))

    assert sorted(state.tpo_daily_cache.keys()) == ["20260523", "20260524", "20260525"]
    assert [key for key, _ in redis.set_calls] == [
        "aureus:tpo:daily:XAUUSD:20260525",
        "aureus:tpo:daily:XAUUSD:20260524",
        "aureus:tpo:daily:XAUUSD:20260523",
    ]
