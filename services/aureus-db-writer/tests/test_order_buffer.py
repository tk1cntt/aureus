"""Tests for order_buffer consumption and state transition validation in DB writer."""

import pytest
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import DBWriter


@pytest.fixture
def db_writer():
    writer = DBWriter()
    writer.redis = MagicMock()
    writer.pg_pool = MagicMock()
    return writer


def _mock_conn():
    """Create a mock asyncpg connection with fetchval support."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)  # No existing record by default
    conn.executemany = AsyncMock()
    return conn


def _mock_pool(conn):
    """Create a mock connection pool."""
    class MockAcquire:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    pool = MagicMock()
    pool.acquire.return_value = MockAcquire()
    return pool


def _mock_redis_pipeline():
    """Create a mock Redis pipeline."""
    pipe = AsyncMock()
    pipe.xack = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock()
    redis_mock = MagicMock()
    redis_mock.pipeline.return_value = pipe
    return redis_mock, pipe


class TestOrderBufferValidTransition:
    """Test valid PENDING→SENT transition inserts successfully."""

    def test_valid_pending_to_sent_inserts(self, db_writer):
        async def run_test():
            conn = _mock_conn()
            db_writer.pg_pool = _mock_pool(conn)
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock

            order_payload = {
                "trace_id": "trace_001",
                "ticket": 1001,
                "symbol": "XAUUSD",
                "magic_number": 12345,
                "strategy_id": 1,
                "strategy_name": "test_strategy",
                "direction": "BUY",
                "entry_type": "MARKET",
                "status": "PENDING",
                "entry_price": 3000.0,
                "volume": 1.0,
            }

            db_writer.order_buffer.append(
                ("aureus:stream:XAUUSD:orders", "123456789-0", order_payload)
            )

            await db_writer.process_batch()

            conn.executemany.assert_called_once()
            query, data_rows = conn.executemany.call_args[0]

            assert "INSERT INTO aureus_trades" in query
            assert "ON CONFLICT (trace_id) DO UPDATE SET" in query
            assert len(data_rows) == 1

            row = data_rows[0]
            assert row[0] == "trace_001"  # trace_id
            assert row[1] == 1001         # ticket
            assert row[2] == "XAUUSD"     # symbol
            assert row[3] == 12345        # magic_number
            assert row[6] == "BUY"        # direction
            assert row[8] == "PENDING"    # status
            assert row[9] == 3000.0       # entry_price

            # Verify ACK was called
            pipe.xack.assert_called()

        asyncio.run(run_test())


class TestOrderBufferInvalidTransition:
    """Test invalid PENDING→FILLED transition is rejected (not inserted)."""

    def test_invalid_pending_to_filled_rejected(self, db_writer):
        async def run_test():
            conn = _mock_conn()
            db_writer.pg_pool = _mock_pool(conn)
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock

            order_payload = {
                "trace_id": "trace_002",
                "ticket": 1002,
                "symbol": "XAUUSD",
                "magic_number": 12345,
                "direction": "BUY",
                "entry_type": "MARKET",
                "status": "FILLED",  # Invalid: skip SENT
                "entry_price": 3000.0,
                "volume": 1.0,
            }

            db_writer.order_buffer.append(
                ("aureus:stream:XAUUSD:orders", "123456789-0", order_payload)
            )

            await db_writer.process_batch()

            # Should NOT call executemany (rejected by state machine)
            conn.executemany.assert_not_called()

        asyncio.run(run_test())


class TestOrderBufferConflictUpdate:
    """Test ON CONFLICT updates existing record with merged payload."""

    def test_conflict_updates_existing(self, db_writer):
        async def run_test():
            conn = _mock_conn()
            # Simulate existing record with PENDING status
            conn.fetchval = AsyncMock(return_value="PENDING")
            db_writer.pg_pool = _mock_pool(conn)
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock

            order_payload = {
                "trace_id": "trace_003",
                "ticket": 1003,
                "symbol": "XAUUSD",
                "magic_number": 12345,
                "direction": "BUY",
                "entry_type": "MARKET",
                "status": "SENT",  # Valid: PENDING→SENT
                "entry_price": 3000.0,
                "volume": 1.0,
            }

            db_writer.order_buffer.append(
                ("aureus:stream:XAUUSD:orders", "123456789-0", order_payload)
            )

            await db_writer.process_batch()

            conn.executemany.assert_called_once()
            query, data_rows = conn.executemany.call_args[0]

            assert "ON CONFLICT (trace_id) DO UPDATE SET" in query
            assert "payload = aureus_trades.payload || EXCLUDED.payload" in query

        asyncio.run(run_test())


class TestOrderBufferMissingTraceId:
    """Test missing trace_id is skipped + logged."""

    def test_missing_trace_id_skipped(self, db_writer):
        async def run_test():
            conn = _mock_conn()
            db_writer.pg_pool = _mock_pool(conn)
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock

            order_payload = {
                # No trace_id!
                "ticket": 1004,
                "symbol": "XAUUSD",
                "magic_number": 12345,
                "direction": "BUY",
                "entry_type": "MARKET",
                "status": "PENDING",
                "entry_price": 3000.0,
                "volume": 1.0,
            }

            db_writer.order_buffer.append(
                ("aureus:stream:XAUUSD:orders", "123456789-0", order_payload)
            )

            await db_writer.process_batch()

            # Should NOT call executemany
            conn.executemany.assert_not_called()

        asyncio.run(run_test())


class TestOrderBufferMagicNumber:
    """Test magic_number preserved in record."""

    def test_magic_number_preserved(self, db_writer):
        async def run_test():
            conn = _mock_conn()
            db_writer.pg_pool = _mock_pool(conn)
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock

            order_payload = {
                "trace_id": "trace_005",
                "ticket": 1005,
                "symbol": "XAUUSD",
                "magic_number": 99999,
                "strategy_id": 5,
                "strategy_name": "magic_strategy",
                "direction": "SELL",
                "entry_type": "LIMIT",
                "status": "PENDING",
                "entry_price": 3050.0,
                "volume": 0.5,
            }

            db_writer.order_buffer.append(
                ("aureus:stream:XAUUSD:orders", "123456789-0", order_payload)
            )

            await db_writer.process_batch()

            query, data_rows = conn.executemany.call_args[0]
            row = data_rows[0]

            assert row[3] == 99999  # magic_number
            assert row[4] == 5      # strategy_id
            assert row[5] == "magic_strategy"  # strategy_name
            assert row[6] == "SELL"  # direction
            assert row[7] == "LIMIT"  # entry_type

        asyncio.run(run_test())
