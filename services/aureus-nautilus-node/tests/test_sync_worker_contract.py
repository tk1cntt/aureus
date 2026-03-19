import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sync_worker import SyncWorker


def test_sync_worker_emits_versioned_execution_envelope():
    async def _case():
        redis_mock = AsyncMock()
        worker = SyncWorker(redis_client=redis_mock, schema_ver="2.0")

        event = SimpleNamespace(
            client_order_id=SimpleNamespace(value="trace-200"),
            instrument_id=SimpleNamespace(value="XAUUSD.SIM"),
            ts_event=1710000000,
        )

        await worker._handle_order_event(event)

        stream = redis_mock.xadd.await_args.args[0]
        data = redis_mock.xadd.await_args.args[1]
        envelope = json.loads(data["data"])

        assert stream == "aureus:stream:XAUUSD:execution"
        assert data["type"] == "EXECUTION_REPORT"
        assert envelope["schema_ver"] == "2.0"
        assert envelope["event_type"] == "ORDER_EVENT"
        assert envelope["trace_id"] == "trace-200"
        assert envelope["event_id"]

    asyncio.run(_case())


def test_sync_worker_routes_bad_event_to_dlq():
    async def _case():
        redis_mock = AsyncMock()
        worker = SyncWorker(redis_client=redis_mock)

        class NonSerializable:
            pass

        bad_event = SimpleNamespace(
            client_order_id=SimpleNamespace(value="trace-bad"),
            instrument_id=SimpleNamespace(value="XAUUSD.SIM"),
            ts_event=NonSerializable(),
        )

        await worker._handle_order_event(bad_event)

        stream = redis_mock.xadd.await_args.args[0]
        data = redis_mock.xadd.await_args.args[1]
        dlq = json.loads(data["data"])

        assert stream == "aureus:stream:sync:dlq"
        assert data["type"] == "SYNC_EVENT_DLQ"
        assert dlq["reason"] == "ORDER_MAPPING_FAILED"
        assert dlq["event_type"] == "order"

    asyncio.run(_case())
