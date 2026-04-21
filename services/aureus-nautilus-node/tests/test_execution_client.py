import asyncio
from unittest.mock import AsyncMock, patch

from execution_client import AureusExecutionClient


def test_execution_client_converts_order_intent():
    async def _case():
        client = AureusExecutionClient(redis_client=AsyncMock())
        client.redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:orders",
                [
                    (
                        b"1678888-0",
                        {
                            b"type": b"ORDER_OPEN",
                            b"data": b'{"trace_id": "test_1", "symbol": "XAUUSD", "side": "BUY", "qty": 1.0, "sl": 1990.0, "tp": 2020.0}',
                        },
                    )
                ],
            ]
        ]

        with patch.object(client, "generate_order") as mock_gen:
            await client._poll_orders_once({"aureus:stream:XAUUSD:orders": "0-0"})
            assert mock_gen.call_count == 3
            entry = mock_gen.call_args_list[0][0][0]
            assert entry["kind"] == "ENTRY"
            assert entry["instrument_id"] == "XAUUSD.AUREUS_VIRTUAL"

    asyncio.run(_case())


def test_order_open_missing_critical_field_has_stable_reason_code():
    async def _case():
        client = AureusExecutionClient(redis_client=AsyncMock())
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
        }

        with patch.object(client, "generate_order") as mock_gen, patch.object(client, "_reject") as mock_reject:
            client._handle_message(message)
            assert mock_gen.call_count == 0
            mock_reject.assert_called_once()
            assert mock_reject.call_args[0][0] == "ORDER_OPEN_MISSING_CRITICAL_FIELD"

    asyncio.run(_case())


def test_order_open_quantity_alias_is_normalized_to_qty():
    async def _case():
        client = AureusExecutionClient(redis_client=AsyncMock())
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"q-alias-1","symbol":"XAUUSD","side":"BUY","quantity":1.25,"sl":1990.0,"tp":2020.0}',
        }

        with patch.object(client, "generate_order") as mock_gen, patch.object(client, "_reject") as mock_reject:
            client._handle_message(message)
            assert mock_reject.call_count == 0
            assert mock_gen.call_count == 3
            entry = mock_gen.call_args_list[0][0][0]
            assert entry["qty"] == 1.25

    asyncio.run(_case())


def test_optional_fields_fallback_increments_metrics():
    async def _case():
        client = AureusExecutionClient(redis_client=AsyncMock())
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"fallback-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
        }

        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message)
            assert mock_gen.call_count == 3
            assert client.metrics["order_open_optional_fallback_total"] == 3

    asyncio.run(_case())
