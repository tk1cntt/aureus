import os
import sys
import unittest
from types import SimpleNamespace

import pandas as pd

# Ensure engine module can be imported when running from repository root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.strategies.base import BaseStrategy
from engine.strategies.registry import StrategyRegistry
from engine.strategies.template import TemplateStrategy


class _LegacyEvaluateStrategy(BaseStrategy):
    """Dummy strategy that only implements legacy evaluate(...) contract."""

    def __init__(self):
        super().__init__(name="LEGACY_DEMO", strategy_id=101, weight=1.5)

    def evaluate(self, df, signals, state):
        return {
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "direction": "BUY",
            "score": 8.2,
            "reason": "Legacy rule matched",
            "t": 1710000000,
        }


class _IncompatibleStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="INCOMPATIBLE_DEMO", strategy_id=202)
        self.spec_compatibility = ["v0"]

    def evaluate(self, df, signals, state):
        return None


class _MissingVersionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MISSING_VERSION", strategy_id=303)
        self.strategy_version = ""

    def evaluate(self, df, signals, state):
        return None


class _PhasedRejectStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="PHASED_REJECT", strategy_id=404)

    def evaluate(self, df, signals, state):
        return None

    def on_bar_close(self, context):
        return {
            "intent_id": "PHASED_REJECT:1",
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "direction": "BUY",
            "t": 1710000060,
            "origin_timestamp": 1710000060,
            "exit_config": {},
            "reason_code": "OK",
            "is_actionable": True,
        }

    def validate_entry(self, intent, context):
        return {
            "is_valid": False,
            "reason_code": "VALIDATION_RULE_FAILED",
            "failed_rules": ["RULE_A"],
            "evaluated_rules": [{"rule": "RULE_A", "passed": False}],
        }


class _OriginNoneStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="ORIGIN_NONE", strategy_id=606)

    def evaluate(self, df, signals, state):
        return None

    def on_bar_close(self, context):
        return {
            "intent_id": "ORIGIN_NONE:1",
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "direction": "BUY",
            "t": 1710000120,
            "origin_timestamp": None,
            "exit_config": {},
            "reason_code": "OK",
            "is_actionable": True,
        }


class _NonActionableSequenceStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="NON_ACTIONABLE_SEQUENCE", strategy_id=505)

    def evaluate(self, df, signals, state):
        return None

    def on_bar_close(self, context):
        return {
            "intent_id": "NON_ACTIONABLE_SEQUENCE:1",
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "direction": "BUY",
            "t": 1710000060,
            "origin_timestamp": 1710000060,
            "exit_config": {},
            "reason_code": "SEQUENCE_NOT_MATCHED",
            "is_actionable": False,
            "sequence_diagnostics": {
                "mismatch_reason": "MISSING_REQUIRED_STEP",
                "missing_required_tags": ["CHOCH_BULL"],
                "current_step_index": 0,
                "matched_steps": 0,
                "total_steps": 2,
            },
        }


