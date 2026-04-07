"""Determinism tests for seed strategies.

Verifies that two independent runs on identical data produce identical results:
same reason_code, score, is_actionable, and rejection lists.

Based on the _o1 parity test pattern from test_atr_o1.py.
No DB, no Redis — pure unit tests.
"""
import sys
import os
import copy
import unittest
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.strategies.template import TemplateStrategy
from engine.strategies.registry import StrategyRegistry


# ---------------------------------------------------------------------------
# Seed strategy configs (same as test_strategy_context_filters.py)
# ---------------------------------------------------------------------------

TREND_CONT_CONFIG = {
    "name": "TREND_CONT",
    "id": 1,
    "min_score_threshold": 6.5,
    "context_filters": [
        {"type": "trend_alignment", "required_trend": "BULLISH"},
        {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]},
        {"type": "ema_alignment", "required_slope": "POSITIVE", "period": 21},
    ],
    "sequence": [
        {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
        {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 15, "reset_signals": ["choch_down"]},
        {"tag": "fvg_bull", "weight": 2.0, "required": False, "max_wait": 10},
    ],
    "trade_execution": {
        "direction": "BUY",
        "size": 2.0,
        "sl": {"type": "FIXED_PIPS", "value": 15},
        "tp": {"type": "RR_RATIO", "value": 3.0},
    },
}

SESSION_SWEEP_CONFIG = {
    "name": "SESSION_SWEEP",
    "id": 2,
    "min_score_threshold": 6.0,
    "context_filters": [
        {"type": "trend_alignment", "required_trend": "BULLISH"},
        {"type": "session_active", "allowed": ["LONDON", "NEW_YORK"]},
    ],
    "sequence": [
        {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
        {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]},
    ],
    "trade_execution": {
        "direction": "BUY",
        "size": 1.5,
        "sl": {"type": "FIXED_PIPS", "value": 10},
        "tp": {"type": "RR_RATIO", "value": 2.5},
    },
}

ORDER_FLOW_DOM_CONFIG = {
    "name": "ORDER_FLOW_DOM",
    "id": 3,
    "min_score_threshold": 7.0,
    "context_filters": [
        {"type": "trend_alignment", "required_trend": "BULLISH"},
        {"type": "ob_imbalance", "min_ratio": 3.0, "lookback": 10},
        {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]},
    ],
    "sequence": [
        {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
    ],
    "trade_execution": {
        "direction": "BUY",
        "size": 3.0,
        "sl": {"type": "FIXED_PIPS", "value": 12},
        "tp": {"type": "RR_RATIO", "value": 4.0},
    },
}


class MockState:
    def __init__(self):
        self.htf_trend = "BULLISH"
        self.current_session = "LONDON"
        self.obs = [{"ob_type": "BULLISH", "top": 100, "bottom": 99, "t_start": 1}] * 4 + \
                   [{"ob_type": "BEARISH", "top": 100, "bottom": 99, "t_start": 1}]
        self.emas = {21: {"slope": 0.5}}
        self.signal_history = []
        self.log_signal_normalize = []
        self.strategy_progress = {}
        self.last_candle = {"t": 1000, "o": 100, "h": 105, "l": 99, "c": 103}
        self.atr = 5.0
        self.market_regime = "SIDEWAYS"


def _create_mock_df(t_val=1000):
    return pd.DataFrame([{
        "t": t_val, "o": 100.0, "h": 105.0, "l": 99.0, "c": 103.0, "v": 1000
    }])


def _make_bullish_signal_history():
    """Return event list used to build normalized strategy inputs."""
    return [
        {"tag": "choch_up", "t": 900},
        {"tag": "sweep_bull", "t": 960},
        {"tag": "fvg_bull", "t": 980},
    ]


def _to_normalized_records(events):
    grouped = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        tag = ev.get("tag")
        t_val = ev.get("t")
        if tag is None or t_val is None:
            continue
        key = int(t_val)
        if key not in grouped:
            grouped[key] = {
                "t": key,
                "signals": {"events": []},
            }
        grouped[key]["signals"]["events"].append({"tag": str(tag)})
    return [grouped[k] for k in sorted(grouped.keys())]


