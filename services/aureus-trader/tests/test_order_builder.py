"""
Unit tests for order_builder.py
"""
import re
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from order_builder import build_order_command, generate_cmd_id


def _make_match_event(overrides=None):
    """Helper to create a valid STRATEGY_MATCH event."""
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


class TestBuildOrderCommand:
    def test_build_market_order(self):
        event = _make_match_event()
        cmd = build_order_command(event)

        assert cmd["type"] == "OPEN_ORDER"
        assert cmd["symbol"] == "XAUUSD"
        assert cmd["direction"] == "BUY"
        assert cmd["order_type"] == "MARKET"
        assert cmd["volume"] == 0.1
        assert cmd["price"] == 0
        assert cmd["sl"] == 2300.0
        assert cmd["tp"] == 2350.0
        assert cmd["magic"] == 10001
        assert cmd["comment"] == "CHOCH_UP"
        assert cmd["cmd_id"].startswith("ord-")

    def test_build_limit_order(self):
        event = _make_match_event(
            {
                "data": {
                    "entry_type": "LIMIT",
                    "entry_price": 2320.5,
                    "size_value": 0.05,
                }
            }
        )
        cmd = build_order_command(event)

        assert cmd["order_type"] == "LIMIT"
        assert cmd["price"] == 2320.5
        assert cmd["volume"] == 0.05

    def test_build_stop_order(self):
        event = _make_match_event(
            {
                "data": {
                    "entry_type": "STOP",
                    "entry_price": 2330.0,
                    "direction": "SELL",
                }
            }
        )
        cmd = build_order_command(event)

        assert cmd["order_type"] == "STOP"
        assert cmd["direction"] == "SELL"
        assert cmd["price"] == 2330.0

    def test_required_keys_present(self):
        event = _make_match_event()
        cmd = build_order_command(event)
        required_keys = {
            "type", "symbol", "cmd_id", "direction", "order_type",
            "volume", "price", "sl", "tp", "magic", "comment",
        }
        assert required_keys.issubset(set(cmd.keys()))


class TestGenerateCmdId:
    def test_cmd_id_format(self):
        data = {
            "strategy_id": "TEST",
            "symbol": "XAUUSD",
            "signal_ts": 1234567890,
            "direction": "BUY",
        }
        cmd_id = generate_cmd_id(data)
        assert re.match(r"^ord-[0-9a-f]{12}$", cmd_id), f"Bad format: {cmd_id}"

    def test_cmd_id_deterministic(self):
        data = {
            "strategy_id": "CHOCH_UP",
            "symbol": "XAUUSD",
            "signal_ts": 1712376000000,
            "direction": "BUY",
        }
        id1 = generate_cmd_id(data)
        id2 = generate_cmd_id(data)
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        data1 = {
            "strategy_id": "CHOCH_UP",
            "symbol": "XAUUSD",
            "signal_ts": 1712376000000,
            "direction": "BUY",
        }
        data2 = {
            "strategy_id": "CHOCH_UP",
            "symbol": "XAUUSD",
            "signal_ts": 1712376000001,
            "direction": "BUY",
        }
        assert generate_cmd_id(data1) != generate_cmd_id(data2)

    def test_cmd_id_uses_t_fallback(self):
        data = {
            "strategy_id": "TEST",
            "direction": "SELL",
            "t": 9999999,
        }
        cmd_id = generate_cmd_id(data)
        assert cmd_id.startswith("ord-")
        assert len(cmd_id) == 16  # ord- + 12 hex chars
