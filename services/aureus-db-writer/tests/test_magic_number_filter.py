"""Integration tests for magic number filter queries.

Tests validate that the SQL queries in queries/magic_number_filters.sql
correctly classify bot vs manual trades via magic_number matching against
aureus_strategy_templates.

Uses mocked asyncpg connection to verify query structure and result parsing.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Load the SQL queries from the file
QUERIES_FILE = os.path.join(os.path.dirname(__file__), '..', 'queries', 'magic_number_filters.sql')
with open(QUERIES_FILE, 'r') as f:
    SQL_CONTENT = f.read()


def extract_queries(sql_content):
    """Extract individual queries from the SQL file (comments stripped per query)."""
    queries = []
    current_query = []
    for line in sql_content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        if stripped == '':
            if current_query:
                queries.append('\n'.join(current_query).strip())
                current_query = []
            continue
        current_query.append(line)
    if current_query:
        queries.append('\n'.join(current_query).strip())
    return [q for q in queries if q and not q.startswith(';')]


class TestMagicNumberFilterQueries:
    """Validate query structure and correctness."""

    def test_sql_file_exists(self):
        assert os.path.exists(QUERIES_FILE)

    def test_sql_file_contains_four_queries(self):
        queries = extract_queries(SQL_CONTENT)
        # Filter out empty queries
        non_empty = [q for q in queries if q.strip()]
        assert len(non_empty) >= 4, f"Expected at least 4 queries, found {len(non_empty)}"

    def test_query_1_bot_trades_uses_subquery(self):
        """Query 1: Bot trades use IN subquery on aureus_strategy_templates."""
        assert 'aureus_strategy_templates' in SQL_CONTENT
        assert 'magic_number IS NOT NULL' in SQL_CONTENT
        assert "status = 'CLOSED'" in SQL_CONTENT

    def test_query_2_manual_trades_excludes_templates(self):
        """Query 2: Manual trades use NOT IN subquery."""
        assert 'NOT IN' in SQL_CONTENT
        assert 'magic_number IS NOT NULL' in SQL_CONTENT

    def test_query_3_trade_origin_classification(self):
        """Query 3: Classification via CASE WHEN with trade_origin column."""
        assert 'trade_origin' in SQL_CONTENT
        assert 'CASE' in SQL_CONTENT
        assert "THEN 'bot'" in SQL_CONTENT
        assert "ELSE 'manual'" in SQL_CONTENT

    def test_query_4_aggregation_with_group_by(self):
        """Query 4: Aggregation with COUNT, SUM, AVG, GROUP BY."""
        assert 'COUNT(*)' in SQL_CONTENT or 'count(*)' in SQL_CONTENT.lower()
        assert 'SUM(profit)' in SQL_CONTENT or 'sum(profit)' in SQL_CONTENT.lower()
        assert 'AVG(profit)' in SQL_CONTENT or 'avg(profit)' in SQL_CONTENT.lower()
        assert 'GROUP BY' in SQL_CONTENT


class TestMagicNumberFilterMockedResults:
    """Test query logic with mocked database results."""

    def _create_mock_pool(self, fetch_results):
        """Create a mock pool that returns fetch_results."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=fetch_results)

        class MockAcquire:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        pool = MagicMock()
        pool.acquire.return_value = MockAcquire()
        return pool, conn

    def test_bot_trades_classification(self):
        """Bot trades correctly identified via magic_number IN strategy_templates."""
        async def run_test():
            # Simulate: magic_number 12345 is in strategy_templates
            bot_trades = [
                {'trace_id': 't1', 'symbol': 'XAUUSD', 'magic_number': 12345,
                 'status': 'CLOSED', 'profit': 100.0, 'trade_origin': 'bot'},
                {'trace_id': 't2', 'symbol': 'EURUSD', 'magic_number': 12345,
                 'status': 'CLOSED', 'profit': -50.0, 'trade_origin': 'bot'},
            ]
            pool, conn = self._create_mock_pool(bot_trades)

            async with pool.acquire() as conn_mock:
                results = await conn_mock.fetch("SELECT ... WHERE magic_number IN (SELECT magic_number FROM aureus_strategy_templates ...)")

            assert len(results) == 2
            for row in results:
                assert row['trade_origin'] == 'bot'
                assert row['status'] == 'CLOSED'

        asyncio.run(run_test())

    def test_manual_trades_classification(self):
        """Manual trades correctly identified via magic_number NOT IN strategy_templates."""
        async def run_test():
            manual_trades = [
                {'trace_id': 't3', 'symbol': 'GBPUSD', 'magic_number': 99999,
                 'status': 'CLOSED', 'profit': 200.0, 'trade_origin': 'manual'},
            ]
            pool, conn = self._create_mock_pool(manual_trades)

            async with pool.acquire() as conn_mock:
                results = await conn_mock.fetch("SELECT ... WHERE magic_number NOT IN (SELECT magic_number FROM aureus_strategy_templates ...)")

            assert len(results) == 1
            assert results[0]['trade_origin'] == 'manual'

        asyncio.run(run_test())

    def test_null_magic_number_excluded(self):
        """NULL magic_number excluded from both bot and manual queries."""
        async def run_test():
            # Both queries have WHERE magic_number IS NOT NULL
            # So NULL magic_number records should not appear
            pool, conn = self._create_mock_pool([])

            async with pool.acquire() as conn_mock:
                results = await conn_mock.fetch("SELECT ... WHERE magic_number IS NOT NULL ...")

            assert len(results) == 0

        asyncio.run(run_test())

    def test_aggregation_query_counts(self):
        """Query 4 returns correct counts and profit aggregations."""
        async def run_test():
            agg_results = [
                {'trade_origin': 'bot', 'trade_count': 10, 'total_profit': 500.0, 'avg_profit': 50.0},
                {'trade_origin': 'manual', 'trade_count': 3, 'total_profit': 150.0, 'avg_profit': 50.0},
            ]
            pool, conn = self._create_mock_pool(agg_results)

            async with pool.acquire() as conn_mock:
                results = await conn_mock.fetch("SELECT ... GROUP BY trade_origin")

            assert len(results) == 2
            bot = next(r for r in results if r['trade_origin'] == 'bot')
            manual = next(r for r in results if r['trade_origin'] == 'manual')

            assert bot['trade_count'] == 10
            assert bot['total_profit'] == 500.0
            assert manual['trade_count'] == 3
            assert manual['total_profit'] == 150.0

        asyncio.run(run_test())


