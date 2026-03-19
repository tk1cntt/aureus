from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from execution_client import AureusExecutionClient



def _client() -> AureusExecutionClient:
    settings = SimpleNamespace(
        symbol_whitelist=["XAUUSD"],
        require_sl_tp=True,
        max_order_notional=10_000.0,
    )
    return AureusExecutionClient(redis_client=AsyncMock(), settings=settings)


def _order_payload(trace_id: str, qty: float = 1.0) -> dict[bytes, bytes]:
    return {
        b"type": b"ORDER_OPEN",
        b"data": (
            "{"
            f'"trace_id":"{trace_id}",'
            '"symbol":"XAUUSD",'
            '"side":"BUY",'
            f'"qty":{qty},'
            '"sl":1990.0,'
            '"tp":2020.0'
            "}"
        ).encode(),
    }


def test_load_orders_preserve_idempotency_and_oco_generation_shape():
    async def _case():
        client = _client()

        with patch.object(client, "generate_order") as mock_gen:
            for i in range(100):
                client._handle_message(_order_payload(f"bulk-{i}"))

            # replay duplicates from the first ten intents
            for i in range(10):
                client._handle_message(_order_payload(f"bulk-{i}"))

            assert client.metrics["accepted_total"] == 100
            assert client.metrics["rejected_total"] == 10
            assert client.metrics["duplicate_trace_id_total"] == 10
            assert mock_gen.call_count == 300

    asyncio.run(_case())


def test_load_rejects_oversized_notional_without_breaking_flow():
    async def _case():
        client = _client()

        with patch.object(client, "generate_order") as mock_gen:
            for i in range(20):
                client._handle_message(_order_payload(f"risk-{i}", qty=20_000.0))

            assert client.metrics["accepted_total"] == 0
            assert client.metrics["rejected_total"] == 20
            assert client.metrics["invalid_notional_total"] == 20
            assert mock_gen.call_count == 0

    asyncio.run(_case())
