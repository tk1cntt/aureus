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
        assert "signal_snapshot" not in cmd
        assert "score_breakdown" not in cmd
        assert "weights_snapshot" not in cmd
        assert "missing_data_policy" not in cmd
        assert "score_version" not in cmd
        assert "signal_schema_version" not in cmd
        assert "trace_id" not in cmd
        assert set(cmd.keys()) == {
            "type", "symbol", "cmd_id", "direction", "order_type",
            "volume", "price", "sl", "tp", "magic", "comment",
        }

    def test_omit_signal_snapshot_and_scoring_payload_fields(self):
        event = _make_match_event(
            {
                "data": {
                    "signal_snapshot": {"atr": 2.5, "ema_21": 3345.12},
                    "score_total": 0.812345,
                    "score_breakdown": {"criteria": [{"name": "signal_quality", "normalized": 0.8}]},
                    "weights_snapshot": {"signal_quality": 0.30},
                    "missing_data_policy": "impute_neutral_and_flag",
                    "score_version": "scor-v1.0.0",
                    "signal_schema_version": "sig-v2.0.0",
                    "trace_id": "trace-123",
                }
            }
        )

        cmd = build_order_command(event)

        assert "signal_snapshot" not in cmd
        assert "score_total" not in cmd
        assert "score_breakdown" not in cmd
        assert "weights_snapshot" not in cmd
        assert "missing_data_policy" not in cmd
        assert "score_version" not in cmd
        assert "signal_schema_version" not in cmd
        assert cmd["trace_id"] == "trace-123"

    def test_forward_top_level_trace_id(self):
        event = _make_match_event({"trace_id": "trace-top-level"})

        cmd = build_order_command(event)

        assert cmd["trace_id"] == "trace-top-level"

    def test_forward_conditional_execution_fields_when_present(self):
        event = _make_match_event(
            {
                "data": {
                    "tp_rr_ratio": 2.0,
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "risk_amount": 75.0,
                }
            }
        )

        cmd = build_order_command(event)

        assert cmd["tp_rr_ratio"] == 2.0
        assert cmd["size_mode"] == "RISK_FIXED_AMOUNT"
        assert cmd["risk_amount"] == 75.0
        assert cmd["volume"] == 0

    def test_do_not_forward_size_mode_when_not_risk_fixed_amount(self):
        event = _make_match_event(
            {
                "data": {
                    "size_mode": "FIXED_LOT",
                    "risk_amount": 99.0,
                }
            }
        )

        cmd = build_order_command(event)

        assert "size_mode" not in cmd
        assert "risk_amount" not in cmd

    def test_fallback_default_risk_budget_for_risk_fixed_amount(self, monkeypatch):
        monkeypatch.setenv("RISK_FIXED_AMOUNT_BUDGET", "55")
        event = _make_match_event(
            {
                "data": {
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "risk_amount": None,
                }
            }
        )

        cmd = build_order_command(event)

        assert cmd["size_mode"] == "RISK_FIXED_AMOUNT"
        assert cmd["risk_amount"] == 55.0
        assert cmd["volume"] == 0

    def test_ignore_invalid_tp_rr_ratio(self):
        event = _make_match_event({"data": {"tp_rr_ratio": "bad-value"}})

        cmd = build_order_command(event)

        assert "tp_rr_ratio" not in cmd

    def test_reject_object_sl_before_mt5_dispatch(self):
        event = _make_match_event({"data": {"sl_absolute": None, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}}})

        with pytest.raises(ValueError, match="sl must be numeric"):
            build_order_command(event)

    def test_reject_object_tp_before_mt5_dispatch(self):
        event = _make_match_event({"data": {"tp_absolute": None, "tp": {"type": "RR_RATIO", "value": 1.5}}})

        with pytest.raises(ValueError, match="tp must be numeric"):
            build_order_command(event)

    def test_numeric_absolute_sl_tp_still_pass_through(self):
        event = _make_match_event({"data": {"sl_absolute": 80590.94, "tp_absolute": 79377.85}})

        cmd = build_order_command(event)

        assert cmd["sl"] == 80590.94
        assert cmd["tp"] == 79377.85

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
