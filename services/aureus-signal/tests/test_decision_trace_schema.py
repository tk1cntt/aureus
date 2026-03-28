import os
import sys
import unittest

# Ensure engine module can be imported when running from repository root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.snapshot_utils import (
    ENGINE_VERSION,
    SPEC_VERSION,
    DecisionTraceValidationError,
    build_decision_trace,
    validate_decision_trace,
)
from engine.orders import SimulatedTradeManager
from engine.state import SymbolState


class TestDecisionTraceSchema(unittest.TestCase):
    def _base_context(self):
        return {
            "trace_id": "trace-001",
            "decision_timestamp": "2026-03-20T07:00:00Z",
            "symbol": "XAUUSD",
            "timeframe": "M1",
            "strategy_id": "S1_CHOCH_OB_RETEST_TREND",
            "strategy_version": "1.0.0",
            "correlation_id": "corr-001",
            "market_snapshot": {
                "bar_timestamp": 1710000000,
                "bar_ohlcv": {"o": 1.0, "h": 2.0, "l": 0.5, "c": 1.8, "v": 1000},
                "spread": 0.2,
                "session_label": "LONDON",
                "backfill_status": "READY",
                "data_window_start": 1709999400,
                "data_window_end": 1710000000,
                "data_window_hash": "window-hash-001",
            },
            "signals": {
                "zigzag_state": {"value": "UP"},
                "ob_state": {"value": "VALID"},
                "choch_state": {"value": "CONFIRMED"},
                "fvg_state": {"value": "PRESENT"},
                "trend_filter_state": {"value": "BULLISH"},
            },
            "evaluated_rules": [
                {
                    "rule_id": "R_CONFIRM_STRUCTURE",
                    "result": "PASS",
                    "reason_code": "OK",
                    "evidence_refs": ["signals.choch_state.value"],
                }
            ],
            "flow_integrity": {
                "current_state": "INTENT",
                "next_state": "VALIDATED",
                "transition_allowed": True,
                "validator_passed": True,
                "validator_failures": [],
            },
        }

    def test_build_and_validate_rejected_trace(self):
        context = self._base_context()
        context["decision_status"] = "REJECTED"
        context["evaluated_rules"] = [
            {
                "rule_id": "R_BACKFILL_READY",
                "result": "FAIL",
                "reason_code": "BACKFILL_NOT_READY",
                "evidence_refs": ["market_snapshot.backfill_status"],
            }
        ]

        trace = build_decision_trace(context)
        validate_decision_trace(trace)

        self.assertEqual(trace["spec_version"], SPEC_VERSION)
        self.assertEqual(trace["engine_version"], ENGINE_VERSION)
        self.assertEqual(trace["decision_status"], "REJECTED")
        self.assertIn("market_snapshot", trace)
        self.assertIn("signals", trace)
        self.assertIn("flow_integrity", trace)

    def test_accepted_trace_requires_order_plan(self):
        context = self._base_context()
        context["decision_status"] = "ACCEPTED"

        trace = build_decision_trace(context)

        with self.assertRaises(DecisionTraceValidationError):
            validate_decision_trace(trace)

    def test_build_and_validate_accepted_trace_with_order_plan(self):
        context = self._base_context()
        context["decision_status"] = "ACCEPTED"
        context["order_plan_snapshot"] = {
            "entry_type": "MARKET",
            "entry_policy": "IMMEDIATE",
            "sl_mode": "PRICE",
            "sl_value": 2298.5,
            "tp_mode": "RR",
            "tp_value": 2.0,
            "trailing_mode": "NONE",
            "trailing_value": 0.0,
            "size_mode": "FIXED_RISK",
            "size_value": 0.01,
            "expiry_policy": "BAR_CLOSE",
        }

        trace = build_decision_trace(context)
        self.assertTrue(validate_decision_trace(trace))

    def test_rejected_trace_requires_at_least_one_fail_rule(self):
        context = self._base_context()
        context["decision_status"] = "REJECTED"
        context["evaluated_rules"] = [
            {
                "rule_id": "R_CONFIRM_STRUCTURE",
                "result": "PASS",
                "reason_code": "OK",
                "evidence_refs": ["signals.choch_state.value"],
            }
        ]

        trace = build_decision_trace(context)

        with self.assertRaises(DecisionTraceValidationError):
            validate_decision_trace(trace)




