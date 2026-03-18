import pytest
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

# Need to ensure we can import DBWriter
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

def test_position_ingest(db_writer):
    async def run_test():
        mock_conn = AsyncMock()
        
        class MockAcquire:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
                
        db_writer.pg_pool.acquire.return_value = MockAcquire()
        
        mock_pipe = AsyncMock()
        db_writer.redis.pipeline.return_value = mock_pipe

        event_time = int(time.time() * 1000)
        position_payload = {
            "event_time": event_time,
            "symbol": "XAUUSD",
            "position_id": "pos_123",
            "side": "BUY",
            "qty": 1.0,
            "avg_entry_price": 3000.5,
            "mark_price": 3005.0,
            "unrealized_pnl": 4.5,
            "realized_pnl": 0.0
        }
        
        db_writer.position_buffer.append(
            ("aureus:stream:XAUUSD:positions", "123456789-0", {"data": json.dumps(position_payload)})
        )
        
        await db_writer.process_batch()
        
        mock_conn.executemany.assert_called_once()
        query, data_rows = mock_conn.executemany.call_args[0]
        
        assert "INSERT INTO aureus_position_snapshots" in query
        assert len(data_rows) == 1
        
        row = data_rows[0]
        assert row[1] == "XAUUSD"
        assert row[2] == "pos_123"
        assert row[3] == "BUY"
        assert row[4] == 1.0
        assert row[5] == 3000.5
        
        mock_pipe.xack.assert_called_once_with("aureus:stream:XAUUSD:positions", "aureus-db-writers", "123456789-0")
        mock_pipe.execute.assert_called_once()
        
    asyncio.run(run_test())

def test_account_ingest(db_writer):
    async def run_test():
        mock_conn = AsyncMock()
        
        class MockAcquire:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
                
        db_writer.pg_pool.acquire.return_value = MockAcquire()
        
        mock_pipe = AsyncMock()
        db_writer.redis.pipeline.return_value = mock_pipe

        event_time = int(time.time() * 1000)
        account_payload = {
            "event_time": event_time,
            "account_id": "acc_main",
            "equity": 10050.0,
            "balance": 10000.0,
            "margin_used": 100.0,
            "margin_free": 9950.0,
            "unrealized_pnl": 50.0,
            "realized_pnl": -10.0
        }
        
        db_writer.account_buffer.append(
            ("aureus:stream:XAUUSD:account", "987654321-0", {"data": json.dumps(account_payload)})
        )
        
        await db_writer.process_batch()
        
        mock_conn.executemany.assert_called_once()
        query, data_rows = mock_conn.executemany.call_args[0]
        
        assert "INSERT INTO aureus_account_snapshots" in query
        assert len(data_rows) == 1
        
        row = data_rows[0]
        assert row[1] == "acc_main"
        assert row[2] == 10050.0  # equity
        assert row[3] == 10000.0  # balance
        assert row[4] == 100.0    # margin_used
        assert row[5] == 9950.0   # margin_free
        
        mock_pipe.xack.assert_called_once_with("aureus:stream:XAUUSD:account", "aureus-db-writers", "987654321-0")
        mock_pipe.execute.assert_called_once()
        
    asyncio.run(run_test())
