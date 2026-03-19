import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sync_worker import SyncWorker


def test_sync_worker_pushes_order_event():
    async def _case():
        redis_mock = AsyncMock()
        worker = SyncWorker(redis_client=redis_mock)

        fake_event = SimpleNamespace(
            client_order_id=SimpleNamespace(value="trace-1"),
            instrument_id=SimpleNamespace(value="XAUUSD.SIM"),
            ts_event=12345,
        )

        await worker._handle_order_event(fake_event)

        assert redis_mock.xadd.await_count == 1
        stream = redis_mock.xadd.await_args.args[0]
        payload = redis_mock.xadd.await_args.args[1]
        body = json.loads(payload["data"])

        assert stream == "aureus:stream:XAUUSD:execution"
        assert payload["type"] == "EXECUTION_REPORT"
        assert body["schema_ver"] == "1.0"
        assert body["trace_id"] == "trace-1"

    asyncio.run(_case())
