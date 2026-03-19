from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

from data_client import AureusMarketDataClient



def _bar_payload(ts: bytes = b"1678888000") -> dict[bytes, bytes]:
    return {
        b"open": b"2000.0",
        b"high": b"2005.0",
        b"low": b"1995.0",
        b"close": b"2002.0",
        b"volume": b"100",
        b"timestamp": ts,
    }


def test_replay_duplicate_stream_ids_increment_duplicate_metric():
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
                    (b"10-0", _bar_payload()),
                    (b"10-0", _bar_payload()),
                    (b"11-0", _bar_payload()),
                ],
            ]
        ]

        await client._poll_market_data_once()

        assert client.msg_bus.publish.call_count == 2
        assert client.metrics["duplicates_total"] == 1

    asyncio.run(_case())


def test_replay_stale_then_fresh_entries_only_publish_fresh_data():
    async def _case():
        client = AureusMarketDataClient(
            redis_client=AsyncMock(),
            stream_name="aureus:stream:XAUUSD:candle",
            instrument_id="XAUUSD.SIM",
        )
        client.msg_bus = Mock()
        client.msg_bus.publish = Mock()
        client._last_id = "20-0"

        client.redis_client.xread.return_value = [
            [
                b"aureus:stream:XAUUSD:candle",
                [
                    (b"19-9", _bar_payload(b"1678887000")),
                    (b"21-0", _bar_payload(b"1678889000")),
                ],
            ]
        ]

        await client._poll_market_data_once()

        assert client.msg_bus.publish.call_count == 1
        assert client.metrics["duplicates_total"] == 1

    asyncio.run(_case())