class _FakeRedis:
    def __init__(self):
        self.members = set()
        self.stream_events = []

    async def sismember(self, key, value):
        return (key, value) in self.members

    async def sadd(self, key, value):
        self.members.add((key, value))

    async def xadd(self, key, payload):
        self.stream_events.append((key, payload))


class TestPhase10OrderAndStatePersistence(unittest.IsolatedAsyncioTestCase):
    async def test_process_triggers_persists_rejection_for_incomplete_order_plan(self):
        fake_redis = _FakeRedis()
        manager = SimulatedTradeManager(fake_redis)
        state = SymbolState("XAUUSD")
        state.last_candle = {"t": 1710000060, "c": 2300.0, "h": 2301.0, "l": 2299.0}

        triggers = [
            {
                "strategy": "S1_CHOCH_OB_RETEST_TREND",
                "strategy_id": "S1",
                "origin_timestamp": 1710000000,
                "order_plan": {
                    "entry_type": "MARKET",
                    "entry_policy": "IMMEDIATE",
                    "size_mode": "FIXED_UNITS",
                    # missing `size` + full sl/tp blocks on purpose
                },
            }
        ]

        await manager.process_triggers("XAUUSD", triggers, state)

        self.assertEqual(len(state.order_rejections), 1)
        rejection = state.order_rejections[0]
        self.assertEqual(rejection["reason_code"], "ORDER_PLAN_INCOMPLETE")
        self.assertIn("size_value", rejection["missing_order_plan_keys"])
        self.assertNotIn("sl_value", rejection["missing_order_plan_keys"])
        self.assertNotIn("tp_value", rejection["missing_order_plan_keys"])
        self.assertEqual(len(state.simulated_orders), 0)
        self.assertEqual(len(fake_redis.stream_events), 1)
        self.assertEqual(fake_redis.stream_events[0][1]["type"], "ORDER_REJECTED")

    def test_symbol_state_ledgers_are_bounded_and_serializable(self):
        state = SymbolState("XAUUSD")

        for idx in range(505):
            state.record_strategy_transition(
                strategy_id="S1",
                current_state="INTENT",
                next_state="VALIDATED",
                transition_allowed=True,
                validator_passed=(idx % 2 == 0),
                validator_failures=[] if idx % 2 == 0 else ["RULE_FAIL"],
                timestamp=1710000000 + idx,
            )
            state.record_validator_failure(
                strategy_id="S1",
                reason_code="VALIDATOR_FAILED",
                failures=["RULE_FAIL"],
                timestamp=1710000000 + idx,
            )
            state.record_order_rejection(
                {
                    "trace_id": f"trace-{idx}",
                    "reason_code": "ORDER_PLAN_INCOMPLETE",
                    "t": 1710000000 + idx,
                }
            )

        payload = state.to_dict()

        self.assertEqual(len(payload["strategy_transition_history"]), 500)
        self.assertEqual(len(payload["strategy_validator_failures"]), 500)
        self.assertEqual(len(payload["order_rejections"]), 500)
        self.assertEqual(payload["strategy_transition_history"][0]["t"], 1710000005)
        self.assertEqual(payload["order_rejections"][0]["trace_id"], "trace-5")
        self.assertEqual(payload["strategy_lifecycle_state"]["S1"]["current_state"], "VALIDATED")

        restored = SymbolState("XAUUSD")
        restored.from_dict(payload)
        self.assertEqual(len(restored.order_rejections), 500)
        self.assertEqual(len(restored.strategy_transition_history), 500)
        self.assertEqual(restored.strategy_last_transition["S1"]["t"], 1710000504)

    def test_symbol_state_signal_history_dual_contract_serialization(self):
        state = SymbolState("XAUUSD")
        t_older = 1710000500
        t_newer = 1710000600

        state.log_signal("market_session", t_older, value="ASIA", data={"window": "OPEN"})
        state.log_signal("market_session", t_older, value="LONDON", data={"window": "OPEN"})

        state.log_signal("ema_50_up", t_newer, value=2312.25, data={"slope": "UP"})
        state.log_signal("ema_50_up", t_newer, value=2313.0, data={"slope": "FLAT"})
        state.log_signal("htf_trend", t_newer, value="BEARISH", data={"timeframe": "H1"})
        state.log_signal("atr_14", t_newer, value=4.003302)
        state.log_signal("zigzag", t_newer, value="ll", data={"price": 0.68956})
        state.log_signal(
            "choch",
            t_newer,
            value="down",
            data={
                "direction": "down",
                "price": 0.68963,
                "breakout_t": t_newer,
                "pivot_t": t_older,
                "ob": {"type": "bearish_ob"},
            },
        )

        payload = state.to_dict()

        # Legacy/raw contract remains available
        self.assertIn("signal_history", payload)
        self.assertEqual(len(payload["signal_history"]), 8)

        # New normalized contract is available for grouped consumers
        self.assertIn("signal_history_normalized", payload)
        normalized = payload["signal_history_normalized"]
        self.assertEqual(len(normalized), 2)

        # Must be sorted ascending by timestamp
        self.assertEqual(normalized[0]["t"], t_older)
        self.assertEqual(normalized[1]["t"], t_newer)
        self.assertNotIn("price", normalized[0])
        self.assertNotIn("price", normalized[1])

        older_signals = normalized[0]["signals"]
        self.assertEqual(older_signals["market_session"]["value"], "LONDON")
        self.assertEqual(older_signals["market_session"]["window"], "OPEN")

        newer_signals = normalized[1]["signals"]
        self.assertEqual(newer_signals["ema"]["ema_50"]["direction"], "up")
        self.assertEqual(newer_signals["ema"]["ema_50"]["value"], 2313.0)
        self.assertEqual(newer_signals["ema"]["ema_50"]["slope"], "FLAT")
        self.assertEqual(newer_signals["htf_trend"]["value"], "BEARISH")
        self.assertEqual(newer_signals["htf_trend"]["timeframe"], "H1")
        self.assertEqual(newer_signals["atr_14"], 4.003302)
        self.assertEqual(newer_signals["zigzag"]["kind"], "ll")
        self.assertEqual(newer_signals["zigzag"]["price"], 0.68956)

        self.assertEqual(len(newer_signals["events"]), 1)
        event = newer_signals["events"][0]
        self.assertEqual(event["tag"], "choch")
        self.assertEqual(event["direction"], "down")
        self.assertEqual(event["price"], 0.68963)
        self.assertEqual(event["breakout_t"], t_newer)
        self.assertEqual(event["pivot_t"], t_older)
        self.assertEqual(event["ob"]["type"], "bearish_ob")

    def test_symbol_state_to_dict_handles_none_timestamp_in_raw_signal_history(self):
        state = SymbolState("XAUUSD")
        state.signal_history.append({"tag": "ema_20_up", "t": None, "value": 2300.0})
        state.log_signal("ema_20_up", 1710000600, value=2301.0)

        payload = state.to_dict()

        self.assertEqual(len(payload["signal_history"]), 2)
        self.assertEqual(payload["signal_history"][0]["t"], 1710000600)
        self.assertIsNone(payload["signal_history"][1].get("t"))

        normalized = payload["signal_history_normalized"]
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["t"], 1710000600)



if __name__ == "__main__":
    unittest.main()

