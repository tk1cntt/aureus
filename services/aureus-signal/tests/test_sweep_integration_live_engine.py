import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.live_engine import run_signal_engine
from engine.signals.base import BaseSignal
from engine.signals.sweep import SweepSignal
from engine.signals.sweep_bear import SweepBearSignal
from engine.signals.sweep_bull import SweepBullSignal


class _SeedSweepTargetsSignal(BaseSignal):
    def __init__(self):
        super().__init__("Seed Sweep Targets")

    def calculate(self, df, state_obj, **kwargs):
        if not getattr(state_obj, "obs", None):
            # SẾP ƠI: Nếu dùng sweep_targets, state.obs sẽ rỗng, vòng lặp 'for ob in obs' ở file sweep sẽ Skip.
            # Do đó sweep_bull sẽ không bao giờ được trigger. Bắt buộc phải dùng obs:
            state_obj.obs = [
                {
                    "ob_type": "BULLISH",
                    "bottom": 1999.0,
                    "top": 1999.5,
                    "t_start": int(df.iloc[-1]["t"]),
                    "status": "PENDING"
                }
            ]
        return None


class _FakeRow(dict):
    def __getattr__(self, item):
        return self[item]


class _FakeDBPool:
    def __init__(self):
        base = datetime.fromtimestamp(1707000000, tz=timezone.utc)
        self._warmup_rows = []
        for i in range(6):
            candle_time = base + timedelta(minutes=i)
            open_px = 2001.0 + (i * 0.2)
            self._warmup_rows.append(
                _FakeRow(
                    time=candle_time,
                    open=open_px,
                    high=open_px + 1.0,
                    low=open_px - 1.0,
                    close=open_px + 0.3,
                    volume=350 + i,
                )
            )

        # Force last candle to sweep below seeded price 1999.0.
        self._warmup_rows[-1].update(open=2000.2, high=2001.1, low=1998.4, close=2000.0)

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

    async def get(self, key):
        return None

    async def xgroup_create(self, *_args, **_kwargs):
        return None

    async def xreadgroup(self, _group, _consumer, streams, **_kwargs):
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


def _build_runtime_sweep_signal_set(_symbol, _cfg):
    return {
        "seed_sweep_targets": _SeedSweepTargetsSignal(),
        "sweep_processor": SweepSignal(),
        "sweep_bull": SweepBullSignal(),
        "sweep_bear": SweepBearSignal(),
    }


class TestSweepEnginePathIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_run_signal_engine_emits_sweep_tag_in_runtime_path(self):
        fake_db = _FakeDBPool()
        fake_redis = _FakeRedis()

        with (
            patch.dict(os.environ, {"SYMBOLS": "XAUUSD", "EXECUTION_MODE": "simulated"}, clear=False),
            patch("engine.live_engine.seed_system_strategies", new=lambda *_a, **_k: asyncio.sleep(0)),
            patch("engine.live_engine.create_signal_set", side_effect=_build_runtime_sweep_signal_set),
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
        tags = [item.get("tag") for item in state.get("signal_history", [])]
        self.assertIn("sweep_bull", tags)


if __name__ == "__main__":
    unittest.main()
