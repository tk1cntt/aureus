import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.state import SymbolState
from engine.signals.tpo import TPOSignal
from engine.tpo_daily_cache import preload_tpo_daily_cache


class _Row(dict):
    def __getattr__(self, item):
        return self[item]


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value
        self.set_calls.append((key, value))


class _FakeDB:
    def __init__(self):
        self.fetch_calls = []

    async def fetch(self, query, symbol, day_start, day_end):
        self.fetch_calls.append((query, symbol, day_start, day_end))
        rows = []
        for i in range(10):
            price = 3000.0 + i
            rows.append(_Row(time=day_start + timedelta(minutes=i), open=price, high=price + 2, low=price - 1, close=price + 0.5, volume=100 + i))
        return rows


def _live_df(now_ts):
    import pandas as pd
    return pd.DataFrame([
        {"t": now_ts - (4 - i) * 60, "o": 3100 + i, "h": 3102 + i, "l": 3099 + i, "c": 3101 + i, "v": 200 + i}
        for i in range(5)
    ])


@pytest.mark.asyncio
async def test_fake_db_redis_preload_path_reaches_tpo_output():
    now_ts = int(datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc).timestamp())
    redis = _FakeRedis()
    db = _FakeDB()
    state = SymbolState("XAUUSD")
    tpo = TPOSignal(symbol="XAUUSD")

    await preload_tpo_daily_cache(db, redis, state, "XAUUSD", now_ts, tpo)
    output = tpo.calculate(_live_df(now_ts), state, symbol="XAUUSD")["value"]

    assert [key for key, _ in redis.set_calls] == [
        "aureus:tpo:daily:XAUUSD:20260525",
        "aureus:tpo:daily:XAUUSD:20260524",
        "aureus:tpo:daily:XAUUSD:20260523",
    ]
    assert sorted(state.tpo_daily_cache.keys()) == ["20260523", "20260524", "20260525"]
    assert output["tpo_d1"] is not None
    assert output["tpo_d2"] is not None
    assert output["tpo_d3"] is not None


def test_live_engine_window_and_limit_unchanged():
    source = Path("engine/live_engine.py").read_text()
    assert "WindowManager(max_window=2000)" in source
    assert source.count("LIMIT 1500") >= 3
    assert "LIMIT 6000" not in source
    assert "max_window=6000" not in source
