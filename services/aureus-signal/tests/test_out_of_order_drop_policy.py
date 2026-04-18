import asyncio
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import run_signal_engine
from engine.symbol_runtime import CandleWorkItem, PerSymbolWorkerRuntime


def test_run_signal_engine_does_not_duplicate_out_of_order_guard_in_main_loop():
    source = inspect.getsource(run_signal_engine)
    assert "ts_unix <= last_executed_t" not in source


@pytest.mark.asyncio
async def test_drop_and_ack_when_candle_is_out_of_order():
    processed = []
    acked = []

    async def handler(symbol: str, item: CandleWorkItem) -> None:
        processed.append((symbol, item.ts_unix))

    async def ack(item: CandleWorkItem) -> None:
        acked.append(item.entry_id)

    runtime = PerSymbolWorkerRuntime(worker_handler=handler)
    await runtime.start_symbol("XAUUSD")

    runtime.set_last_executed_candle_t("XAUUSD", 100)

    await runtime.enqueue(
        "XAUUSD",
        CandleWorkItem(
            entry_id="late-1",
            stream_key="aureus:stream:XAUUSD:candle",
            ts_unix=100,
            payload={"t": "100"},
            ack=ack,
        ),
    )

    await asyncio.wait_for(runtime.join_symbol("XAUUSD"), timeout=1)

    assert processed == []
    assert acked == ["late-1"]

    await runtime.stop_all()
