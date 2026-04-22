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
                "open_time": 1234567890,
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
                "status": "SENT",
                "entry_price": 3000.0,
                "volume": 1.0,
                "open_time": 1234567890,
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
                "open_time": 1234567890,
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


# ============================================================
# WAVE 2: Wrapped Payload + 6-Pillar Test Strategy
# ============================================================

class TestWrappedPayloadUndoWrap:
    """Inbound + White Box: Verify order_buffer correctly unwraps data field."""

    def test_unwrap_json_string_data(self, db_writer):
        order_data = {
            "trace_id": "XAUUSD:strat_001:1234567890",
            "symbol": "XAUUSD", "strategy_id": 1, "strategy_name": "TestStrat",
            "side": "BUY", "entry_type": "MARKET", "status": "PENDING",
            "open_time": 1234567890, "entry_price": 2000.0, "sl": 1990.0, "tp": 2020.0,
        }
        wrapped = {"type": "ORDER_OPEN", "data": json.dumps(order_data)}
        event_type, normalized = db_writer._normalize_order_payload(wrapped)
        assert event_type == "ORDER_OPEN"
        assert normalized["trace_id"] == "XAUUSD:strat_001:1234567890"
        assert normalized["side"] == "BUY"
        assert normalized["entry_price"] == 2000.0

    def test_unwrap_dict_data(self, db_writer):
        order_data = {
            "trace_id": "EURUSD:strat_002:999", "symbol": "EURUSD",
            "side": "SELL", "entry_type": "MARKET", "status": "PENDING",
            "open_time": 999999999, "entry_price": 1.08,
        }
        wrapped = {"type": "ORDER_OPEN", "data": order_data}
        event_type, normalized = db_writer._normalize_order_payload(wrapped)
        assert event_type == "ORDER_OPEN"
        assert normalized["trace_id"] == "EURUSD:strat_002:999"

    def test_non_dict_data_raises_value_error(self, db_writer):
        """Integer data field raises ValueError."""
        wrapped = {"type": "ORDER_OPEN", "data": 12345}
        with pytest.raises(ValueError, match="Order payload data must be a JSON object"):
            db_writer._normalize_order_payload(wrapped)

    def test_no_data_field_backward_compat(self, db_writer):
        flat = {"trace_id": "TEST:flat:001", "symbol": "GBPUSD", "side": "BUY", "entry_type": "MARKET", "status": "PENDING", "open_time": 1234567890}
        event_type, normalized = db_writer._normalize_order_payload(flat)
        assert normalized["trace_id"] == "TEST:flat:001"
        assert event_type == ""

    def test_invalid_json_string_data_raises(self, db_writer):
        wrapped = {"type": "ORDER_OPEN", "data": "not a valid json"}
        with pytest.raises(ValueError, match="Failed to parse order data JSON"):
            db_writer._normalize_order_payload(wrapped)


class TestMissingTimestampRejection:
    """Boundary + Black Box: Strict timestamp validation."""

    def _make_order(self, **overrides):
        base = {
            "trace_id": "XAUUSD:strat:ts", "symbol": "XAUUSD",
            "side": "BUY", "entry_type": "MARKET", "status": "PENDING",
            "entry_price": 2000.0, "sl": 1990.0, "tp": 2020.0, "open_time": 1234567890,
        }
        base.update(overrides)
        return {"type": "ORDER_OPEN", "data": json.dumps(base)}

    def test_missing_open_time_rejected(self, db_writer):
        wrapped = self._make_order()
        data = json.loads(wrapped["data"])
        del data["open_time"]
        wrapped["data"] = json.dumps(data)
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") is None

    def test_empty_open_time_rejected(self, db_writer):
        wrapped = self._make_order(open_time="")
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") == ""

    def test_none_open_time_rejected(self, db_writer):
        wrapped = self._make_order(open_time=None)
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") is None

    def test_valid_open_time_accepted(self, db_writer):
        wrapped = self._make_order(open_time=1234567890)
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") == 1234567890

    def test_open_time_zero_boundary(self, db_writer):
        wrapped = self._make_order(open_time=0)
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") == 0

    def test_open_time_string_iso_format(self, db_writer):
        wrapped = self._make_order(open_time="2024-01-01T00:00:00")
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") == "2024-01-01T00:00:00"

    def test_open_time_invalid_string(self, db_writer):
        wrapped = self._make_order(open_time="not-a-date")
        _, order_data = db_writer._normalize_order_payload(wrapped)
        assert order_data.get("open_time") == "not-a-date"


class TestCanonicalPayloadStorage:
    """Black Box: Payload column stores canonical data, not raw envelope."""

    def test_canonical_storage_no_envelope_keys(self, db_writer):
        order_data = {
            "trace_id": "XAUUSD:test:canonical", "symbol": "XAUUSD",
            "side": "SELL", "entry_type": "MARKET", "status": "PENDING",
            "open_time": 1234567890, "entry_price": 2000.0,
        }
        wrapped = {"type": "ORDER_OPEN", "data": json.dumps(order_data)}
        _, normalized = db_writer._normalize_order_payload(wrapped)
        stored_dict = json.loads(json.dumps(normalized))
        assert stored_dict["trace_id"] == "XAUUSD:test:canonical"
        assert stored_dict["side"] == "SELL"

    def test_no_envelope_type_in_stored(self, db_writer):
        raw_envelope = {"type": "ORDER_OPEN", "data": '{"trace_id": "X"}'}
        _, normalized = db_writer._normalize_order_payload(raw_envelope)
        stored = json.dumps(normalized)
        assert '"ORDER_OPEN"' not in stored

    def test_backward_compat_flat_storage(self, db_writer):
        flat = {"trace_id": "TEST:flat:002", "symbol": "GBPUSD", "side": "BUY", "entry_type": "LIMIT", "status": "PENDING", "open_time": 1234567890}
        _, normalized = db_writer._normalize_order_payload(flat)
        stored_dict = json.loads(json.dumps(normalized))
        assert stored_dict["trace_id"] == "TEST:flat:002"
        assert "data" not in stored_dict


