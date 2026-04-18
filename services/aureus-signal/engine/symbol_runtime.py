import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional


@dataclass
class CandleWorkItem:
    entry_id: str
    stream_key: str
    ts_unix: int
    payload: Dict[str, Any]
    ack: Optional[Callable[["CandleWorkItem"], Awaitable[None]]] = None


class PerSymbolWorkerRuntime:
    def __init__(self, worker_handler: Callable[[str, CandleWorkItem], Awaitable[None]]) -> None:
        self._worker_handler = worker_handler
        self._queues: Dict[str, asyncio.Queue[CandleWorkItem]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._last_executed_candle_t: Dict[str, int] = {}

    async def start_symbol(self, symbol: str) -> None:
        if symbol in self._tasks:
            return
        queue: asyncio.Queue[CandleWorkItem] = asyncio.Queue()
        self._queues[symbol] = queue
        self._tasks[symbol] = asyncio.create_task(self._worker_loop(symbol))

    async def enqueue(self, symbol: str, item: CandleWorkItem) -> None:
        if symbol not in self._queues:
            await self.start_symbol(symbol)
        await self._queues[symbol].put(item)

    def set_last_executed_candle_t(self, symbol: str, ts_unix: int) -> None:
        self._last_executed_candle_t[symbol] = int(ts_unix)

    async def join_symbol(self, symbol: str) -> None:
        queue = self._queues.get(symbol)
        if queue is None:
            return
        await queue.join()

    async def stop_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        for task in self._tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _worker_loop(self, symbol: str) -> None:
        queue = self._queues[symbol]
        while True:
            item = await queue.get()
            try:
                last_executed = int(self._last_executed_candle_t.get(symbol, 0) or 0)
                if item.ts_unix <= last_executed:
                    if item.ack:
                        await item.ack(item)
                    continue

                await self._worker_handler(symbol, item)
                self._last_executed_candle_t[symbol] = int(item.ts_unix)
            finally:
                queue.task_done()
