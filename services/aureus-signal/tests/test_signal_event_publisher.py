"""
tests/test_signal_event_publisher.py — Phase 26 signal event publisher tests

Covers:
- Channel name building
- publish_signal_event async flow
- publish_strategy_match payload shape
- Error handling returns False
"""
import os
import sys
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure engine module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.signal_event_publisher import (
    _build_channel,
    publish_signal_event,
    publish_strategy_match,
    CHANNEL_PREFIX,
)


class TestBuildChannel:
    def test_build_channel_format(self):
        assert _build_channel("XAUUSD") == "aureus:signals:XAUUSD"

    def test_build_channel_prefix(self):
        assert _build_channel("EURUSD").startswith(CHANNEL_PREFIX)


@pytest.mark.asyncio
class TestPublishSignalEvent:
    async def test_publish_success(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        result = await publish_signal_event(
            mock_redis, "XAUUSD", "SIGNAL_EVENT", 1700000000,
            {"signals_snapshot_keys": ["zigzag_state", "ob_state"]}
        )
        assert result is True
        mock_redis.publish.assert_called_once()

        # Verify channel name
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "aureus:signals:XAUUSD"

        # Verify payload structure
        payload = json.loads(call_args[0][1])
        assert payload["type"] == "SIGNAL_EVENT"
        assert payload["symbol"] == "XAUUSD"
        assert payload["t"] == 1700000000
        assert "data" in payload

    async def test_publish_failure_returns_false(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(side_effect=Exception("Connection lost"))

        result = await publish_signal_event(
            mock_redis, "XAUUSD", "SIGNAL_EVENT", 1700000000, {}
        )
        assert result is False


@pytest.mark.asyncio
class TestPublishStrategyMatch:
    async def test_publish_strategy_match_payload(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=2)

        strategy_result = {
            "strategy": "CHOCH_UP",
            "strategy_id": 10,
            "side": "BUY",
            "entry_type": "MARKET",
            "size_value": 1.0,
            "size_mode": "FIXED_UNITS",
            "magic_number": 10000,
            "sl": 1950.5,
            "tp": 1970.0,
            "reason_code": "OK",
            "origin_timestamp": 1700000000,
            "t": 1700000000,
            "normalized_signal_snapshot": {"atr": 2.5, "ema_21": 3345.12},
        }

        result = await publish_strategy_match(mock_redis, "XAUUSD", strategy_result)
        assert result is True

        call_args = mock_redis.publish.call_args
        payload = json.loads(call_args[0][1])
        assert payload["type"] == "STRATEGY_MATCH"
        assert payload["symbol"] == "XAUUSD"
        assert payload["data"]["strategy"] == "CHOCH_UP"
        assert payload["data"]["magic_number"] == 10000
        assert payload["data"]["size_value"] == 1.0
        assert payload["data"]["size_mode"] == "FIXED_UNITS"
        assert payload["data"]["entry_type"] == "MARKET"
        assert payload["data"]["signal_snapshot"] == {"atr": 2.5, "ema_21": 3345.12}

    async def test_publish_strategy_match_with_missing_fields(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=0)

        strategy_result = {"t": 100, "strategy": "TEST"}
        result = await publish_strategy_match(mock_redis, "XAUUSD", strategy_result)
        assert result is True

        call_args = mock_redis.publish.call_args
        payload = json.loads(call_args[0][1])
        assert payload["data"]["entry_type"] == "MARKET"
        assert payload["data"]["size_mode"] == "FIXED_UNITS"
        assert payload["data"]["signal_snapshot"] == {}
