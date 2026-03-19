from __future__ import annotations

import asyncio

from main import run_live_node


class DummyNode:
    def __init__(self, config):
        self.config = config
        self.stopped = False

    async def stop(self):
        self.stopped = True


def test_live_node_bootstrap_uses_live_trading_node_and_exposes_health_state():
    async def _case():
        stop_event = asyncio.Event()

        async def _trigger_stop():
            await asyncio.sleep(0.02)
            stop_event.set()

        asyncio.create_task(_trigger_stop())
        state = await run_live_node(node_factory=lambda cfg: DummyNode(cfg), stop_event=stop_event, warmup_seconds=0.01)

        assert state.phase == "STOPPED"
        assert state.healthy is False
        assert state.last_error == ""

    asyncio.run(_case())


def test_live_node_bootstrap_records_failure_state():
    async def _case():
        state = await run_live_node(node_factory=lambda _cfg: (_ for _ in ()).throw(RuntimeError("boom")), warmup_seconds=0.0)
        assert state.phase == "FAILED"
        assert state.healthy is False
        assert "boom" in state.last_error

    asyncio.run(_case())
