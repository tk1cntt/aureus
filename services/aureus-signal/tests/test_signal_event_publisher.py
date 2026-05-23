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
            "score_total": 0.812345,
            "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
            "weights_snapshot": {"signal_quality": 0.30},
            "missing_data_policy": "impute_neutral_and_flag",
            "score_version": "scor-v1.0.0",
            "signal_schema_version": "sig-v2.0.0",
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
        assert payload["data"]["score_total"] == 0.812345
        assert payload["data"]["score_breakdown"] == {"criteria": [{"name": "signal_quality", "normalized": 0.8}]}
        assert payload["data"]["weights_snapshot"] == {"signal_quality": 0.30}
        assert payload["data"]["missing_data_policy"] == "impute_neutral_and_flag"
        assert payload["data"]["score_version"] == "scor-v1.0.0"
        assert payload["data"]["signal_schema_version"] == "sig-v2.0.0"

    async def test_publish_strategy_match_derives_indicator_fields_into_signal_snapshot(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        strategy_result = {
            "strategy": "CHOCH_UP",
            "strategy_id": 10,
            "t": 1700000000,
            "origin_timestamp": 1700000000,
            "normalized_signal_snapshot": {"zigzag_state": {"status": "OK"}},
            "indicator_snapshot": {
                "emas": {"values": [3345.12, 3344.34, 3343.55, 3342.89, 3342.10, 3341.20]},
                "bb_m15": {"upper": 3352.55, "middle": 3342.0, "lower": 3331.12},
                "bb_m5": {"upper": 3350.55, "middle": 3341.0, "lower": 3332.12},
                "cisd_mtf": {"M15": "bearish", "M5": "bullish"},
                "tpo_d0": {"POC": 4690.0, "VAH": 4730.0, "VAL": 4680.0},
                "tpo_d1": {"POC": 4696.92, "VAH": 4736.72, "VAL": 4685.42},
                "tpo_d2": {"POC": 4688.0, "VAH": 4720.0, "VAL": 4670.0},
                "tpo_d3": {"POC": 4677.0, "VAH": 4710.0, "VAL": 4660.0},
            },
        }

        result = await publish_strategy_match(mock_redis, "XAUUSD", strategy_result)
        assert result is True

        payload = json.loads(mock_redis.publish.call_args[0][1])
        snapshot = payload["data"]["signal_snapshot"]
        assert snapshot["ema_21"] == 3345.12
        assert snapshot["ema_55"] == 3343.55
        assert snapshot["bb_m15_up"] == 3352.55
        assert snapshot["bb_m15_dn"] == 3331.12
        assert snapshot["bb_m5_up"] == 3350.55
        assert snapshot["bb_m5_dn"] == 3332.12
        assert snapshot["cisd_m15"] == "BEARISH"
        assert snapshot["cisd_m5"] == "BULLISH"
        assert snapshot["tpo_d0"] == {"POC": 4690.0, "VAH": 4730.0, "VAL": 4680.0}
        assert snapshot["tpo_d1"] == {"POC": 4696.92, "VAH": 4736.72, "VAL": 4685.42}
        assert snapshot["tpo_d2"] == {"POC": 4688.0, "VAH": 4720.0, "VAL": 4670.0}
        assert snapshot["tpo_d3"] == {"POC": 4677.0, "VAH": 4710.0, "VAL": 4660.0}
        assert "zigzag_state" in snapshot

    async def test_publish_strategy_match_derives_extra_indicator_fields_into_signal_snapshot(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        strategy_result = {
            "strategy": "CHOCH_UP",
            "strategy_id": 10,
            "t": 1700000000,
            "origin_timestamp": 1700000000,
            "normalized_signal_snapshot": {},
            "indicator_snapshot": {
                "atr_14": "2.75",
                "vol_sma20": 12345.0,
                "session": "LONDON",
                "candle_color_d1": "BULLISH",
                "candle_color_H1": "BEARISH",
                "candle_color_M30": "BULL",
                "candle_color_M15": "BEAR",
                "candle_color_m5": 1,
            },
        }

        result = await publish_strategy_match(mock_redis, "XAUUSD", strategy_result)
        assert result is True

        payload = json.loads(mock_redis.publish.call_args[0][1])
        snapshot = payload["data"]["signal_snapshot"]
        assert snapshot["atr"] == pytest.approx(2.75)
        assert snapshot["vol_sma_20"] == pytest.approx(12345.0)
        assert snapshot["session"] == 2
        assert snapshot["candle_color_d1"] == 1
        assert snapshot["candle_color_h1"] == -1
        assert snapshot["candle_color_m30"] == 1
        assert snapshot["candle_color_m15"] == -1
        assert snapshot["candle_color_m5"] == 1

    async def test_publish_strategy_match_keeps_existing_snapshot_values_on_conflict(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        strategy_result = {
            "strategy": "CHOCH_UP",
            "strategy_id": 10,
            "t": 1700000000,
            "origin_timestamp": 1700000000,
            "normalized_signal_snapshot": {"ema_21": 9999.0, "bb_m15_up": 4444.0},
            "indicator_snapshot": {
                "emas": {"values": [3345.12, 3344.34, 3343.55, 3342.89, 3342.10, 3341.20]},
                "bb_m15": {"upper": 3352.55, "middle": 3342.0, "lower": 3331.12},
            },
        }

        result = await publish_strategy_match(mock_redis, "XAUUSD", strategy_result)
        assert result is True

        payload = json.loads(mock_redis.publish.call_args[0][1])
        snapshot = payload["data"]["signal_snapshot"]
        assert snapshot["ema_21"] == 9999.0
        assert snapshot["bb_m15_up"] == 4444.0

    async def test_publish_strategy_match_merges_partial_tpo_d1_without_dropping_d0_d2_d3(self):
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)

        strategy_result = {
            "strategy": "TREND_CONT_BULL",
            "strategy_id": 260523,
            "t": 1700000000,
            "origin_timestamp": 1700000000,
            "normalized_signal_snapshot": {
                "tpo_d1": {"POC": 4696.92, "CLOSE": 4701.5},
            },
            "indicator_snapshot": {
                "tpo_d0": {"POC": 4690.0, "VAH": 4730.0, "VAL": 4680.0, "OPEN": 4688.0, "HIGH": 4732.0, "LOW": 4678.0, "CLOSE": 4700.0},
                "tpo_d1": {"POC": 4696.92, "VAH": 4736.72, "VAL": 4685.42, "OPEN": 4690.0, "HIGH": 4740.0, "LOW": 4680.0, "CLOSE": 4702.0},
                "tpo_d2": {"POC": 4688.0, "VAH": 4720.0, "VAL": 4670.0, "OPEN": 4680.0, "HIGH": 4722.0, "LOW": 4668.0, "CLOSE": 4698.0},
                "tpo_d3": {"POC": 4677.0, "VAH": 4710.0, "VAL": 4660.0, "OPEN": 4670.0, "HIGH": 4712.0, "LOW": 4658.0, "CLOSE": 4688.0},
            },
        }

        result = await publish_strategy_match(mock_redis, "XAUUSD", strategy_result)
        assert result is True

        payload = json.loads(mock_redis.publish.call_args[0][1])
        snapshot = payload["data"]["signal_snapshot"]
        assert snapshot["tpo_d0"]["POC"] == 4690.0
        assert snapshot["tpo_d1"] == {
            "POC": 4696.92,
            "CLOSE": 4701.5,
            "VAH": 4736.72,
            "VAL": 4685.42,
            "OPEN": 4690.0,
            "HIGH": 4740.0,
            "LOW": 4680.0,
        }
        assert snapshot["tpo_d2"]["POC"] == 4688.0
        assert snapshot["tpo_d3"]["POC"] == 4677.0

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
