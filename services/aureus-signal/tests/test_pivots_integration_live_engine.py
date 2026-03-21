import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import run_signal_engine


class _FakeRow(dict):
    def __getattr__(self, item):
        return self[item]


class _FakeDBPool:
    def __init__(self):
        base = datetime.fromtimestamp(1706000000, tz=timezone.utc)
        prices = [2000, 2002, 2005, 2003, 1998, 1995, 1999, 2004, 2001, 1996, 1992, 1997, 2003]
        self._warmup_rows = []
        for i, close_px in enumerate(prices):
            candle_time = base + timedelta(minutes=i)
            self._warmup_rows.append(
                _FakeRow(
                    time=candle_time,
                    open=close_px - 0.5,
                    high=close_px + 1.0,
                    low=close_px - 1.0,
                    close=close_px,
                    volume=400 + i,
                )
            )

    async def fetchrow(self, query, symbol):
        return None

    async def fetch(self, query, *args):
        if "ORDER BY time DESC" in query and "LIMIT 1500" in query:
            return self._warmup_rows
        if "ORDER BY time ASC" in query:
            return []
        return []

    async def executemany(self, query, payload):
        return None


class _FakePubSub:
    async def subscribe(self, *_args, **_kwargs):
        return None

    async def listen(self):
        while True:
            await asyncio.sleep(3600)
            if False:
                yield None


class _FakeRedis:
    def __init__(self):
        self.state_payload = None
        self._candle_read_done = False

    async def get(self, key):
        return None

    async def xgroup_create(self, *_args, **_kwargs):
        return None

    async def xreadgroup(self, _group, _consumer, streams, **_kwargs):
        if any(str(k).endswith(":candle") for k in streams.keys()):
            if self._candle_read_done:
                await asyncio.sleep(3600)
                return []
            self._candle_read_done = True
            return [
                (
                    "aureus:stream:XAUUSD:candle",
                    [
                        (
                            "1-0",
                            {
                                "t": "1706000780",
                                "type": "CANDLE",
                                "symbol": "XAUUSD",
                                "o": "2002.0",
                                "h": "2004.0",
                                "l": "2001.0",
                                "c": "2003.0",
                                "v": "500",
                                "tf": "M1",
                            },
                        )
                    ],
                )
            ]
        return []

    async def xack(self, *_args, **_kwargs):
        return None

    async def set(self, key, value):
        if key == "aureus:state:XAUUSD":
            self.state_payload = value
            raise asyncio.CancelledError()

    async def xadd(self, *_args, **_kwargs):
        return None

    def pubsub(self):
        return _FakePubSub()


class _FakeStrategyRegistry:
    async def load_from_db(self, *_args, **_kwargs):
        return None

    def evaluate_all(self, *_args, **_kwargs):
        return []

    def get_rejections(self, clear=True):
        return []


class _FakeTradeManager:
    def __init__(self, *_args, **_kwargs):
        self.last_tick_events = []

    async def update_orders(self, *_args, **_kwargs):
        return None

    async def process_triggers(self, *_args, **_kwargs):
        return None


def _swallow_task(coro):
    coro.close()

    class _DoneTask:
        def cancel(self):
            return None

        def done(self):
            return True

    return _DoneTask()


class TestPivotsEnginePathIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_run_signal_engine_emits_pivot_tag_in_runtime_loop(self):
        fake_db = _FakeDBPool()
        fake_redis = _FakeRedis()

        with (
            patch.dict(os.environ, {"SYMBOLS": "XAUUSD", "EXECUTION_MODE": "simulated"}, clear=False),
            patch("engine.live_engine.seed_system_strategies", new=lambda *_a, **_k: asyncio.sleep(0)),
            patch("engine.live_engine.StrategyRegistry", _FakeStrategyRegistry),
            patch("engine.live_engine.SimulatedTradeManager", _FakeTradeManager),
            patch("engine.live_engine.AIValidator"),
            patch("engine.live_engine.NewsProvider.fetch_this_week", return_value=None),
            patch("engine.live_engine.NewsProvider.get_todays_events", return_value=[]),
            patch("engine.live_engine.integrity_and_recalc_task", new=lambda *_a, **_k: asyncio.sleep(0)),
            patch("engine.live_engine.asyncio.create_task", side_effect=_swallow_task),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_signal_engine(db_pool=fake_db, redis_client=fake_redis)

        state_payload = fake_redis.state_payload
        self.assertIsNotNone(state_payload, "Expected engine to persist state to Redis")
        self.assertIsInstance(state_payload, str)

        state = json.loads(state_payload)
        pivot_tags = {"hh", "hl", "lh", "ll"}
        tags = [item.get("tag") for item in state.get("signal_history", [])]
        self.assertTrue(any(tag in pivot_tags for tag in tags))


if __name__ == "__main__":
    unittest.main()