class TestTrendContDeterminism(unittest.TestCase):
    """Two independent TREND_CONT runs on identical data must produce identical results."""

    def test_determinism_with_matching_sequence(self):
        signal_history = _make_bullish_signal_history()
        normalized_log = _to_normalized_records(signal_history)

        # Run A
        strat_a = TemplateStrategy(copy.deepcopy(TREND_CONT_CONFIG))
        state_a = MockState()
        state_a.log_signal_normalize = copy.deepcopy(normalized_log)
        context_a = {"df": _create_mock_df(1000), "state": state_a, "backfill_status": "READY"}
        intent_a = strat_a.on_bar_close(context_a)

        # Run B (independent instance)
        strat_b = TemplateStrategy(copy.deepcopy(TREND_CONT_CONFIG))
        state_b = MockState()
        state_b.log_signal_normalize = copy.deepcopy(normalized_log)
        context_b = {"df": _create_mock_df(1000), "state": state_b, "backfill_status": "READY"}
        intent_b = strat_b.on_bar_close(context_b)

        self.assertEqual(intent_a["reason_code"], intent_b["reason_code"])
        self.assertEqual(intent_a["score"], intent_b["score"])
        self.assertEqual(intent_a["is_actionable"], intent_b["is_actionable"])

    def test_determinism_with_context_filter_fail(self):
        signal_history = _make_bullish_signal_history()
        normalized_log = _to_normalized_records(signal_history)

        # Both runs have BEARISH trend → context fails
        for _ in range(2):
            strat = TemplateStrategy(copy.deepcopy(TREND_CONT_CONFIG))
            state = MockState()
            state.htf_trend = "BEARISH"
            state.log_signal_normalize = copy.deepcopy(normalized_log)
            context = {"df": _create_mock_df(1000), "state": state, "backfill_status": "READY"}
            intent = strat.on_bar_close(context)
            self.assertEqual(intent["reason_code"], "CONTEXT_FILTER_FAILED")
            self.assertFalse(intent["is_actionable"])


class TestSessionSweepDeterminism(unittest.TestCase):
    def test_determinism(self):
        signal_history = [
            {"tag": "choch_up", "t": 900},
            {"tag": "sweep_bull", "t": 960},
        ]
        normalized_log = _to_normalized_records(signal_history)

        results = []
        for _ in range(2):
            strat = TemplateStrategy(copy.deepcopy(SESSION_SWEEP_CONFIG))
            state = MockState()
            state.log_signal_normalize = copy.deepcopy(normalized_log)
            context = {"df": _create_mock_df(1000), "state": state, "backfill_status": "READY"}
            results.append(strat.on_bar_close(context))

        self.assertEqual(results[0]["reason_code"], results[1]["reason_code"])
        self.assertEqual(results[0]["score"], results[1]["score"])
        self.assertEqual(results[0]["is_actionable"], results[1]["is_actionable"])


class TestOrderFlowDomDeterminism(unittest.TestCase):
    def test_determinism(self):
        signal_history = [
            {"tag": "sweep_bull", "t": 960},
        ]
        normalized_log = _to_normalized_records(signal_history)

        results = []
        for _ in range(2):
            strat = TemplateStrategy(copy.deepcopy(ORDER_FLOW_DOM_CONFIG))
            state = MockState()
            state.log_signal_normalize = copy.deepcopy(normalized_log)
            context = {"df": _create_mock_df(1000), "state": state, "backfill_status": "READY"}
            results.append(strat.on_bar_close(context))

        self.assertEqual(results[0]["reason_code"], results[1]["reason_code"])
        self.assertEqual(results[0]["score"], results[1]["score"])
        self.assertEqual(results[0]["is_actionable"], results[1]["is_actionable"])


class TestRegistryDeterminism(unittest.TestCase):
    """Two independent StrategyRegistry runs on identical data produce identical results."""

    def test_registry_full_determinism(self):
        signal_history = _make_bullish_signal_history()
        normalized_log = _to_normalized_records(signal_history)

        results = []
        for _ in range(2):
            registry = StrategyRegistry()
            for cfg in [TREND_CONT_CONFIG, SESSION_SWEEP_CONFIG, ORDER_FLOW_DOM_CONFIG]:
                config = copy.deepcopy(cfg)
                registry.register(TemplateStrategy(config))

            state = MockState()
            state.log_signal_normalize = copy.deepcopy(normalized_log)
            df = _create_mock_df(1000)
            signals = {}  # Empty signals dict — not needed for strategy evaluation

            accepted = registry.evaluate_all(df, signals, state)
            rejections = registry.get_rejections(clear=True)
            results.append({"accepted": accepted, "rejections": rejections})

        self.assertEqual(len(results[0]["accepted"]), len(results[1]["accepted"]))
        self.assertEqual(len(results[0]["rejections"]), len(results[1]["rejections"]))

        for a, b in zip(results[0]["accepted"], results[1]["accepted"]):
            self.assertEqual(a.get("strategy"), b.get("strategy"))

        for a, b in zip(results[0]["rejections"], results[1]["rejections"]):
            self.assertEqual(a.get("reason_code"), b.get("reason_code"))
            self.assertEqual(a.get("strategy"), b.get("strategy"))


if __name__ == "__main__":
    unittest.main()
