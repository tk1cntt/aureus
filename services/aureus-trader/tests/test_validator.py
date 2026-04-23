"""
Unit tests for validator.py
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validator import (
    validate_strategy_match,
    ValidationResult,
    VALID_ENTRY_TYPES,
    VALID_DIRECTIONS,
    SUPPORTED_SIZE_MODES,
)


def _make_event(overrides=None):
    """Helper to create a valid STRATEGY_MATCH event with optional overrides."""
    base = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "t": 1712376000000,
        "data": {
            "strategy_id": "CHOCH_UP",
            "direction": "BUY",
            "entry_type": "MARKET",
            "entry_price": 0,
            "size_mode": "FIXED_LOT",
            "size_value": 0.1,
            "sl_absolute": 2300.0,
            "tp_absolute": 2350.0,
            "magic_number": 10001,
        },
    }
    if overrides:
        if "data" in overrides:
            base["data"].update(overrides["data"])
            del overrides["data"]
        base.update(overrides)
    return base


class TestValidEvents:
    def test_valid_market_order(self):
        event = _make_event()
        result = validate_strategy_match(event)
        assert result.valid is True
        assert result.errors == []

    def test_valid_limit_order(self):
        event = _make_event(
            {"data": {"entry_type": "LIMIT", "entry_price": 2320.0}}
        )
        result = validate_strategy_match(event)
        assert result.valid is True

    def test_valid_stop_order(self):
        event = _make_event(
            {"data": {"entry_type": "STOP", "entry_price": 2330.0}}
        )
        result = validate_strategy_match(event)
        assert result.valid is True


class TestInvalidEntryType:
    def test_invalid_entry_type(self):
        event = _make_event({"data": {"entry_type": "INVALID"}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("entry_type" in e for e in result.errors)


class TestInvalidDirection:
    def test_invalid_direction(self):
        event = _make_event({"data": {"direction": "HOLD"}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("direction" in e for e in result.errors)


class TestSizeMode:
    def test_risk_percent_rejected(self):
        event = _make_event({"data": {"size_mode": "RISK_PERCENT"}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert "RISK_PERCENT not yet supported" in result.errors

    def test_unsupported_size_mode(self):
        event = _make_event({"data": {"size_mode": "DYNAMIC"}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("size_mode" in e for e in result.errors)


class TestSizeValue:
    def test_zero_size_value(self):
        event = _make_event({"data": {"size_value": 0}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("size_value" in e for e in result.errors)

    def test_negative_size_value(self):
        event = _make_event({"data": {"size_value": -0.5}})
        result = validate_strategy_match(event)
        assert result.valid is False


class TestSLTP:
    def test_missing_sl_absolute(self):
        event = _make_event({"data": {"sl_absolute": None}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("sl_absolute" in e for e in result.errors)

    def test_missing_tp_absolute(self):
        event = _make_event({"data": {"tp_absolute": None}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("tp_absolute" in e for e in result.errors)


class TestMagicNumber:
    def test_missing_magic_number(self):
        event = _make_event({"data": {"magic_number": 0}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("magic_number" in e for e in result.errors)


class TestPendingOrderValidation:
    def test_limit_order_no_entry_price(self):
        event = _make_event({"data": {"entry_type": "LIMIT", "entry_price": 0}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("entry_price" in e for e in result.errors)

    def test_stop_order_no_entry_price(self):
        event = _make_event({"data": {"entry_type": "STOP", "entry_price": 0}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("entry_price" in e for e in result.errors)

    def test_limit_order_entry_price_numeric_string(self):
        event = _make_event({"data": {"entry_type": "LIMIT", "entry_price": "2320.5"}})
        result = validate_strategy_match(event)
        assert result.valid is True

    def test_limit_order_entry_price_invalid_string(self):
        event = _make_event({"data": {"entry_type": "LIMIT", "entry_price": "abc"}})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("entry_price" in e for e in result.errors)


class TestMissingData:
    def test_missing_data_field(self):
        event = {"type": "STRATEGY_MATCH", "symbol": "XAUUSD"}
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("data" in e for e in result.errors)

    def test_wrong_event_type(self):
        event = _make_event({"type": "SIGNAL_EVENT"})
        result = validate_strategy_match(event)
        assert result.valid is False
        assert any("STRATEGY_MATCH" in e for e in result.errors)