class TestStrategyContractV1(unittest.TestCase):
    def test_base_strategy_exposes_required_metadata_fields(self):
        strategy = _LegacyEvaluateStrategy()

        self.assertTrue(hasattr(strategy, "strategy_id"))
        self.assertTrue(hasattr(strategy, "strategy_version"))
        self.assertTrue(hasattr(strategy, "spec_compatibility"))

        self.assertIsInstance(strategy.strategy_version, str)
        self.assertTrue(strategy.strategy_version)
        self.assertIsInstance(strategy.spec_compatibility, (list, tuple, set))
        self.assertGreaterEqual(len(strategy.spec_compatibility), 1)

    def test_legacy_evaluate_is_adapted_by_on_bar_close(self):
        strategy = _LegacyEvaluateStrategy()

        context = {
            "df": None,
            "signals": {},
            "state": {},
        }

        intent = strategy.on_bar_close(context)

        self.assertIsInstance(intent, dict)
        self.assertEqual(intent["strategy"], "LEGACY_DEMO")
        self.assertEqual(intent["strategy_id"], 101)
        self.assertEqual(intent["strategy_version"], strategy.strategy_version)
        self.assertIn("intent_id", intent)
        self.assertIn("legacy_result", intent)

    def test_validate_entry_returns_contract_shape(self):
        strategy = _LegacyEvaluateStrategy()

        valid = strategy.validate_entry({"intent_id": "LEGACY_DEMO:1"}, context={})
        rejected = strategy.validate_entry(None, context={})

        self.assertEqual(valid["is_valid"], True)
        self.assertEqual(valid["failed_rules"], [])
        self.assertEqual(valid["reason_code"], "OK")

        self.assertEqual(rejected["is_valid"], False)
        self.assertEqual(rejected["reason_code"], "NO_INTENT")
        self.assertIn("INTENT_MISSING", rejected["failed_rules"])

    def test_build_order_plan_returns_required_policy_fields(self):
        strategy = _LegacyEvaluateStrategy()

        intent = strategy.on_bar_close({"df": None, "signals": {}, "state": {}})
        order_plan = strategy.build_order_plan(intent, context={})

        self.assertIsInstance(order_plan, dict)
        self.assertEqual(order_plan["entry_type"], "MARKET")
        self.assertEqual(order_plan["entry_policy"], "IMMEDIATE")
        self.assertEqual(order_plan["direction"], "BUY")
        self.assertIn("size", order_plan)

    def test_template_strategy_emits_structured_phased_artifacts(self):
        strategy = TemplateStrategy(
            {
                "id": 7,
                "name": "TEMPLATE_DEMO",
                "min_score_threshold": 1.0,
                "sequence": [{"tag": "CHOCH_BULL", "weight": 2.0, "required": True}],
                "exit_config": {
                    "entry_type": "MARKET",
                    "entry_policy": "IMMEDIATE",
                    "sl": {"mode": "FIXED", "value": 15},
                    "tp": {"mode": "RR", "value": 2},
                    "trailing": {"mode": "ATR", "value": 1.2},
                    "expiry": 3,
                },
            }
        )

        state_obj = SimpleNamespace(signal_history=[{"tag": "CHOCH_BULL", "t": 1710000000}])
        df = pd.DataFrame([{"t": 1710000060, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}])
        context = {"df": df, "signals": {}, "state": state_obj, "backfill_status": "READY"}

        intent = strategy.on_bar_close(context)
        self.assertIsInstance(intent, dict)
        self.assertEqual(intent["reason_code"], "OK")
        self.assertEqual(intent["is_actionable"], True)
        self.assertIn("evaluated_rules", intent)
        self.assertIn("evidence_refs", intent)
        self.assertGreaterEqual(len(intent["evaluated_rules"]), 1)

        validation = strategy.validate_entry(intent, context)
        self.assertEqual(validation["is_valid"], True)
        self.assertEqual(validation["reason_code"], "OK")
        self.assertIn("evaluated_rules", validation)

        order_plan = strategy.build_order_plan(intent, context)
        self.assertEqual(order_plan["reason_code"], "OK")
        self.assertEqual(order_plan["entry_type"], "MARKET")
        self.assertEqual(order_plan["entry_policy"], "IMMEDIATE")
        self.assertIn("sl", order_plan)
        self.assertIn("tp", order_plan)
        self.assertIn("trailing", order_plan)
        self.assertIn("size", order_plan)
        self.assertIn("expiry", order_plan)

    def test_template_strategy_backfill_not_ready_returns_deterministic_reason(self):
        strategy = TemplateStrategy(
            {
                "id": 8,
                "name": "TEMPLATE_BACKFILL_GATE",
                "min_score_threshold": 1.0,
                "sequence": [{"tag": "CHOCH_BULL", "weight": 1.0, "required": True}],
            }
        )

        state_obj = SimpleNamespace(signal_history=[{"tag": "CHOCH_BULL", "t": 1710000000}])
        df = pd.DataFrame([{"t": 1710000060, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}])
        context = {"df": df, "signals": {}, "state": state_obj, "backfill_status": "WARMING"}

        intent = strategy.on_bar_close(context)
        self.assertIsInstance(intent, dict)
        self.assertEqual(intent["reason_code"], "BACKFILL_NOT_READY")
        self.assertEqual(intent["is_actionable"], False)

        validation = strategy.validate_entry(intent, context)
        self.assertEqual(validation["is_valid"], False)
        self.assertEqual(validation["reason_code"], "BACKFILL_NOT_READY")
        self.assertIn("BACKFILL_NOT_READY", validation["failed_rules"])

    def test_registry_fail_fast_rejects_incompatible_strategy(self):
        registry = StrategyRegistry(active_spec_version="v1")
        accepted = registry.register(_IncompatibleStrategy())

        self.assertFalse(accepted)
        self.assertEqual(registry.list_strategies(), [])

        rejections = registry.get_rejections()
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["phase"], "register")
        self.assertEqual(rejections[0]["reason_code"], "SPEC_VERSION_INCOMPATIBLE")

    def test_registry_fail_fast_rejects_missing_strategy_version(self):
        registry = StrategyRegistry(active_spec_version="v1")
        accepted = registry.register(_MissingVersionStrategy())

        self.assertFalse(accepted)
        rejections = registry.get_rejections()
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["reason_code"], "INVALID_STRATEGY_VERSION")

    def test_registry_evaluate_all_returns_only_accepted_and_buffers_phase_rejections(self):
        registry = StrategyRegistry(active_spec_version="v1")
        registry.register(_LegacyEvaluateStrategy())
        registry.register(_PhasedRejectStrategy())

        state_obj = SimpleNamespace(signal_history=[{"tag": "CHOCH_BULL", "t": 1710000000}])
        df = pd.DataFrame([{"t": 1710000060, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}])

        accepted = registry.evaluate_all(df=df, signals={}, state_obj=state_obj)

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["strategy"], "LEGACY_DEMO")
        self.assertEqual(accepted[0]["reason_code"], "OK")

        rejections = registry.get_rejections()
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["strategy"], "PHASED_REJECT")
        self.assertEqual(rejections[0]["phase"], "validate_entry")
        self.assertEqual(rejections[0]["reason_code"], "VALIDATION_RULE_FAILED")

    def test_registry_evaluate_all_falls_back_origin_timestamp_when_intent_origin_is_none(self):
        registry = StrategyRegistry(active_spec_version="v1")
        registry.register(_OriginNoneStrategy())

        state_obj = SimpleNamespace(signal_history=[])
        df = pd.DataFrame([{"t": 1710000120, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}])

        accepted = registry.evaluate_all(df=df, signals={}, state_obj=state_obj)

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["strategy"], "ORIGIN_NONE")
        self.assertEqual(accepted[0]["origin_timestamp"], 1710000120)

    def test_registry_on_bar_close_rejection_includes_symbol_and_sequence_summary(self):
        registry = StrategyRegistry(active_spec_version="v1")
        registry.register(_NonActionableSequenceStrategy())

        state_obj = SimpleNamespace(symbol="XAUUSD", signal_history=[])
        df = pd.DataFrame([{"t": 1710000060, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}])

        accepted = registry.evaluate_all(df=df, signals={}, state_obj=state_obj)
        self.assertEqual(accepted, [])

        rejections = registry.get_rejections()
        self.assertEqual(len(rejections), 1)
        rejection = rejections[0]
        self.assertEqual(rejection["strategy"], "NON_ACTIONABLE_SEQUENCE")
        self.assertEqual(rejection["phase"], "on_bar_close")
        self.assertEqual(rejection["reason_code"], "SEQUENCE_NOT_MATCHED")
        self.assertEqual(rejection["details"]["symbol"], "XAUUSD")
        self.assertEqual(
            rejection["details"]["sequence_diagnostics_summary"]["mismatch_reason"],
            "MISSING_REQUIRED_STEP",
        )
        self.assertEqual(
            rejection["details"]["sequence_diagnostics_summary"]["missing_required_tags"],
            ["CHOCH_BULL"],
        )
        self.assertNotIn("evaluated_rules", rejection["details"])
        self.assertNotIn("evidence_refs", rejection["details"])

    def test_registry_accepts_template_strategy_with_out_of_order_normalized_records(self):
        registry = StrategyRegistry(active_spec_version="v1")
        registry.register(
            TemplateStrategy(
                {
                    "id": 909,
                    "name": "TEMPLATE_SORTED_ACCEPTED",
                    "min_score_threshold": 2.0,
                    "sequence": [
                        {"tag": "STEP1", "weight": 1.0, "required": True},
                        {"tag": "STEP2", "weight": 1.0, "required": True},
                    ],
                    "exit_config": {"tp": 120},
                }
            )
        )

        state_obj = SimpleNamespace(
            symbol="XAUUSD",
            signal_history=[{"tag": "WRONG_HISTORY_TAG", "t": 1710000000}],
            log_signal_normalize=[
                {"t": 1710000060, "signals": {"events": [{"tag": "STEP2"}]}},
                {"t": 1710000000, "signals": {"events": [{"tag": "STEP1"}]}},
            ],
            strategy_progress={},
        )
        df = pd.DataFrame([{"t": 1710000060, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}])

        accepted = registry.evaluate_all(df=df, signals={}, state_obj=state_obj)

        self.assertEqual(len(accepted), 1)
        result = accepted[0]
        self.assertEqual(result["strategy"], "TEMPLATE_SORTED_ACCEPTED")
        self.assertEqual(result["strategy_id"], 909)
        self.assertEqual(result["reason_code"], "OK")
        self.assertEqual(result["t"], 1710000060)
        self.assertEqual(result["origin_timestamp"], 1710000000)
        self.assertEqual(result["side"], "BUY")
        self.assertEqual(result["entry_type"], "MARKET")
        self.assertEqual(result["entry_policy"], "IMMEDIATE")

        intent = result["intent"]
        self.assertEqual(intent["reason_code"], "OK")
        self.assertEqual(intent["sequence_diagnostics"]["matched_steps"], 2)
        self.assertEqual(intent["sequence_diagnostics"]["missing_required"], False)

        progress = state_obj.strategy_progress["TEMPLATE_SORTED_ACCEPTED"]
        self.assertEqual(progress["origin_timestamp"], 1710000000)
        self.assertEqual(progress["sequence"][0]["time"], 1710000000)
        self.assertEqual(progress["sequence"][1]["time"], 1710000060)

        self.assertEqual(registry.get_rejections(), [])


if __name__ == "__main__":
    unittest.main()
