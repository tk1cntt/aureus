"""
Unit tests for dispatcher.py
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dispatcher import is_retryable, RETRYABLE_NACK_REASONS, NON_RETRYABLE_NACK_REASONS


class TestIsRetryable:
    def test_is_retryable_trade_disabled(self):
        event = {"type": "NACK", "reason": "TRADE_DISABLED"}
        assert is_retryable(event) is True

    def test_is_retryable_market_closed(self):
        event = {"type": "ORDER_FAILED", "reason": "MARKET_CLOSED"}
        assert is_retryable(event) is True

    def test_is_retryable_server_busy(self):
        event = {"type": "ORDER_FAILED", "reason": "SERVER_BUSY"}
        assert is_retryable(event) is True

    def test_is_retryable_server_error_keyword(self):
        event = {
            "type": "ORDER_FAILED",
            "reason": "UNKNOWN",
            "message": "server error occurred",
        }
        assert is_retryable(event) is True

    def test_is_retryable_busy_keyword(self):
        event = {
            "type": "ORDER_FAILED",
            "reason": "UNKNOWN",
            "message": "system is busy, try again",
        }
        assert is_retryable(event) is True


class TestNotRetryable:
    def test_not_retryable_duplicate(self):
        event = {"type": "NACK", "reason": "DUPLICATE"}
        assert is_retryable(event) is False

    def test_not_retryable_invalid_command(self):
        event = {"type": "NACK", "reason": "INVALID_COMMAND"}
        assert is_retryable(event) is False

    def test_not_retryable_unknown_symbol(self):
        event = {"type": "NACK", "reason": "UNKNOWN_SYMBOL"}
        assert is_retryable(event) is False

    def test_not_retryable_insufficient_margin(self):
        event = {"type": "ORDER_FAILED", "reason": "INSUFFICIENT_MARGIN"}
        assert is_retryable(event) is False

    def test_not_retryable_invalid_stops(self):
        event = {"type": "ORDER_FAILED", "reason": "INVALID_STOPS"}
        assert is_retryable(event) is False

    def test_not_retryable_unknown_reason(self):
        event = {"type": "NACK", "reason": "SOME_OTHER_REASON"}
        assert is_retryable(event) is False


class TestOrderDispatcherQueue:
    """Test OrderDispatcher enqueue behavior with mock Redis."""

    @pytest.mark.asyncio
    async def test_enqueue_order_success(self):
        """Order enqueued when queue is not full."""
        from dispatcher import OrderDispatcher
        from config import TraderConfig

        mock_redis = FakeRedisMock()
        config = TraderConfig(max_queue_size=100)
        dispatcher = OrderDispatcher(mock_redis, config)

        order = {"cmd_id": "ord-test123", "symbol": "XAUUSD"}
        result = await dispatcher.enqueue_order(order)

        assert result is True
        assert mock_redis.lpop_queue[-1] == '{"cmd_id": "ord-test123", "symbol": "XAUUSD"}'

    @pytest.mark.asyncio
    async def test_enqueue_order_queue_full(self):
        """Order rejected when queue size >= max_queue_size."""
        from dispatcher import OrderDispatcher
        from config import TraderConfig

        mock_redis = FakeRedisMock(queue_size=100)
        config = TraderConfig(max_queue_size=100)
        dispatcher = OrderDispatcher(mock_redis, config)

        order = {"cmd_id": "ord-test456", "symbol": "BTCUSD"}
        result = await dispatcher.enqueue_order(order)

        assert result is False


class FakeRedisMock:
    """Minimal fake Redis for queue tests without fakeredis."""

    def __init__(self, queue_size=0):
        self._queue_size = queue_size
        self.lpop_queue = []

    async def llen(self, key):
        return self._queue_size

    async def rpush(self, key, value):
        self.lpop_queue.append(value)

    async def publish(self, channel, message):
        pass

    def pubsub(self):
        return FakePubSub()


class FakePubSub:
    async def subscribe(self, *channels):
        pass

    async def unsubscribe(self, *channels):
        pass
