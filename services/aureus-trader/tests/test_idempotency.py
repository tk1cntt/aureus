"""
Unit tests for idempotency.py using fakeredis.
"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from fakeredis import FakeAsyncRedis
except ImportError:
    pytest.skip("fakeredis not installed", allow_module_level=True)

from idempotency import IdempotencyChecker


@pytest.fixture
def redis_client():
    return FakeAsyncRedis()


@pytest.fixture
def checker(redis_client):
    return IdempotencyChecker(redis_client, ttl=86400)


@pytest.mark.asyncio
async def test_new_order_not_duplicate(checker):
    """First call to check_and_mark returns True (new order)."""
    result = await checker.check_and_mark("ord-abc123")
    assert result is True


@pytest.mark.asyncio
async def test_duplicate_order_detected(checker):
    """Second call with same cmd_id returns False (duplicate)."""
    result1 = await checker.check_and_mark("ord-abc123")
    assert result1 is True

    result2 = await checker.check_and_mark("ord-abc123")
    assert result2 is False


@pytest.mark.asyncio
async def test_mark_processed(redis_client, checker):
    """Manually marking then checking is_duplicate returns True."""
    await checker.mark_processed("ord-xyz789")
    is_dup = await checker.is_duplicate("ord-xyz789")
    assert is_dup is True


@pytest.mark.asyncio
async def test_is_duplicate_returns_false_for_new(checker):
    """is_duplicate returns False for a cmd_id that was never marked."""
    is_dup = await checker.is_duplicate("ord-neverseen")
    assert is_dup is False


@pytest.mark.asyncio
async def test_different_orders_not_confused(checker):
    """Different cmd_ids should not interfere with each other."""
    await checker.check_and_mark("ord-order1")
    await checker.check_and_mark("ord-order2")

    # Both should be marked as processed
    assert await checker.is_duplicate("ord-order1") is True
    assert await checker.is_duplicate("ord-order2") is True

    # New order should still be accepted
    result = await checker.check_and_mark("ord-order3")
    assert result is True
