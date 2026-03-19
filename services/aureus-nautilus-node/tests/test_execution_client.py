import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from execution_client import AureusExecutionClient

@pytest.mark.asyncio
async def test_execution_client_converts_order_intent():
    client = AureusExecutionClient(redis_client=AsyncMock())
    # mock order intent
    client.redis_client.xread.return_value = [
        [b"aureus:stream:XAUUSD:orders", [
            (b"1678888-0", {
                b"type": b"ORDER_OPEN", 
                b"data": b'{"trace_id": "test_1", "symbol": "XAUUSD", "side": "BUY", "qty": 1.0, "sl": 1990.0, "tp": 2020.0}'
            })
        ]]
    ]
    with patch.object(client, 'generate_order') as mock_gen:
        await client._poll_orders_once()
        assert mock_gen.called
        # Check generated order
        order = mock_gen.call_args[0][0]
        # Depending on OCO or bracket order logic
        assert order.instrument_id.symbol.value == "XAUUSD"
