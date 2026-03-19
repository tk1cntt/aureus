import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from data_client import AureusMarketDataClient
from nautilus_trader.core.message import Event
from nautilus_trader.model.data import Bar

@pytest.mark.asyncio
async def test_market_data_client_parses_redis_candle():
    client = AureusMarketDataClient(
        redis_client=AsyncMock(), 
        stream_name="aureus:stream:XAUUSD:candle",
        instrument_id="XAUUSD.SIM"
    )
    # mock msg bus
    client.msg_bus = AsyncMock()
    
    # Mock redis xread to return 1 candle
    client.redis_client.xread.return_value = [
        [b"aureus:stream:XAUUSD:candle", [
            (b"1678888-0", {
                b"open": b"2000.0", 
                b"high": b"2005.0", 
                b"low": b"1995.0", 
                b"close": b"2002.0", 
                b"volume": b"100", 
                b"timestamp": b"1678888000"
            })
        ]]
    ]
    with patch.object(client.msg_bus, 'publish') as mock_publish:
        await client._poll_market_data_once()
        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, Bar)
        assert getattr(event, "open") == 2000.0
