import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import run_signal_engine


class _FakeRow(dict):
    def __getattr__(self, item):
        return self[item]


class _FakeDBPool:
    def __init__(self):
        base = datetime.fromtimestamp(1701000000, tz=timezone.utc)
        self._warmup_rows = []
        for i in range(30):
            candle_time = base + timedelta(minutes=i)
            open_px = 2048.0 + (i * 0.4)
            self._warmup_rows.append(
                _FakeRow(
                    time=candle_time,
                    open=open_px,
                    high=open_px + 1.8,
                    low=open_px - 1.6,
                    close=open_px + 0.9,
                    volume=300 + i,
                )
            )

        # Force a deterministic bullish FVG on warmup evaluation window (c3.low > c1.high).
        self._warmup_rows[-3].update(open=2064.0, high=2065.0, low=2063.1, close=2064.6)
        self._warmup_rows[-2].update(open=2064.8, high=2065.4, low=2063.8, close=2064.2)
        self._warmup_rows[-1].update(open=2068.2, high=2069.1, low=2066.3, close=2068.7)

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
                                "t": "1701001800",
                                "type": "CANDLE",
                                "symbol": "XAUUSD",
                                "o": "2070.1",
                                "h": "2072.2",
                                "l": "2070.0",
                                "c": "2071.4",
                                "v": "330",
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


class TestFVGEnginePathIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_run_signal_engine_emits_fvg_tag_in_runtime_loop(self):
        fake_db = _FakeDBPool()
        fake_redis = _FakeRedis()

        with (
            patch.dict(
                os.environ,
                {
                    "SYMBOLS": "XAUUSD",
                    "EXECUTION_MODE": "simulated",
                    "AUREUS_ENABLE_FVG_SIGNAL": "1",
                },
                clear=False,
            ),
            patch("engine.live_engine.seed_system_strategies", new=lambda *_a, **_k: asyncio.sleep(0)),
            patch("engine.live_engine.StrategyRegistry", _FakeStrategyRegistry),
            patch("engine.live_engine.SimulatedTradeManager", _FakeTradeManager),
            patch("engine.live_engine.AIValidator"),
            patch("engine.live_engine.NewsProvider.fetch_this_week", return_value=None),
            patch("engine.live_engine.NewsProvider.get_todays_events", return_value=[]),
            patch("engine.live_engine.integrity_and_recalc_task", new=lambda *_a, **_k: asyncio.sleep(0)),
            patch("engine.live_engine.evaluate_closed_candle_gate", return_value=(True, "")),
            patch("engine.live_engine.evaluate_backfill_readiness_gate", return_value=(True, "")),
            patch("engine.live_engine.evaluate_window_integrity_gate", return_value=(True, "")),
            patch("engine.live_engine.asyncio.create_task", side_effect=_swallow_task),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await run_signal_engine(db_pool=fake_db, redis_client=fake_redis)

        state_payload = fake_redis.state_payload
        self.assertIsNotNone(state_payload, "Expected engine to persist state to Redis")
        self.assertIsInstance(state_payload, str)

        state_payload_str = cast(str, state_payload)
        state = json.loads(state_payload_str)
        tags = [item.get("tag") for item in state.get("signal_history", [])]
        self.assertIn("fvg_up", tags)


if __name__ == "__main__":
    unittest.main()
