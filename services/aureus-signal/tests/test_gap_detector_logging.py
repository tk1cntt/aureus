import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import logging
import sys
import os
import asyncpg
import pytest

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.gap_detector import GapDetector

class TestGapDetectorLogging(unittest.IsolatedAsyncioTestCase):
    async def test_find_gaps_logging_format(self):
        """
        AC 1: Logger name must be aureus-signal.gap-detector.
        AC 2: Each log entry must be prefixed with [symbol] [function_name].
        AC 3: Within the function, logs must be sequenced like 1..., 2..., etc.
        """
        symbol = "XAUUSD"
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        
        # Proper async context manager mock
        cm = AsyncMock()
        cm.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value = cm

        detector = GapDetector(mock_pool)
        
        with patch('engine.gap_detector.logger') as mock_logger:
            await detector.find_gaps(symbol)
            
            # Check if logs were called with correct sequence and prefix
            # Note: We haven't implemented them yet, so this SHOULD fail.
            
            calls = mock_logger.debug.call_args_list
            print(f"\nDEBUG: calls={calls}")
            self.assertTrue(len(calls) >= 2, f"Should have at least 2 debug logs, found {len(calls)}")
            
            # 1... Start log
            self.assertIn(f"[{symbol}] [find_gaps] 1... Starting gap detection", calls[0][0][0])
            
            # 2... Post-query log
            self.assertIn(f"[{symbol}] [find_gaps] 2... Query completed", calls[1][0][0])

    async def test_find_gaps_error_logging_format(self):
        """
        AC 4: The error log in the catch block must also follow this pattern.
        """
        symbol = "XAUUSD"
        mock_pool = MagicMock(spec=asyncpg.Pool)
        mock_pool.acquire.side_effect = Exception("DB Error")
        
        detector = GapDetector(mock_pool)
        
        with patch('engine.gap_detector.logger') as mock_logger:
            await detector.find_gaps(symbol)
            
            mock_logger.error.assert_called()
            error_msg = mock_logger.error.call_args[0][0]
            self.assertIn(f"[{symbol}] [find_gaps] 4... Error: Gap detection query failed", error_msg)

if __name__ == '__main__':
    unittest.main()