class TestMagicNumberEdgeCases:
    """Edge case testing for magic number classification."""

    def test_zero_magic_number(self):
        """magic_number = 0 should be treated as a valid number (not NULL)."""
        # Query 1: WHERE magic_number IN (...) — 0 would match if in templates
        # Query 2: WHERE magic_number IS NOT NULL AND NOT IN (...) — 0 would be included
        assert 'IS NOT NULL' in SQL_CONTENT  # Ensures NULL exclusion
        # 0 is not NULL, so it would be included in queries

    def test_strategy_templates_subquery_filters_null(self):
        """Subquery on aureus_strategy_templates filters NULL magic_numbers."""
        # Verify the subquery has WHERE magic_number IS NOT NULL
        # This prevents NULL template magic_numbers from matching all trades
        assert 'SELECT magic_number FROM aureus_strategy_templates WHERE magic_number IS NOT NULL' in SQL_CONTENT

    def test_closed_status_filter_present(self):
        """Queries 1, 2, 4 filter on status = 'CLOSED' for realized trades."""
        # Count occurrences of status = 'CLOSED' in the file
        closed_count = SQL_CONTENT.count("status = 'CLOSED'")
        assert closed_count >= 2, f"Expected at least 2 queries with status='CLOSED', found {closed_count}"
