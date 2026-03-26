import asyncio
import json
import logging
import uuid
from typing import Any

try:
    from nautilus_trader.core.message import Event
    from nautilus_trader.model.events import OrderEvent, PositionEvent
except ModuleNotFoundError:  # pragma: no cover - optional dependency in tests
    Event = Any
    OrderEvent = Any
    PositionEvent = Any


class SyncWorker:
    def __init__(self, redis_client, schema_ver: str = "1.0", dlq_stream: str = "aureus:stream:sync:dlq"):
        self.redis_client = redis_client
        self._running = False
        self._queue = asyncio.Queue()
        self.log = logging.getLogger(self.__class__.__name__)
        self.schema_ver = schema_ver
        self.dlq_stream = dlq_stream

    def start(self):
        self._running = True
        self.log.info("[SYNC_WORKER][START] Started queue processing loop dlq_stream=%s", self.dlq_stream)
        asyncio.create_task(self._process_loop())

    def stop(self):
        self._running = False
        self.log.info("[SYNC_WORKER][STOP] Stop requested queue_size=%d", self._queue.qsize())

    def on_order_event(self, event: OrderEvent):
        self._queue.put_nowait(("order", event))
        self.log.debug("[SYNC_WORKER][ENQUEUE] type=order queue_size=%d", self._queue.qsize())

    def on_position_event(self, event: PositionEvent):
        self._queue.put_nowait(("position", event))
        self.log.debug("[SYNC_WORKER][ENQUEUE] type=position queue_size=%d", self._queue.qsize())

    async def _process_loop(self):
        self.log.info("[SYNC_WORKER][LOOP] Entered process loop")
        while self._running:
            await self._process_queue_once()
            await asyncio.sleep(0.01)
        self.log.info("[SYNC_WORKER][LOOP] Exited process loop")

    async def _process_queue_once(self):
        while not self._queue.empty():
            evt_type, event = self._queue.get_nowait()
            self.log.info(
                "[SYNC_WORKER][PROCESS] Dequeued event type=%s source_event=%s queue_remaining=%d",
                evt_type,
                event.__class__.__name__ if event is not None else "unknown",
                self._queue.qsize(),
            )
            try:
                if evt_type == "order":
                    await self._handle_order_event(event)
                elif evt_type == "position":
                    await self._handle_position_event(event)
                else:
                    await self._emit_dlq("UNKNOWN_EVENT_TYPE", evt_type, event, "unsupported event type")
            except Exception as exc:
                await self._emit_dlq("PROCESSING_ERROR", evt_type, event, str(exc))

    @staticmethod
    def _unwrap_value(value: Any, default: str = "unknown") -> str:
        if value is None:
            return default
        inner = getattr(value, "value", value)
        return str(inner)

    def _extract_symbol(self, event: Any) -> str:
        instrument = getattr(event, "instrument_id", "UNKNOWN")
        value = self._unwrap_value(instrument, "UNKNOWN")
        return value.split(".")[0].upper()

    def _build_envelope(self, event_type: str, trace_id: str, ts_event: Any, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_ver": self.schema_ver,
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "trace_id": trace_id,
            "ts_event": ts_event,
            "payload": payload,
        }

    async def _handle_order_event(self, event):
        try:
            trace_raw = getattr(event, "client_order_id", getattr(event, "order_id", "unknown"))
            trace_id = self._unwrap_value(trace_raw)
            symbol = self._extract_symbol(event)
            ts_event = getattr(event, "ts_event", 0)
            payload = {
                "status": event.__class__.__name__.upper(),
                "nautilus_event": True,
                "symbol": symbol,
            }
            envelope = self._build_envelope("ORDER_EVENT", trace_id, ts_event, payload)
            stream_key = f"aureus:stream:{symbol}:execution"
            await self.redis_client.xadd(
                stream_key,
                {"type": "EXECUTION_REPORT", "data": json.dumps(envelope)},
            )
            self.log.info(
                "[SYNC_WORKER][ORDER_PUBLISH] stream=%s trace_id=%s status=%s",
                stream_key,
                trace_id,
                payload["status"],
            )
        except Exception as exc:
            await self._emit_dlq("ORDER_MAPPING_FAILED", "order", event, str(exc))

    async def _handle_position_event(self, event):
        try:
            symbol = self._extract_symbol(event)
            trace_id = self._unwrap_value(getattr(event, "position_id", "unknown"))
            ts_event = getattr(event, "ts_event", 0)
            payload = {
                "position_id": trace_id,
                "symbol": symbol,
                "unrealized_pnl": float(getattr(event, "unrealized_pnl", 0.0)),
                "realized_pnl": float(getattr(event, "realized_pnl", 0.0)),
            }
            envelope = self._build_envelope("POSITION_EVENT", trace_id, ts_event, payload)
            stream_key = f"aureus:stream:{symbol}:positions"
            await self.redis_client.xadd(
                stream_key,
                {"type": "POSITION_REPORT", "data": json.dumps(envelope)},
            )
            self.log.info(
                "[SYNC_WORKER][POSITION_PUBLISH] stream=%s trace_id=%s unrealized_pnl=%s realized_pnl=%s",
                stream_key,
                trace_id,
                payload["unrealized_pnl"],
                payload["realized_pnl"],
            )
        except Exception as exc:
            await self._emit_dlq("POSITION_MAPPING_FAILED", "position", event, str(exc))

    async def _emit_dlq(self, reason: str, event_type: str, event: Any, error: str) -> None:
        diagnostics = {
            "schema_ver": self.schema_ver,
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "reason": reason,
            "error": error,
            "source_event": event.__class__.__name__ if event is not None else "unknown",
        }
        await self.redis_client.xadd(self.dlq_stream, {"type": "SYNC_EVENT_DLQ", "data": json.dumps(diagnostics)})
        self.log.error(
            "[SYNC_WORKER][DLQ] stream=%s reason=%s event_type=%s source_event=%s error=%s",
            self.dlq_stream,
            reason,
            event_type,
            diagnostics["source_event"],
            error,
        )
