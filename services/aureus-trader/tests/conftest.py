"""
Test fixtures for Trade Journal tests.
"""
import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from journal import TradeJournalManager


class MockDBConnection:
    """Mock asyncpg connection for testing."""

    def __init__(self):
        self.queries = []
        self.results = {}
        self._insert_counter = 0

    async def fetchval(self, query, *args):
        self.queries.append(("fetchval", query, args))
        return self.results.get("fetchval", 1)

    async def fetchrow(self, query, *args):
        self.queries.append(("fetchrow", query, args))
        if "UPDATE aureus_trade_journal" in query and "RETURNING" in query:
            execute_result = self.results.get("execute", "UPDATE 1")
            if execute_result != "UPDATE 1":
                return None
        return self.results.get("fetchrow", {
            "id": 1,
            "trace_id": args[0],
            "entry_time": datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc),
            "direction": "BUY",
            "symbol": "XAUUSD",
            "active_signals": [{"tag": "liquidity_sweep", "status": "active"}],
            "context_filters": {"session": "london"},
            "strategy_name": "chandelier_breakout",
        })

    async def execute(self, query, *args):
        self.queries.append(("execute", query, args))
        return self.results.get("execute", "UPDATE 1")

    def transaction(self):
        return _MockDBContextManager(self)


class MockDBPool:
    """Mock asyncpg connection pool."""

    def __init__(self, connection=None):
        self._conn = connection or MockDBConnection()
        self.acquired = []

    def acquire(self):
        self.acquired.append(True)
        return _MockDBContextManager(self._conn)

    def set_result(self, method_name, value):
        self._conn.results[method_name] = value


class _MockDBContextManager:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


class MockRedisClient:
    """Minimal mock Redis for pub/sub tests."""

    def __init__(self):
        self.published = []
        self._queue = []

    async def publish(self, channel, message):
        self.published.append((channel, message))

    async def llen(self, key):
        return len(self._queue)

    async def rpush(self, key, value):
        self._queue.append(value)

    def pubsub(self):
        return MockPubSub()


class MockPubSub:
    async def subscribe(self, *channels):
        pass

    async def unsubscribe(self, *channels):
        pass


@pytest.fixture
def mock_db_pool():
    """Provide a mock DB pool."""
    return MockDBPool()


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    return MockRedisClient()


@pytest.fixture
def journal_manager(mock_db_pool):
    """Provide a TradeJournalManager with mock DB pool."""
    return TradeJournalManager(mock_db_pool)


@pytest.fixture
def valid_strategy_match_event():
    """Provide a valid STRATEGY_MATCH event."""
    from datetime import datetime, timezone
    return {
        "type": "STRATEGY_MATCH",
        "trace_id": "trace-test-journal-001",
        "data": {
            "strategy_name": "chandelier_breakout",
            "strategy_id": 101,
            "direction": "BUY",
            "symbol": "XAUUSD",
            "score": 0.85,
            "active_signals": [
                {"tag": "liquidity_sweep", "weight": 0.7, "status": "active"},
                {"tag": "break_of_structure", "weight": 0.8, "status": "active"}
            ],
            "context_filters": {
                "htf_trend": "bearish",
                "session": "london",
                "ob_alignment": "aligned",
                "ema_trend": "below"
            },
            "origin_timestamp": datetime(2026, 4, 8, 14, 0, 0, tzinfo=timezone.utc).timestamp()
        }
    }


@pytest.fixture
def valid_order_opened_event():
    """Provide a valid ORDER_OPENED event."""
    return {
        "type": "ORDER_OPENED",
        "trace_id": "trace-test-journal-001",
        "ticket": 12345,
        "open_price": 3250.50,
        "sl": 3247.50,
        "tp": 3256.50,
        "volume": 0.01,
        "position_id": 67890,
        "time": 1744095600,
        "entry_type": "LIMIT"
    }


@pytest.fixture
def valid_order_closed_event():
    """Provide a valid ORDER_CLOSED event."""
    return {
        "type": "ORDER_CLOSED",
        "trace_id": "trace-test-journal-001",
        "ticket": 12345,
        "close_price": 3260.50,
        "close_time": 1744102800,
        "profit": 10.00,
        "commission": 0.05,
        "swap": 0.01,
        "close_reason": "TP_HIT",
        "open_price": 3250.50
    }
