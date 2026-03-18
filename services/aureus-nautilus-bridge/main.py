import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Set

import redis.asyncio as redis

from mapper import map_order_intent, parse_order_data
from reconciliation import is_terminal_status, normalize_execution_report


logger = logging.getLogger("aureus-nautilus-bridge.main")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


REDIS_HOST = os.getenv("REDIS_HOST", "aureus-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CONSUMER_GROUP = os.getenv("BRIDGE_CONSUMER_GROUP", "aureus-nautilus-bridge")
CONSUMER_NAME = f"bridge-{os.getenv('HOSTNAME', 'local')}"
ORDER_EVENT_TYPES = {"ORDER_OPEN"}

NAUTILUS_ADAPTER_MODE = os.getenv("NAUTILUS_ADAPTER_MODE", "simulated").strip().lower()
NAUTILUS_LIFECYCLE_STREAM_PATTERN = os.getenv(
    "NAUTILUS_LIFECYCLE_STREAM_PATTERN",
    "aureus:stream:*:nautilus_execution",
)
NAUTILUS_LIFECYCLE_EVENT_TYPES = {
    "NAUTILUS_EXECUTION_REPORT",
    "EXECUTION_REPORT",
    "ORDER_LIFECYCLE",
    "EXECUTION_EVENT",
}


def _stream_name(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _is_order_stream(stream_name: str) -> bool:
    return stream_name.endswith(":orders")


def _parse_report_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_data = payload.get("data") if isinstance(payload, dict) else None
    if raw_data is None:
        raw_data = payload
    return parse_order_data(raw_data)


class NautilusAdapter:
    """Minimal adapter abstraction for simulated mode."""

    async def submit_order(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "ORDER_ACCEPTED",
            "event_time": intent["event_time"],
            "quantity": intent.get("quantity", 1.0),
            "fill_price": intent.get("entry_price", 0.0),
            "adapter_order_id": f"nautilus:{intent['trace_id']}",
        }


class BridgeProcessor:
    def __init__(self, adapter: Optional[NautilusAdapter] = None):
        self.adapter = adapter or NautilusAdapter()
        self.status_by_trace: Dict[str, str] = {}

    async def process_order_event(self, event_type: str, order_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event_type not in ORDER_EVENT_TYPES:
            return None

        intent = map_order_intent(order_payload)
        adapter_report = await self.adapter.submit_order(intent)
        return normalize_execution_report(intent, adapter_report, self.status_by_trace)

    async def process_lifecycle_report(self, order_payload: Dict[str, Any], adapter_report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        intent = map_order_intent(order_payload)
        return normalize_execution_report(intent, adapter_report, self.status_by_trace)


class AureusNautilusBridge:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.running = True
        self.processor = BridgeProcessor()
        self.known_streams: Set[str] = set()
        self.pending_intents: Dict[str, Dict[str, Any]] = {}
        self.adapter_mode = NAUTILUS_ADAPTER_MODE

    def _redis_client(self) -> redis.Redis:
        if self.redis is None:
            raise RuntimeError("Redis client is not connected")
        return self.redis

    async def connect_redis(self):
        while self.running:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                await self.redis.ping()
                logger.info(
                    "Connected to Redis at %s:%s (adapter_mode=%s)",
                    REDIS_HOST,
                    REDIS_PORT,
                    self.adapter_mode,
                )
                return
            except Exception as exc:
                logger.error("Waiting for Redis: %s", exc)
                await asyncio.sleep(2)

    async def ensure_consumer_group(self, stream_key: str):
        client = self._redis_client()
        try:
            await client.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
            logger.info("Created group %s for %s", CONSUMER_GROUP, stream_key)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                logger.error("Group creation error for %s: %s", stream_key, exc)

    async def discover_streams(self):
        client = self._redis_client()
        found_streams: Set[str] = set()

        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="aureus:stream:*:orders", count=100)
            found_streams.update(_stream_name(k) for k in keys)
            if cursor == 0:
                break

        if self.adapter_mode == "stream":
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor,
                    match=NAUTILUS_LIFECYCLE_STREAM_PATTERN,
                    count=100,
                )
                found_streams.update(_stream_name(k) for k in keys)
                if cursor == 0:
                    break

        new_streams = found_streams - self.known_streams
        for stream in new_streams:
            await self.ensure_consumer_group(stream)
        self.known_streams.update(new_streams)

    async def _publish_execution_event(self, event: Dict[str, Any]):
        client = self._redis_client()
        execution_stream = f"aureus:stream:{event['symbol']}:execution"
        await client.xadd(
            execution_stream,
            {
                "type": "EXECUTION_EVENT",
                "data": json.dumps(event),
            },
        )
        logger.info("Published execution event for %s -> %s", event["trace_id"], execution_stream)

    async def _handle_order_message(self, msg_id: str, payload: Dict[str, Any]):
        event_type = payload.get("type", "")
        if event_type not in ORDER_EVENT_TYPES:
            return

        order_payload = parse_order_data(payload.get("data"))
        intent = map_order_intent(order_payload)
        trace_id = intent["trace_id"]
        self.pending_intents[trace_id] = dict(order_payload)

        if self.adapter_mode != "stream":
            event = await self.processor.process_order_event(event_type, order_payload)
            if event is not None:
                await self._publish_execution_event(event)
                if is_terminal_status(event.get("status")):
                    self.pending_intents.pop(trace_id, None)
            return

        logger.info("Registered order intent for stream-mode lifecycle ingestion: %s", trace_id)

    async def _handle_lifecycle_message(self, msg_id: str, payload: Dict[str, Any]):
        event_type = payload.get("type", "")
        if event_type and event_type not in NAUTILUS_LIFECYCLE_EVENT_TYPES:
            return

        report = _parse_report_data(payload)
        trace_value = report.get("trace_id")
        symbol_value = report.get("symbol")
        if not isinstance(trace_value, str) or not trace_value:
            raise ValueError("Lifecycle report requires non-empty trace_id")
        if not isinstance(symbol_value, str) or not symbol_value:
            raise ValueError("Lifecycle report requires non-empty symbol")

        trace_id = trace_value
        symbol = symbol_value

        order_payload = self.pending_intents.get(trace_id)
        if not order_payload:
            order_payload = {
                "trace_id": trace_id,
                "symbol": symbol,
                "event_time": report.get("event_time"),
                "side": report.get("side", "BUY"),
                "type": report.get("type", "MARKET"),
                "quantity": report.get("quantity", 1.0),
                "entry_price": report.get("entry_price", report.get("fill_price", 0.0)),
                "sl": report.get("sl"),
                "tp": report.get("tp"),
                "execution_mode": "nautilus",
            }

        event = await self.processor.process_lifecycle_report(order_payload, report)
        if event is None:
            return

        await self._publish_execution_event(event)
        self.pending_intents[trace_id] = dict(order_payload)
        if is_terminal_status(event.get("status")):
            self.pending_intents.pop(trace_id, None)

    async def handle_message(self, stream_name: str, msg_id: str, payload: Dict[str, Any]):
        client = self._redis_client()
        stream_name = _stream_name(stream_name)
        try:
            if _is_order_stream(stream_name):
                await self._handle_order_message(msg_id, payload)
            elif self.adapter_mode == "stream":
                await self._handle_lifecycle_message(msg_id, payload)
            await client.xack(stream_name, CONSUMER_GROUP, msg_id)
        except Exception as exc:
            logger.error("Failed processing %s/%s: %s", stream_name, msg_id, exc)
            await client.xack(stream_name, CONSUMER_GROUP, msg_id)

    async def run(self):
        await self.connect_redis()
        logger.info("Aureus Nautilus bridge worker started")

        while self.running:
            await self.discover_streams()
            if not self.known_streams:
                await asyncio.sleep(1)
                continue

            streams_dict = {stream: ">" for stream in self.known_streams}
            try:
                client = self._redis_client()
                response = await client.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams=streams_dict,
                    count=100,
                    block=1000,
                )
                if not response:
                    continue

                for stream_name, messages in response:
                    for msg_id, payload in messages:
                        await self.handle_message(stream_name, msg_id, payload)
            except Exception as exc:
                logger.error("Bridge read loop error: %s", exc)
                await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(AureusNautilusBridge().run())
    except KeyboardInterrupt:
        pass
