from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

from data_client import AureusMarketDataClient, Bar



def _valid_payload() -> dict[bytes, bytes]:
    return {
        b"open": b"2000.0",
        b"high": b"2005.0",
        b"low": b"1995.0",
        b"close": b"2002.0",
        b"volume": b"100",
        b"timestamp": b"1678888000",
    }


def test_market_data_client_parses_redis_candle():
    async def _case():
        client = AureusMarketDataClient(
            redis_client=AsyncMock(),
            stream_name="aureus:stream:XAUUSD:candle",
            instrument_id="XAUUSD.SIM",
        )
        client.msg_bus = Mock()
        client.msg_bus.publish = Mock()

        client.redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:candle",
                [(b"1678888-0", _valid_payload())],
            ]
        ]

        await client._poll_market_data_once()
        assert client.msg_bus.publish.called
        event = client.msg_bus.publish.call_args[0][0]
        assert isinstance(event, Bar)
        assert getattr(event, "open") == 2000.0

    asyncio.run(_case())


def test_market_data_client_rejects_malformed_payload():
    async def _case():
        client = AureusMarketDataClient(
            redis_client=AsyncMock(),
            stream_name="aureus:stream:XAUUSD:candle",
            instrument_id="XAUUSD.SIM",
        )
        client.msg_bus = Mock()
        client.msg_bus.publish = Mock()

        client.redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:candle",
                [
                    (
                        b"1678888-0",
                        {
                            b"open": b"2000.0",
                            b"high": b"2005.0",
                            b"close": b"2002.0",
                            b"timestamp": b"1678888000",
                        },
                    )
                ],
            ]
        ]

        await client._poll_market_data_once()
        assert client.msg_bus.publish.call_count == 0
        assert client.metrics["malformed_payload_total"] == 1

    asyncio.run(_case())


def test_market_data_client_marks_stale_stream_id_as_duplicate():
    async def _case():
        client = AureusMarketDataClient(
            redis_client=AsyncMock(),
            stream_name="aureus:stream:XAUUSD:candle",
            instrument_id="XAUUSD.SIM",
        )
        client.msg_bus = Mock()
        client.msg_bus.publish = Mock()
        client._last_id = "5-1"

        client.redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:candle",
                [
                    (b"5-0", _valid_payload()),
                    (b"6-0", _valid_payload()),
                ],
            ]
        ]

        await client._poll_market_data_once()

        assert client.msg_bus.publish.call_count == 1
        assert client.metrics["duplicates_total"] == 1

    asyncio.run(_case())
