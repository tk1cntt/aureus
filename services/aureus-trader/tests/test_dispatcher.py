"""
Unit tests for dispatcher.py
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dispatcher import is_retryable, RETRYABLE_NACK_REASONS, NON_RETRYABLE_NACK_REASONS, OrderDispatcher


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
    def __init__(self, messages=None):
        self._messages = list(messages or [])

    async def subscribe(self, *channels):
        pass

    async def unsubscribe(self, *channels):
        pass

    async def listen(self):
        for msg in self._messages:
            yield msg


class EventRedisMock(FakeRedisMock):
    def __init__(self, messages=None):
        super().__init__(queue_size=0)
        self._pubsub = FakePubSub(messages=messages)

    def pubsub(self):
        return self._pubsub


class DummyJournal:
    def __init__(self):
        self.opened_events = []
        self.closed_events = []

    async def on_order_opened(self, event):
        self.opened_events.append(event)
        return True

    async def on_order_closed(self, event):
        self.closed_events.append(event)
        return True


class TestOrderDispatcherMt5TimeMapping:
    @pytest.mark.asyncio
    async def test_dispatch_order_maps_open_time_from_t_when_missing(self):
        from config import TraderConfig

        redis_mock = EventRedisMock()
        journal = DummyJournal()
        dispatcher = OrderDispatcher(redis_mock, TraderConfig(), journal_manager=journal)

        responses = [
            {"type": "ACK", "cmd_id": "ord-open-1", "t": 1744095600000},
            {
                "type": "ORDER_OPENED",
                "cmd_id": "ord-open-1",
                "ticket": 123456,
                "symbol": "XAUUSD",
                "t": 1744095600,
            },
        ]

        async def fake_wait_for_response(cmd_id, timeout):
            return responses.pop(0)

        dispatcher._wait_for_response = fake_wait_for_response

        await dispatcher.dispatch_order({"cmd_id": "ord-open-1", "symbol": "XAUUSD", "trace_id": "tr-open-1"})

        assert len(journal.opened_events) == 1
        opened = journal.opened_events[0]
        assert opened["open_time"] == 1744095600
        assert opened["trace_id"] == "tr-open-1"

    @pytest.mark.asyncio
    async def test_event_listener_maps_close_time_from_t_when_missing(self):
        from config import TraderConfig

        message = {
            "type": "message",
            "data": '{"type":"ORDER_CLOSED","ticket":123456,"symbol":"XAUUSD","t":1744102800}',
        }
        redis_mock = EventRedisMock(messages=[message])
        journal = DummyJournal()
        dispatcher = OrderDispatcher(redis_mock, TraderConfig(), journal_manager=journal)

        task = asyncio.create_task(dispatcher.event_listener())
        await asyncio.sleep(0.05)
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task

        assert len(journal.closed_events) == 1
        closed = journal.closed_events[0]
        assert closed["close_time"] == 1744102800
        assert closed["time"] == 1744102800
        assert closed["symbol"] == "XAUUSD"
        assert closed["ticket"] == 123456

        # cleanup tasks spawned by event_listener
        await asyncio.sleep(0.05)

