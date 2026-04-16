from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd

from engine.snapshot_utils import build_snapshot, insert_single_snapshot, batch_insert_snapshots


class _DummyAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyPool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _DummyAcquire(self._conn)


def _make_state():
    return SimpleNamespace(
        symbol="XAUUSD",
        atr=1.2,
        emas={21: {"current": 1.0}, 34: {"current": 1.1}, 55: {"current": 1.2}, 89: {"current": 1.3}, 100: {"current": 1.4}, 200: {"current": 1.5}},
        vol_sma_20=1500.0,
        htf_trend="BULLISH",
        market_regime="SIDEWAYS",
        current_session="LONDON",
        transient_signals={},
        obs=[],
        swing_points=[],
        strategy_progress={},
        aci=55,
        sentiment="NEUTRAL",
        narrative="ok",
    )


def _make_m1_df(rows: int = 25):
    data = []
    base = 100.0
    for i in range(rows):
        open_price = base + (i * 0.1)
        close_price = open_price + 0.05
        data.append({"t": i * 60, "o": open_price, "h": close_price + 0.1, "l": open_price - 0.1, "c": close_price, "v": 100 + i})
    return pd.DataFrame(data)


def test_build_snapshot_contains_new_mtf_fields_and_keeps_old_fields():
    state = _make_state()
    candle = {"t": 1700000000, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "symbol": "XAUUSD"}
    df = _make_m1_df(25)

    snap = build_snapshot(state, candle, m1_df=df, digits=2)

    for key in ["candle_color_d1", "candle_color_h1", "candle_color_m30", "candle_color_m15", "candle_color_m5", "bb_m1", "bb_m5", "bb_m15", "bb_m30", "bb_h1"]:
        assert key in snap

    for key in ["ema_21", "ema_200", "vol_sma_20", "htf_trend", "strategy_progress"]:
        assert key in snap


def test_insert_single_snapshot_query_contains_new_columns():
    state = _make_state()
    candle = {"t": 1700000000, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "symbol": "XAUUSD"}
    snap = build_snapshot(state, candle, m1_df=_make_m1_df(25), digits=2)

    pool = AsyncMock()
    pool.execute = AsyncMock()

    import asyncio

    asyncio.run(insert_single_snapshot(pool, snap))

    args = pool.execute.call_args[0]
    query = args[0]
    assert "candle_color_d1" in query
    assert "bb_m1" in query
    assert "$32" in query


def test_batch_insert_snapshot_query_contains_same_new_columns():
    state = _make_state()
    candle = {"t": 1700000000, "o": 100.0, "h": 100.2, "l": 99.8, "c": 100.1, "symbol": "XAUUSD"}
    snap = build_snapshot(state, candle, m1_df=_make_m1_df(25), digits=2)

    stmt = AsyncMock()
    stmt.fetch = AsyncMock()

    conn = AsyncMock()
    conn.prepare = AsyncMock(return_value=stmt)
    pool = _DummyPool(conn)

    import asyncio

    asyncio.run(batch_insert_snapshots(pool, [snap]))

    query = conn.prepare.call_args[0][0]
    assert "candle_color_d1" in query
    assert "bb_m1" in query
    assert "$32" in query
