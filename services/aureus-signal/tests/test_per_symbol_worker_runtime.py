import asyncio
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import run_signal_engine
from engine.symbol_runtime import CandleWorkItem, PerSymbolWorkerRuntime


def test_run_signal_engine_wires_worker_runtime_enqueue_path():
    source = inspect.getsource(run_signal_engine)
    assert "PerSymbolWorkerRuntime(" in source
    assert ".enqueue(" in source


@pytest.mark.asyncio
async def test_per_symbol_workers_run_without_cross_symbol_blocking():
    processed = []
    gate = asyncio.Event()

    async def handler(symbol: str, item: CandleWorkItem) -> None:
        if symbol == "XAUUSD" and item.ts_unix == 1:
            await gate.wait()
        processed.append((symbol, item.ts_unix))

    runtime = PerSymbolWorkerRuntime(worker_handler=handler)

    await runtime.start_symbol("XAUUSD")
    await runtime.start_symbol("EURUSD")

    await runtime.enqueue("XAUUSD", CandleWorkItem(entry_id="x1", stream_key="sx", ts_unix=1, payload={}))
    await runtime.enqueue("EURUSD", CandleWorkItem(entry_id="e1", stream_key="se", ts_unix=1, payload={}))

    await asyncio.sleep(0.05)
    assert ("EURUSD", 1) in processed
    assert ("XAUUSD", 1) not in processed

    gate.set()
    await runtime.enqueue("XAUUSD", CandleWorkItem(entry_id="x2", stream_key="sx", ts_unix=2, payload={}))

    await asyncio.wait_for(runtime.join_symbol("XAUUSD"), timeout=1)
    await asyncio.wait_for(runtime.join_symbol("EURUSD"), timeout=1)

    xau_seq = [t for s, t in processed if s == "XAUUSD"]
    eur_seq = [t for s, t in processed if s == "EURUSD"]

    assert xau_seq == [1, 2]
    assert eur_seq == [1]

    await runtime.stop_all()


@pytest.mark.asyncio
async def test_per_symbol_queue_keeps_fifo_order():
    processed = []

    async def handler(symbol: str, item: CandleWorkItem) -> None:
        processed.append((symbol, item.ts_unix))

    runtime = PerSymbolWorkerRuntime(worker_handler=handler)
    await runtime.start_symbol("XAUUSD")

    await runtime.enqueue("XAUUSD", CandleWorkItem(entry_id="x1", stream_key="sx", ts_unix=10, payload={}))
    await runtime.enqueue("XAUUSD", CandleWorkItem(entry_id="x2", stream_key="sx", ts_unix=20, payload={}))
    await runtime.enqueue("XAUUSD", CandleWorkItem(entry_id="x3", stream_key="sx", ts_unix=30, payload={}))

    await asyncio.wait_for(runtime.join_symbol("XAUUSD"), timeout=1)

    assert processed == [
        ("XAUUSD", 10),
        ("XAUUSD", 20),
        ("XAUUSD", 30),
    ]

    await runtime.stop_all()
