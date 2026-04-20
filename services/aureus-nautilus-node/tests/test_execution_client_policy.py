from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from execution_client import AureusExecutionClient


def _client(symbols=None):
    settings = SimpleNamespace(
        symbol_whitelist=symbols or ["XAUUSD", "EURUSD"],
        require_sl_tp=True,
        max_order_notional=10_000.0,
    )
    return AureusExecutionClient(redis_client=AsyncMock(), settings=settings)


def test_discover_order_streams_without_matches_does_not_fallback_xauusd_stream():
    async def _case():
        client = _client()
        client.redis_client.keys.return_value = []

        discovered = await client._discover_order_streams()

        assert discovered == {}

    asyncio.run(_case())


def test_stream_payload_symbol_mismatch_rejected_with_reason_code():
    async def _case():
        client = _client()
        message = {
            b"type": b"ORDER_OPEN",
            b"data": b'{"trace_id":"mismatch-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
        }

        with patch.object(client, "generate_order") as mock_gen:
            client._handle_message(message, stream_symbol="EURUSD")
            assert mock_gen.call_count == 0
            assert client.metrics["rejected_total"] == 1
            assert client.metrics["symbol_stream_mismatch_total"] == 1

    asyncio.run(_case())


def test_poll_multi_stream_updates_per_stream_last_id_independently():
    async def _case():
        client = _client()
        streams = {
            "aureus:stream:XAUUSD:orders": "0-0",
            "aureus:stream:EURUSD:orders": "0-0",
        }
        client.redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:orders",
                [
                    (
                        b"101-0",
                        {
                            b"type": b"ORDER_OPEN",
                            b"data": b'{"trace_id":"x-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
                        },
                    )
                ],
            ],
            [
                b"aureus:stream:EURUSD:orders",
                [
                    (
                        b"205-0",
                        {
                            b"type": b"ORDER_OPEN",
                            b"data": b'{"trace_id":"e-1","symbol":"EURUSD","side":"SELL","qty":1.0,"sl":1.2,"tp":1.1}',
                        },
                    )
                ],
            ],
        ]

        with patch.object(client, "generate_order") as mock_gen:
            await client._poll_orders_once(streams)
            assert mock_gen.call_count == 6
            assert client._last_ids["aureus:stream:XAUUSD:orders"] == "101-0"
            assert client._last_ids["aureus:stream:EURUSD:orders"] == "205-0"

    asyncio.run(_case())
