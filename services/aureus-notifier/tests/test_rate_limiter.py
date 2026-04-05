"""Tests for rate_limiter.py"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import Route
from rate_limiter import RateLimitedDispatcher


def _make_signal_event(symbol="XAUUSD", signals=None, session="NEW_YORK"):
    return {
        "type": "SIGNAL_EVENT",
        "symbol": symbol,
        "t": 1712345678,
        "data": {
            "signals": signals or {"test": "value"},
            "session": session,
        },
    }


def _make_strategy_event(symbol="XAUUSD", strategy="CHOCH_UP", side="BUY"):
    return {
        "type": "STRATEGY_MATCH",
        "symbol": symbol,
        "t": 1712345678,
        "data": {
            "strategy": strategy,
            "strategy_id": 10,
            "side": side,
            "entry_type": "MARKET",
            "sl": 1950.50,
            "tp": 1970.00,
            "size_value": 1.0,
            "reason_code": "OK",
        },
    }


@pytest.fixture
def mock_sender():
    sender = MagicMock()
    sender.send_message = AsyncMock(return_value=True)
    return sender


@pytest.fixture
def dispatcher(mock_sender):
    return RateLimitedDispatcher(sender=mock_sender, delay=0.1, max_queue_size=10)


def test_init_creates_empty_queues(mock_sender):
    """Dispatcher starts with no queues."""
    disp = RateLimitedDispatcher(sender=mock_sender)
    assert disp.queues == {}
    assert disp._running is False


def test_get_queue_creates_new_queue(dispatcher):
    """_get_queue creates a new queue for unknown chat_id."""
    queue = dispatcher._get_queue("chat_1")
    assert isinstance(queue, asyncio.Queue)
    assert "chat_1" in dispatcher.queues


def test_get_queue_returns_existing_queue(dispatcher):
    """_get_queue returns same queue for known chat_id."""
    q1 = dispatcher._get_queue("chat_1")
    q2 = dispatcher._get_queue("chat_1")
    assert q1 is q2


@pytest.mark.asyncio
async def test_enqueue_signal_event(dispatcher):
    """enqueue formats SIGNAL_EVENT and queues for matching chats."""
    event = _make_signal_event()
    routes = [Route(chat_id="chat_1", event_types=["SIGNAL_EVENT"], symbols=None)]

    count = await dispatcher.enqueue(event, routes)

    assert count == 1
    assert "chat_1" in dispatcher.queues
    assert not dispatcher.queues["chat_1"].empty()


@pytest.mark.asyncio
async def test_enqueue_strategy_match(dispatcher):
    """enqueue formats STRATEGY_MATCH and queues for matching chats."""
    event = _make_strategy_event()
    routes = [Route(chat_id="chat_2", event_types=["STRATEGY_MATCH"], symbols=None)]

    count = await dispatcher.enqueue(event, routes)

    assert count == 1
    assert "chat_2" in dispatcher.queues


@pytest.mark.asyncio
async def test_enqueue_no_matching_routes(dispatcher):
    """enqueue returns 0 when no routes match."""
    event = _make_signal_event()
    routes = [Route(chat_id="chat_1", event_types=["STRATEGY_MATCH"])]

    count = await dispatcher.enqueue(event, routes)

    assert count == 0


@pytest.mark.asyncio
async def test_enqueue_unknown_event_type(dispatcher):
    """enqueue returns 0 for unknown event type."""
    event = {"type": "UNKNOWN_TYPE", "symbol": "XAUUSD", "data": {}}
    routes = [Route(chat_id="chat_1")]

    count = await dispatcher.enqueue(event, routes)

    assert count == 0


@pytest.mark.asyncio
async def test_enqueue_multiple_chats(dispatcher):
    """enqueue queues message to all matching chat_ids."""
    event = _make_signal_event()
    routes = [
        Route(chat_id="chat_1", event_types=["SIGNAL_EVENT"], symbols=None),
        Route(chat_id="chat_2", event_types=["SIGNAL_EVENT"], symbols=None),
    ]

    count = await dispatcher.enqueue(event, routes)

    assert count == 2
    assert "chat_1" in dispatcher.queues
    assert "chat_2" in dispatcher.queues


@pytest.mark.asyncio
async def test_enqueue_queue_full_drops_oldest():
    """enqueue drops oldest message when queue is full."""
    mock_sender = MagicMock()
    mock_sender.send_message = AsyncMock(return_value=True)
    dispatcher = RateLimitedDispatcher(sender=mock_sender, delay=0.1, max_queue_size=2)

    event1 = _make_signal_event(signals={"a": "1"})
    event2 = _make_signal_event(signals={"b": "2"})
    event3 = _make_signal_event(signals={"c": "3"})  # Should drop event1
    routes = [Route(chat_id="chat_1", event_types=["SIGNAL_EVENT"], symbols=None)]

    await dispatcher.enqueue(event1, routes)
    await dispatcher.enqueue(event2, routes)
    count = await dispatcher.enqueue(event3, routes)

    assert count == 1  # event3 enqueued after dropping event1
    queue = dispatcher.queues["chat_1"]
    assert queue.qsize() == 2  # Full queue with event2 and event3


@pytest.mark.asyncio
async def test_dispatch_loop_sends_messages(mock_sender):
    """dispatch_loop sends enqueued messages and marks them done."""
    dispatcher = RateLimitedDispatcher(sender=mock_sender, delay=0.05, max_queue_size=10)

    event = _make_signal_event()
    routes = [Route(chat_id="chat_1", event_types=["SIGNAL_EVENT"], symbols=None)]

    await dispatcher.enqueue(event, routes)

    # Run dispatch loop briefly
    task = asyncio.create_task(dispatcher.dispatch_loop())
    await asyncio.sleep(0.3)
    dispatcher.stop()

    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_sender.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_loop_requeues_on_failure():
    """dispatch_loop re-queues message if send fails."""
    mock_sender = MagicMock()
    mock_sender.send_message = AsyncMock(return_value=False)
    dispatcher = RateLimitedDispatcher(sender=mock_sender, delay=0.05, max_queue_size=10)

    event = _make_signal_event()
    routes = [Route(chat_id="chat_1", event_types=["SIGNAL_EVENT"], symbols=None)]

    await dispatcher.enqueue(event, routes)

    # Run dispatch loop briefly
    task = asyncio.create_task(dispatcher.dispatch_loop())
    await asyncio.sleep(0.3)
    dispatcher.stop()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Message should still be in queue (re-queued after failure)
    assert dispatcher.queues["chat_1"].qsize() == 1


def test_stop_sets_running_false(dispatcher):
    """stop() sets _running=False."""
    dispatcher._running = True
    dispatcher.stop()
    assert dispatcher._running is False
