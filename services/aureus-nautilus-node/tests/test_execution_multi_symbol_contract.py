from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from execution_client import AureusExecutionClient


def test_default_policy_does_not_fallback_singleton_xauusd():
    client = AureusExecutionClient(redis_client=AsyncMock(), settings=None)
    assert "XAUUSD" not in client._symbol_whitelist


def test_symbol_stream_mismatch_returns_reason_code():
    client = AureusExecutionClient(redis_client=AsyncMock(), settings=None)
    payload = {
        "trace_id": "mismatch-contract-1",
        "symbol": "XAUUSD",
        "side": "BUY",
        "qty": 1.0,
        "sl": 1990.0,
        "tp": 2020.0,
        "_stream_symbol": "EURUSD",
    }

    valid, reason, orders = client._validate_and_build_orders(payload)

    assert valid is False
    assert reason == "SYMBOL_STREAM_MISMATCH"
    assert orders == []


def test_multi_stream_cursor_is_independent_per_symbol_contract():
    async def _case():
        class _Settings:
            symbol_whitelist = ["XAUUSD", "EURUSD"]
            require_sl_tp = True
            max_order_notional = 10_000.0

        redis_client = AsyncMock()
        redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:orders",
                [
                    (
                        b"301-0",
                        {
                            b"type": b"ORDER_OPEN",
                            b"data": b'{"trace_id":"x-contract-1","symbol":"XAUUSD","side":"BUY","qty":1.0,"sl":1990.0,"tp":2020.0}',
                        },
                    )
                ],
            ],
            [
                b"aureus:stream:EURUSD:orders",
                [
                    (
                        b"401-0",
                        {
                            b"type": b"ORDER_OPEN",
                            b"data": b'{"trace_id":"e-contract-1","symbol":"EURUSD","side":"SELL","qty":1.0,"sl":1.2,"tp":1.1}',
                        },
                    )
                ],
            ],
        ]

        client = AureusExecutionClient(redis_client=redis_client, settings=_Settings())
        await client._poll_orders_once(
            {
                "aureus:stream:XAUUSD:orders": "0-0",
                "aureus:stream:EURUSD:orders": "0-0",
            }
        )

        assert client._last_ids["aureus:stream:XAUUSD:orders"] == "301-0"
        assert client._last_ids["aureus:stream:EURUSD:orders"] == "401-0"

    asyncio.run(_case())