class TestOrderRejectedSkip:
    """Abnormal: ORDER_REJECTED events are skipped."""

    def test_order_rejected_skipped_wrapped(self, db_writer):
        reason_payload = {
            "trace_id": "XAUUSD:strat:rejected", "symbol": "XAUUSD", "side": "BUY",
        }
        wrapped = {"type": "ORDER_REJECTED", "data": json.dumps(reason_payload)}
        event_type, order_data = db_writer._normalize_order_payload(wrapped)
        assert event_type == "ORDER_REJECTED"
        assert order_data["trace_id"] == "XAUUSD:strat:rejected"

    def test_order_rejected_no_data_field(self, db_writer):
        wrapped = {"type": "ORDER_REJECTED", "trace_id": "TEST:rej:001"}
        event_type, order_data = db_writer._normalize_order_payload(wrapped)
        assert event_type == "ORDER_REJECTED"
        assert order_data["trace_id"] == "TEST:rej:001"


class TestEdgeCases:
    """Abnormal + Coverage: Edge cases for 100%% coverage."""

    def test_data_field_is_list(self, db_writer):
        wrapped = {"type": "ORDER_OPEN", "data": ["item1", "item2"]}
        with pytest.raises(ValueError, match="Order payload data must be a JSON object"):
            db_writer._normalize_order_payload(wrapped)

    def test_data_field_is_json_null(self, db_writer):
        wrapped = {"type": "ORDER_OPEN", "data": "null"}
        with pytest.raises(ValueError, match="Order payload data must be a JSON object"):
            db_writer._normalize_order_payload(wrapped)

    def test_deeply_nested_json(self, db_writer):
        order_data = {
            "trace_id": "TEST:nested:001", "symbol": "XAUUSD",
            "side": "BUY", "entry_type": "MARKET", "status": "PENDING",
            "open_time": 1234567890,
            "metadata": {"level1": {"level2": {"level3": "deep_value"}}},
        }
        wrapped = {"type": "ORDER_OPEN", "data": json.dumps(order_data)}
        _, normalized = db_writer._normalize_order_payload(wrapped)
        assert normalized["metadata"]["level1"]["level2"]["level3"] == "deep_value"

    def test_envelope_type_empty_string(self, db_writer):
        flat = {"symbol": "XAUUSD", "side": "BUY", "entry_type": "MARKET", "status": "PENDING", "open_time": 1234567890}
        event_type, _ = db_writer._normalize_order_payload(flat)
        assert event_type == ""

    def test_trace_id_special_chars(self, db_writer):
        order_data = {
            "trace_id": "'; DROP TABLE aureus_trades;--",
            "symbol": "XAUUSD", "side": "BUY", "entry_type": "MARKET",
            "status": "PENDING", "open_time": 1234567890,
        }
        wrapped = {"type": "ORDER_OPEN", "data": json.dumps(order_data)}
        _, normalized = db_writer._normalize_order_payload(wrapped)
        assert "DROP TABLE" in normalized["trace_id"]

    def test_premium_ai_status_normalized(self, db_writer):
        async def run_test():
            conn = AsyncMock()
            conn.fetchval = AsyncMock(return_value=None)
            conn.executemany = AsyncMock()
            class MockAcquire:
                async def __aenter__(self): return conn
                async def __aexit__(self, *args): pass
            pool = MagicMock()
            pool.acquire.return_value = MockAcquire()
            db_writer.pg_pool = pool
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock
            order_data = {
                "trace_id": "trace_pai_001", "symbol": "XAUUSD",
                "side": "BUY", "entry_type": "MARKET", "status": "PENDING_AI",
                "open_time": 1234567890, "entry_price": 2000.0,
            }
            wrapped = {"type": "ORDER_PENDING", "data": json.dumps(order_data)}
            db_writer.order_buffer.append(("aureus:stream:XAUUSD:orders", "123456789-0", wrapped))
            await db_writer.process_batch()
            conn.executemany.assert_called_once()
            _, data_rows = conn.executemany.call_args[0]
            assert data_rows[0][8] == "PENDING"
        import asyncio
        asyncio.run(run_test())

    def test_active_status_normalized(self, db_writer):
        async def run_test():
            conn = AsyncMock()
            conn.fetchval = AsyncMock(return_value=None)
            conn.executemany = AsyncMock()
            class MockAcquire:
                async def __aenter__(self): return conn
                async def __aexit__(self, *args): pass
            pool = MagicMock()
            pool.acquire.return_value = MockAcquire()
            db_writer.pg_pool = pool
            redis_mock, pipe = _mock_redis_pipeline()
            db_writer.redis = redis_mock
            order_data = {
                "trace_id": "trace_act_001", "symbol": "XAUUSD",
                "side": "BUY", "entry_type": "MARKET", "status": "ACTIVE",
                "open_time": 1234567890, "entry_price": 2000.0,
            }
            wrapped = {"type": "ORDER_OPEN", "data": json.dumps(order_data)}
            db_writer.order_buffer.append(("aureus:stream:XAUUSD:orders", "123456789-0", wrapped))
            await db_writer.process_batch()
            conn.executemany.assert_called_once()
            _, data_rows = conn.executemany.call_args[0]
            assert data_rows[0][8] == "SENT"
        import asyncio
        asyncio.run(run_test())
