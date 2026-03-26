from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from typing import Any, Callable, Optional

from config import get_node_config

try:
    from nautilus_trader.live.node import LiveTradingNode
except Exception:  # pragma: no cover
    LiveTradingNode = None

try:
    from nautilus_trader.live.node import TradingNode
except Exception:  # pragma: no cover
    TradingNode = None


log = logging.getLogger("aureus.nautilus.node.main")


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root_logger.setLevel(level)

    log.setLevel(level)


@dataclass
class RuntimeHealth:
    phase: str = "BOOTSTRAP"
    healthy: bool = False
    last_error: str = ""


def _default_node_factory(config: Any) -> Any:
    node_cls = LiveTradingNode or TradingNode
    if node_cls is None:  # pragma: no cover
        raise RuntimeError("No Nautilus node class available")
    return node_cls(config=config)


async def run_live_node(
    node_factory: Optional[Callable[[Any], Any]] = None,
    stop_event: Optional[asyncio.Event] = None,
    warmup_seconds: float = 0.05,
) -> RuntimeHealth:
    lifecycle = RuntimeHealth()
    stopper = stop_event or asyncio.Event()
    factory = node_factory or _default_node_factory

    try:
        lifecycle.phase = "BOOTSTRAP"
        log.info("[NAUTILUS_NODE][BOOTSTRAP] Loading node config")
        config = get_node_config()
        node = factory(config)
        log.info(
            "[NAUTILUS_NODE][BOOTSTRAP] Node created node_class=%s factory=%s warmup_seconds=%.3f",
            node.__class__.__name__,
            getattr(factory, "__name__", factory.__class__.__name__),
            warmup_seconds,
        )
        log.warning(
            "[NAUTILUS_NODE][BOOTSTRAP] Auxiliary execution pipeline wiring is not initialized in main runtime "
            "(AureusExecutionClient/SyncWorker not started here)",
        )

        lifecycle.phase = "WARMUP"
        log.info("[NAUTILUS_NODE][WARMUP] Starting warmup")
        await asyncio.sleep(max(0.0, warmup_seconds))

        lifecycle.phase = "LIVE"
        lifecycle.healthy = True
        log.info("[NAUTILUS_NODE][LIVE] Node ready and waiting for stop_event")
        await stopper.wait()

        lifecycle.phase = "SHUTDOWN"
        lifecycle.healthy = False
        log.info("[NAUTILUS_NODE][SHUTDOWN] Stop signal received; stopping node")

        stop = getattr(node, "stop", None)
        if callable(stop):
            maybe_coro = stop()
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro

        lifecycle.phase = "STOPPED"
        log.info("[NAUTILUS_NODE][STOPPED] Node shutdown complete")
        return lifecycle
    except Exception as exc:
        lifecycle.phase = "FAILED"
        lifecycle.healthy = False
        lifecycle.last_error = str(exc)
        log.exception("[NAUTILUS_NODE][FAILED] Runtime failure: %s", exc)
        return lifecycle


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    def _trigger_stop() -> None:
        log.info("[NAUTILUS_NODE][SIGNAL] Stop signal handler triggered")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _trigger_stop)
        except NotImplementedError:  # pragma: no cover
            signal.signal(sig, lambda *_: stop_event.set())


async def _main_async() -> RuntimeHealth:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop, stop_event)
    log.info("[NAUTILUS_NODE][BOOTSTRAP] Signal handlers installed")
    return await run_live_node(stop_event=stop_event)


def main() -> RuntimeHealth:
    _configure_logging()
    return asyncio.run(_main_async())


if __name__ == "__main__":
    main()
