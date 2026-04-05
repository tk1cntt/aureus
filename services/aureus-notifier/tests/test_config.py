"""Tests for config.py"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import (
    FilterConfig,
    Route,
    load_filters,
    load_routes,
    passes_filter,
    match_routes,
    subscribe_config_updates,
)


# ── load_filters tests ──

@pytest.mark.asyncio
async def test_load_filters_defaults():
    """Empty Redis returns enabled=True with default signal_types."""
    mock_redis = AsyncMock()
    mock_redis.hgetall.return_value = {}

    result = await load_filters(mock_redis)

    assert result.enabled is True
    assert result.signal_types == {"SIGNAL_EVENT", "STRATEGY_MATCH"}
    assert result.symbols == set()
    assert result.strategies == set()
    assert result.min_confidence is None


@pytest.mark.asyncio
async def test_load_filters_from_redis():
    """Mock HGETALL returns values, verify parsed correctly."""
    mock_redis = AsyncMock()
    mock_redis.hgetall.return_value = {
        "enabled": "false",
        "signal_types": "SIGNAL_EVENT",
        "symbols": "XAUUSD,BTCUSD",
        "strategies": "CHOCH_UP",
        "min_confidence": "0.8",
    }

    result = await load_filters(mock_redis)

    assert result.enabled is False
    assert result.signal_types == {"SIGNAL_EVENT"}
    assert result.symbols == {"XAUUSD", "BTCUSD"}
    assert result.strategies == {"CHOCH_UP"}
    assert result.min_confidence == 0.8


# ── passes_filter tests ──

def test_passes_filter_enabled_false():
    """Returns False when enabled=False."""
    config = FilterConfig(enabled=False)
    event = {"type": "SIGNAL_EVENT", "symbol": "XAUUSD", "data": {}}
    assert passes_filter(config, event) is False


def test_passes_filter_signal_type_mismatch():
    """Returns False when event type not in signal_types."""
    config = FilterConfig(enabled=True, signal_types={"STRATEGY_MATCH"})
    event = {"type": "SIGNAL_EVENT", "symbol": "XAUUSD", "data": {}}
    assert passes_filter(config, event) is False


def test_passes_filter_symbol_mismatch():
    """Returns False when symbol not in symbols set."""
    config = FilterConfig(enabled=True, symbols={"XAUUSD", "BTCUSD"})
    event = {"type": "SIGNAL_EVENT", "symbol": "EURUSD", "data": {}}
    assert passes_filter(config, event) is False


def test_passes_filter_all_match():
    """Returns True when all criteria match."""
    config = FilterConfig(
        enabled=True,
        signal_types={"SIGNAL_EVENT", "STRATEGY_MATCH"},
        symbols={"XAUUSD"},
        strategies=set(),
    )
    event = {"type": "SIGNAL_EVENT", "symbol": "XAUUSD", "data": {}}
    assert passes_filter(config, event) is True


# ── match_routes tests ──

def test_match_routes_exact():
    """Event matches route with exact event_type, symbol, strategy."""
    routes = [
        Route(
            chat_id="chat_1",
            event_types=["STRATEGY_MATCH"],
            symbols=["XAUUSD"],
            strategies=["CHOCH_UP"],
        )
    ]
    event = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "data": {"strategy": "CHOCH_UP"},
    }
    result = match_routes(event, routes)
    assert result == ["chat_1"]


def test_match_routes_wildcard():
    """Route with null symbols/strategies matches any event."""
    routes = [
        Route(
            chat_id="chat_all",
            event_types=["SIGNAL_EVENT"],
            symbols=None,
            strategies=None,
        )
    ]
    event = {"type": "SIGNAL_EVENT", "symbol": "ANYTHING", "data": {}}
    result = match_routes(event, routes)
    assert result == ["chat_all"]


def test_match_routes_no_match():
    """Event doesn't match route criteria."""
    routes = [
        Route(
            chat_id="chat_1",
            event_types=["STRATEGY_MATCH"],
            symbols=["XAUUSD"],
            strategies=None,
        )
    ]
    event = {"type": "SIGNAL_EVENT", "symbol": "XAUUSD", "data": {}}
    result = match_routes(event, routes)
    assert result == []


def test_match_routes_multiple():
    """One event matches multiple routes, returns multiple chat_ids."""
    routes = [
        Route(chat_id="chat_1", event_types=["SIGNAL_EVENT"], symbols=["XAUUSD"]),
        Route(chat_id="chat_2", event_types=["SIGNAL_EVENT"], symbols=None),
        Route(chat_id="chat_3", event_types=["STRATEGY_MATCH"]),
    ]
    event = {"type": "SIGNAL_EVENT", "symbol": "XAUUSD", "data": {}}
    result = match_routes(event, routes)
    assert "chat_1" in result
    assert "chat_2" in result
    assert "chat_3" not in result
    assert len(result) == 2


def test_match_routes_partial_criteria():
    """Route filters only by event_type, not symbol."""
    routes = [
        Route(
            chat_id="chat_type_only",
            event_types=["SIGNAL_EVENT"],
            symbols=None,
            strategies=None,
        )
    ]
    event = {"type": "SIGNAL_EVENT", "symbol": "RANDOM_SYMBOL", "data": {}}
    result = match_routes(event, routes)
    assert result == ["chat_type_only"]


# ── load_routes tests ──

@pytest.mark.asyncio
async def test_load_routes_empty():
    """Empty Redis returns empty list."""
    mock_redis = AsyncMock()
    mock_redis.hget.return_value = None

    result = await load_routes(mock_redis)
    assert result == []


@pytest.mark.asyncio
async def test_load_routes_from_redis():
    """Mock HGET returns JSON, verify parsed correctly."""
    mock_redis = AsyncMock()
    routes_data = [
        {"chat_id": "123", "event_types": ["SIGNAL_EVENT"], "symbols": ["XAUUSD"]},
        {"chat_id": "456", "event_types": None, "symbols": None},
    ]
    mock_redis.hget.return_value = json.dumps(routes_data)

    result = await load_routes(mock_redis)

    assert len(result) == 2
    assert result[0].chat_id == "123"
    assert result[0].event_types == ["SIGNAL_EVENT"]
    assert result[0].symbols == ["XAUUSD"]
    assert result[1].chat_id == "456"
    assert result[1].event_types is None


# ── subscribe_config_updates tests ──

@pytest.mark.asyncio
async def test_subscribe_config_updates_calls_callback():
    """Verify callback is called when message received on config channel."""
    mock_pubsub = MagicMock()

    # Simulate pubsub.listen() yielding a message then blocking
    async def mock_listen():
        yield {"type": "message", "data": "reload"}
        # Block forever after first message
        await asyncio.Event().wait()

    mock_pubsub.listen = mock_listen
    mock_pubsub.subscribe = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    callback_called = False

    async def mock_callback():
        nonlocal callback_called
        callback_called = True

    # Run with timeout to avoid infinite loop
    with patch("config.REDIS_CONFIG_CHANNEL", "test_channel"):
        task = asyncio.create_task(subscribe_config_updates(mock_redis, mock_callback))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert callback_called is True
