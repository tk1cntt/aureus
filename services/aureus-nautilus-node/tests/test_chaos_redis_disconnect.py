from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

from data_client import AureusMarketDataClient



def _valid_bar_payload() -> dict[bytes, bytes]:
    return {
        b"open": b"2000.0",
        b"high": b"2005.0",
        b"low": b"1995.0",
        b"close": b"2002.0",
        b"volume": b"100",
        b"timestamp": b"1678888000",
    }


def test_market_data_client_recovers_after_transient_redis_disconnect():
    async def _case():
        client = AureusMarketDataClient(
            redis_client=AsyncMock(),
            stream_name="aureus:stream:XAUUSD:candle",
            instrument_id="XAUUSD.SIM",
            max_read_retries=3,
            retry_backoff_ms=0,
        )
        client.msg_bus = Mock()
        client.msg_bus.publish = Mock()

        client.redis_client.xread.side_effect = [
            ConnectionError("redis unavailable"),
            [
                [
                    b"aureus:stream:XAUUSD:candle",
                    [(b"2-0", _valid_bar_payload())],
                ]
            ],
        ]

        await client._poll_market_data_once()

        assert client.metrics["read_error_total"] == 1
        assert client.msg_bus.publish.call_count == 1

    asyncio.run(_case())


def test_market_data_client_stops_after_retry_budget_exhausted():
    async def _case():
        client = AureusMarketDataClient(
            redis_client=AsyncMock(),
            stream_name="aureus:stream:XAUUSD:candle",
            instrument_id="XAUUSD.SIM",
            max_read_retries=1,
            retry_backoff_ms=0,
        )
        client.msg_bus = Mock()
        client.msg_bus.publish = Mock()

        client.redis_client.xread.side_effect = [
            ConnectionError("redis unavailable"),
            ConnectionError("redis still unavailable"),
        ]

        await client._poll_market_data_once()

        assert client.metrics["read_error_total"] == 2
        assert client.msg_bus.publish.call_count == 0

    asyncio.run(_case())
