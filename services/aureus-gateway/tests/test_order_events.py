import pytest
import json
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import process_message

@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.hget = AsyncMock(return_value=None)
    r.hset = AsyncMock()
    r.xadd = AsyncMock()
    r.publish = AsyncMock()
    return r

@pytest.mark.asyncio
async def test_order_opened_event(mock_redis):
    data = {
        "type": "ORDER_OPENED", "cmd_id": "ord-001", "symbol": "XAUUSD",
        "ticket": 12345678, "direction": "BUY", "order_type": "MARKET",
        "volume": 0.1, "open_price": 1960.25, "sl": 1950.50, "tp": 1970.00,
        "magic": 10001, "t": 1712376000000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "aureus:mt5:events"

@pytest.mark.asyncio
async def test_order_closed_event(mock_redis):
    data = {
        "type": "ORDER_CLOSED", "symbol": "XAUUSD", "ticket": 12345678,
        "direction": "BUY", "volume": 0.1, "open_price": 1960.25,
        "close_price": 1968.50, "profit": 82.50, "commission": -0.70,
        "swap": 0.00, "magic": 10001, "t": 1712379600000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_order_failed_event(mock_redis):
    data = {
        "type": "ORDER_FAILED", "cmd_id": "ord-001", "symbol": "XAUUSD",
        "reason": "INSUFFICIENT_MARGIN", "retcode": 10019, "t": 1712376000000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_ack_event(mock_redis):
    data = {"type": "ACK", "cmd_id": "ord-001", "t": 1712376000000}
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_nack_event(mock_redis):
    data = {"type": "NACK", "cmd_id": "ord-001", "reason": "DUPLICATE", "t": 1712376000000}
    result = await process_message(mock_redis, data, source="TCP")
    assert result is True
    mock_redis.publish.assert_called_once()

@pytest.mark.asyncio
async def test_order_event_invalid_fields(mock_redis):
    """ORDER_OPENED missing required 'ticket' field should fail validation."""
    data = {
        "type": "ORDER_OPENED", "cmd_id": "ord-001", "symbol": "XAUUSD",
        "direction": "BUY", "t": 1712376000000
    }
    result = await process_message(mock_redis, data, source="TCP")
    assert result is False
    mock_redis.publish.assert_not_called()

@pytest.mark.asyncio
async def test_order_event_publishes_correct_channel(mock_redis):
    """Verify events go to aureus:mt5:events channel."""
    data = {
        "type": "ORDER_OPENED", "cmd_id": "ord-002", "symbol": "BTCUSD",
        "ticket": 99999, "direction": "SELL", "order_type": "LIMIT",
        "volume": 0.5, "open_price": 60000.0, "sl": 61000.0, "tp": 58000.0,
        "magic": 20001, "t": 1712376000000
    }
    await process_message(mock_redis, data, source="TCP")
    channel = mock_redis.publish.call_args[0][0]
    assert channel == "aureus:mt5:events"

@pytest.mark.asyncio
async def test_order_event_json_payload(mock_redis):
    """Verify published JSON contains expected fields."""
    data = {
        "type": "ORDER_CLOSED", "symbol": "XAUUSD", "ticket": 12345678,
        "direction": "BUY", "volume": 0.1, "open_price": 1960.25,
        "close_price": 1968.50, "profit": 82.50, "commission": -0.70,
        "swap": 0.00, "magic": 10001, "t": 1712379600000
    }
    await process_message(mock_redis, data, source="TCP")
    published_json = mock_redis.publish.call_args[0][1]
    parsed = json.loads(published_json)
    assert parsed["type"] == "ORDER_CLOSED"
    assert parsed["ticket"] == 12345678
    assert parsed["profit"] == 82.50
