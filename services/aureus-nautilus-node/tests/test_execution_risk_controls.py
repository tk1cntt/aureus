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


def test_order_without_sl_tp_is_rejected_in_strict_mode():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"r1","symbol":"XAUUSD","side":"BUY","qty":1.0}',
        }
        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            assert mock_gen.call_count == 0
            assert client.metrics["missing_sl_tp_total"] == 1
            assert client.metrics["rejected_total"] == 1

    asyncio.run(_case())


def test_duplicate_trace_id_is_ignored():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"dup-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
        }
        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            client._handle_message(message)
            assert mock_gen.call_count == 3
            assert client.metrics["duplicate_trace_id_total"] == 1
            assert client.metrics["rejected_total"] == 1

    asyncio.run(_case())


def test_valid_order_generates_entry_plus_sl_tp_contingents():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"ok-1","symbol":"XAUUSD","side":"BUY","quantity":2.0,"sl":1988.0,"tp":2028.0}',
        }
        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            assert mock_gen.call_count == 3
            kinds = [call[0][0]["kind"] for call in mock_gen.call_args_list]
            assert kinds == ["ENTRY", "STOP_LOSS", "TAKE_PROFIT"]
            entry = mock_gen.call_args_list[0][0][0]
            assert entry["qty"] == 2.0

    asyncio.run(_case())


def test_duplicate_trace_id_rejected_with_stable_reason_and_no_regenerate():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"dup-stable-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
        }
        with patch.object(client, "generate_order") as mock_gen, patch.object(client, "_reject") as mock_reject:
            client._handle_message(message)
            client._handle_message(message)
            assert mock_gen.call_count == 3
            mock_reject.assert_called_once()
            assert mock_reject.call_args[0][0] == "DUPLICATE_TRACE_ID"

    asyncio.run(_case())
