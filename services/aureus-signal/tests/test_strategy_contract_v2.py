"""
tests/test_strategy_contract_v2.py — Phase 26 strategy contract v2 tests

Covers:
- entry_type enum validation
- size_value + size_mode normalization
- magic_number per strategy
- Backward compatibility
"""
import os
import sys
import pytest

# Ensure engine module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.snapshot_utils import VALID_ENTRY_TYPES, VALID_SIZE_MODES
from engine.strategies.base import BaseStrategy
from engine.strategies.template import TemplateStrategy


# --- Concrete Strategy for testing BaseStrategy ---

class ConcreteStrategy(BaseStrategy):
    def evaluate(self, df, signals, state):
        return {"direction": "BUY", "t": 100}


class TestEntryTypeEnum:
    """Verify entry_type enum constants and defaults."""

    def test_valid_entry_types_contains_expected(self):
        assert "MARKET" in VALID_ENTRY_TYPES
        assert "LIMIT" in VALID_ENTRY_TYPES
        assert "STOP" in VALID_ENTRY_TYPES

    def test_base_strategy_default_entry_type(self):
        strat = ConcreteStrategy("test-strat", strategy_id=1)
        intent = {"intent_id": "test:1:100", "direction": "BUY"}
        plan = strat.build_order_plan(intent, {})
        assert plan["entry_type"] == "MARKET"

    def test_template_strategy_reads_entry_type_from_trade_execution(self):
        config = {
            "name": "test-template",
            "id": 10,
            "trade_execution": {"entry_type": "LIMIT"},
        }
        strat = TemplateStrategy(config)
        intent = {"intent_id": "test:10:100", "direction": "BUY", "reason_code": "OK"}
        plan = strat.build_order_plan(intent, {})
        assert plan["entry_type"] == "LIMIT"

    def test_template_strategy_invalid_entry_type_defaults_to_market(self):
        config = {
            "name": "test-template",
            "id": 10,
            "trade_execution": {"entry_type": "INVALID_TYPE"},
        }
        strat = TemplateStrategy(config)
        intent = {"intent_id": "test:10:100", "direction": "BUY", "reason_code": "OK"}
        plan = strat.build_order_plan(intent, {})
        assert plan["entry_type"] == "MARKET"


class TestSizeNormalization:
    """Verify size_value + size_mode normalization."""

    def test_valid_size_modes_contains_expected(self):
        assert "FIXED_UNITS" in VALID_SIZE_MODES
        assert "FIXED_LOT" in VALID_SIZE_MODES
        assert "RISK_PERCENT" in VALID_SIZE_MODES

    def test_base_strategy_emits_size_value_and_size_mode(self):
        strat = ConcreteStrategy("test-strat", strategy_id=1)
        intent = {"intent_id": "test:1:100", "direction": "BUY"}
        plan = strat.build_order_plan(intent, {})
        assert plan["size_value"] == 1.0
        assert plan["size_mode"] == "FIXED_UNITS"
        # Legacy key still present
        assert plan["size"] == 1.0

    def test_template_strategy_reads_size_mode_from_trade_execution(self):
        config = {
            "name": "test-template",
            "id": 10,
            "trade_execution": {"size_value": 0.5, "size_mode": "RISK_PERCENT"},
        }
        strat = TemplateStrategy(config)
        intent = {"intent_id": "test:10:100", "direction": "BUY", "reason_code": "OK"}
        plan = strat.build_order_plan(intent, {})
        assert plan["size_value"] == 0.5
        assert plan["size_mode"] == "RISK_PERCENT"
        assert plan["size"] == 0.5  # legacy compat

    def test_template_strategy_invalid_size_mode_defaults(self):
        config = {
            "name": "test-template",
            "id": 10,
            "trade_execution": {"size_mode": "BAD_MODE"},
        }
        strat = TemplateStrategy(config)
        intent = {"intent_id": "test:10:100", "direction": "BUY", "reason_code": "OK"}
        plan = strat.build_order_plan(intent, {})
        assert plan["size_mode"] == "FIXED_UNITS"


class TestMagicNumber:
    """Verify magic_number per strategy."""

    def test_base_strategy_magic_number_default(self):
        strat = ConcreteStrategy("test-strat", strategy_id=1)
        assert strat.magic_number == 0

    def test_template_strategy_reads_magic_number_from_config(self):
        config = {"name": "test-template", "id": 10, "magic_number": 12345}
        strat = TemplateStrategy(config)
        assert strat.magic_number == 12345

    def test_template_strategy_default_magic_number(self):
        config = {"name": "test-template", "id": 10}
        strat = TemplateStrategy(config)
        assert strat.magic_number == 10000  # strategy_id * 1000

    def test_order_plan_includes_magic_number(self):
        config = {"name": "test-template", "id": 10, "magic_number": 99999}
        strat = TemplateStrategy(config)
        intent = {"intent_id": "test:10:100", "direction": "BUY", "reason_code": "OK"}
        plan = strat.build_order_plan(intent, {})
        assert plan["magic_number"] == 99999

    def test_base_strategy_order_plan_includes_magic_number(self):
        strat = ConcreteStrategy("test-strat", strategy_id=5)
        intent = {"intent_id": "test:5:100", "direction": "BUY"}
        plan = strat.build_order_plan(intent, {})
        assert plan["magic_number"] == 0


class TestBackwardCompatibility:
    """Verify existing keys still present in order plan."""

    def test_order_plan_has_legacy_keys(self):
        strat = ConcreteStrategy("test-strat", strategy_id=1)
        intent = {"intent_id": "test:1:100", "direction": "BUY"}
        plan = strat.build_order_plan(intent, {})
        # All legacy keys must still be present
        assert "size" in plan
        assert "entry_type" in plan
        assert "entry_policy" in plan
        assert "sl" in plan
        assert "tp" in plan
        assert "trailing" in plan
        assert "expiry" in plan

    def test_template_strategy_order_plan_has_legacy_keys(self):
        config = {"name": "test-template", "id": 10}
        strat = TemplateStrategy(config)
        intent = {"intent_id": "test:10:100", "direction": "BUY", "reason_code": "OK"}
        plan = strat.build_order_plan(intent, {})
        assert "size" in plan
        assert "entry_type" in plan
        assert "entry_policy" in plan
        assert "sl" in plan
        assert "tp" in plan
