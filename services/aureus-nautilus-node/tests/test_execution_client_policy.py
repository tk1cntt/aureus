import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from execution_client import AureusExecutionClient


def _client():
    settings = SimpleNamespace(
        symbol_whitelist=["XAUUSD"],
        require_sl_tp=True,
        max_order_notional=10_000.0,
    )
    return AureusExecutionClient(redis_client=AsyncMock(), settings=settings)


def test_hybrid_policy_accepts_when_optional_metadata_missing_but_counts_trace_gaps():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"hyb-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
        }

        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            assert mock_gen.call_count == 3
            assert client.metrics["accepted_total"] == 1
            assert client.metrics["trace_completeness_failures_total"] == 3
            assert client.metrics["missing_backfill_status_total"] == 1
            assert client.metrics["missing_entry_policy_total"] == 1
            assert client.metrics["missing_expiry_policy_total"] == 1

    asyncio.run(_case())


def test_hybrid_policy_rejects_when_backfill_not_ready():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"hyb-2","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0,"entry_policy":"IMMEDIATE","expiry_policy":"BAR_CLOSE","backfill_status":"LOADING"}',
        }

        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            assert mock_gen.call_count == 0
            assert client.metrics["rejected_total"] == 1
            assert client.metrics["backfill_violation_total"] == 1

    asyncio.run(_case())


def test_hybrid_policy_rejects_when_validator_state_fails():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"hyb-3","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0,"entry_policy":"IMMEDIATE","expiry_policy":"BAR_CLOSE","backfill_status":"READY","transition_allowed":false,"validator_passed":false,"validator_failures":["STATE_TRANSITION_BLOCKED"]}',
        }

        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            assert mock_gen.call_count == 0
            assert client.metrics["rejected_total"] == 1
            assert client.metrics["validator_state_error_total"] == 1

    asyncio.run(_case())
