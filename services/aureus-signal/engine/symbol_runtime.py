import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from common.circuit_breaker import CircuitBreaker, CircuitBreakerState


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


class SymbolRuntimeHealthManager:
    LAG_P95_THRESHOLD_MS = 2000.0
    QUEUE_DEPTH_THRESHOLD = 200
    ERROR_RATE_THRESHOLD = 0.05

    BREACH_CONSECUTIVE_MINUTES = 3
    RECOVERY_CONSECUTIVE_MINUTES = 5
    RECOVERY_FACTOR = 0.5

    def __init__(
        self,
        lag_p95_threshold_ms: float = LAG_P95_THRESHOLD_MS,
        queue_depth_threshold: int = QUEUE_DEPTH_THRESHOLD,
        error_rate_threshold: float = ERROR_RATE_THRESHOLD,
    ) -> None:
        self._lag_p95_threshold_ms = float(lag_p95_threshold_ms)
        self._queue_depth_threshold = int(queue_depth_threshold)
        self._error_rate_threshold = float(error_rate_threshold)
        self._states: Dict[str, Dict[str, Any]] = {}

    def _get_state(self, symbol: str) -> Dict[str, Any]:
        state = self._states.get(symbol)
        if state is not None:
            return state

        state = {
            "mode": "full",
            "lag_p95_ms": 0.0,
            "queue_depth": 0,
            "error_rate": 0.0,
            "consecutive_breach_minutes": 0,
            "consecutive_healthy_minutes": 0,
            "last_transition_reason": None,
            "breaker": CircuitBreaker(error_threshold=5, timeout_seconds=60),
        }
        self._states[symbol] = state
        return state

    def record_symbol_failure(self, symbol: str) -> None:
        state = self._get_state(symbol)
        breaker = state["breaker"]
        breaker.record_failure()

    def record_symbol_success(self, symbol: str) -> None:
        state = self._get_state(symbol)
        breaker = state["breaker"]
        breaker.record_success()

    def _slo_breach_reason(self, lag_p95_ms: float, queue_depth: int, error_rate: float) -> Optional[str]:
        if lag_p95_ms > self._lag_p95_threshold_ms:
            return "lag_p95_ms"
        if queue_depth > self._queue_depth_threshold:
            return "queue_depth"
        if error_rate > self._error_rate_threshold:
            return "error_rate"
        return None

    def _is_healthy_for_recovery(self, lag_p95_ms: float, queue_depth: int, error_rate: float) -> bool:
        return (
            lag_p95_ms <= (self._lag_p95_threshold_ms * self.RECOVERY_FACTOR)
            and queue_depth <= int(self._queue_depth_threshold * self.RECOVERY_FACTOR)
            and error_rate <= (self._error_rate_threshold * self.RECOVERY_FACTOR)
        )

    def update_symbol_metrics(
        self,
        symbol: str,
        lag_p95_ms: float,
        queue_depth: int,
        error_rate: float,
    ) -> Optional[str]:
        state = self._get_state(symbol)
        state["lag_p95_ms"] = float(lag_p95_ms)
        state["queue_depth"] = int(queue_depth)
        state["error_rate"] = float(error_rate)

        breach_reason = self._slo_breach_reason(
            lag_p95_ms=float(lag_p95_ms),
            queue_depth=int(queue_depth),
            error_rate=float(error_rate),
        )
        if breach_reason:
            state["consecutive_breach_minutes"] += 1
            state["consecutive_healthy_minutes"] = 0
            state["last_transition_reason"] = breach_reason

            if state["consecutive_breach_minutes"] >= self.BREACH_CONSECUTIVE_MINUTES:
                state["mode"] = "fallback_serial"
                return "SLO_BREACH_FALLBACK_SERIAL"

            if state["queue_depth"] > self._queue_depth_threshold:
                return "BACKLOG_THRESHOLD_BREACH"
            return None

        state["consecutive_breach_minutes"] = 0
        if state["mode"] == "fallback_serial":
            if self._is_healthy_for_recovery(
                lag_p95_ms=float(lag_p95_ms),
                queue_depth=int(queue_depth),
                error_rate=float(error_rate),
            ):
                state["consecutive_healthy_minutes"] += 1
                if state["consecutive_healthy_minutes"] >= self.RECOVERY_CONSECUTIVE_MINUTES:
                    state["mode"] = "full"
                    return "SLO_RECOVERED_PARALLEL"
            else:
                state["consecutive_healthy_minutes"] = 0
        else:
            state["consecutive_healthy_minutes"] = 0

        return None

    def set_symbol_mode(self, symbol: str, mode: str) -> None:
        if mode not in {"shadow", "canary", "full", "fallback_serial"}:
            raise ValueError(f"Unsupported symbol mode: {mode}")
        state = self._get_state(symbol)
        state["mode"] = mode

    def get_symbol_mode(self, symbol: str) -> str:
        return str(self._get_state(symbol)["mode"])

    def get_symbol_status(self, symbol: str) -> Dict[str, Any]:
        state = self._get_state(symbol)
        breaker = state["breaker"]
        breaker_open = breaker.state == CircuitBreakerState.OPEN
        allow_parallel = (not breaker_open) and state["mode"] != "fallback_serial"

        return {
            "symbol": symbol,
            "mode": state["mode"],
            "lag_p95_ms": state["lag_p95_ms"],
            "queue_depth": state["queue_depth"],
            "error_rate": state["error_rate"],
            "consecutive_breach_minutes": state["consecutive_breach_minutes"],
            "consecutive_healthy_minutes": state["consecutive_healthy_minutes"],
            "last_transition_reason": state["last_transition_reason"],
            "breaker_open": breaker_open,
            "allow_parallel": allow_parallel,
        }
