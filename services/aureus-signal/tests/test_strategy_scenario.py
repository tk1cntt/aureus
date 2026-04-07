"""Scenario tests: run seed strategies through FULL signal pipeline on frozen CSV data.

Validates that strategies produce meaningful triggers/rejections on real market data
and that reject reasons are from the expected set. Also verifies determinism of the
full pipeline (two independent replays on same data → identical results).

Requires CSV fixture files from Plan 01 (export_candle_fixtures.py).
No DB, no Redis — pure offline pipeline.
"""
import json
import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.state import SymbolState
from engine.signal_factory import create_signal_set
from engine.live_engine import execute_signals_for_candle
from engine.strategies.registry import StrategyRegistry
from engine.strategies.template import TemplateStrategy


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SYMBOLS_JSON = os.path.join(os.path.dirname(__file__), "..", "symbols.json")


def _load_fixture(symbol: str) -> pd.DataFrame:
    path = os.path.join(FIXTURES_DIR, f"candles_{symbol}.csv")
    if not os.path.exists(path):
        raise unittest.SkipTest(f"Fixture not found: {path}")
    df = pd.read_csv(path)
    df["t"] = df["t"].astype(int)
    for col in ["o", "h", "l", "c"]:
        df[col] = df[col].astype(float)
    df["v"] = df["v"].astype(float)
    return df


def _load_symbol_config(symbol: str) -> dict:
    if os.path.exists(SYMBOLS_JSON):
        with open(SYMBOLS_JSON) as f:
            return json.load(f).get(symbol, {})
    return {}


# ---------------------------------------------------------------------------
# Seed strategy configs (same as seed_strategies.py)
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
        "trailing": {"type": "SWING_LOW", "activation_pips": 20},
        "capital_risk_pct": 1.0,
        "early_exits": ["choch_down"],
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
        "trailing": {"type": "BREAKEVEN", "activation_pips": 15},
        "capital_risk_pct": 0.5,
        "early_exits": ["choch_down"],
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
        "trailing": {"type": "SWING_LOW", "activation_pips": 15},
        "capital_risk_pct": 1.5,
        "early_exits": ["choch_down"],
    },
}

ALL_CONFIGS = [TREND_CONT_CONFIG, SESSION_SWEEP_CONFIG, ORDER_FLOW_DOM_CONFIG]


# ---------------------------------------------------------------------------
# Replay helper
# ---------------------------------------------------------------------------

def _run_replay(df: pd.DataFrame, strategy_configs: list, symbol: str = "XAUUSD") -> dict:
    """Feed candles through full signal+strategy pipeline, return metrics.

    Uses a subset of data (last 250 bars) to keep tests fast.
    The full 2000-bar replay is done by strategy_replay.py (Plan 04).
    """
    import copy

    TOTAL_BARS = 250  # Use last N bars of fixture data
    EVAL_BARS = 100   # Only track events for the last N bars
    WINDOW_SIZE = 250 # Sliding window for signal computation

    sym_cfg = _load_symbol_config(symbol)
    signals = create_signal_set(symbol, sym_cfg)
    state = SymbolState(symbol)
    registry = StrategyRegistry()
    for cfg in strategy_configs:
        config = copy.deepcopy(cfg)
        registry.register(TemplateStrategy(config))

    all_accepted = []
    all_rejections = []

    # Slice to last TOTAL_BARS for fast execution
    df = df.iloc[-TOTAL_BARS:].reset_index(drop=True)
    eval_start = max(0, len(df) - EVAL_BARS)

    for i in range(len(df)):
        window = df.iloc[max(0, i - WINDOW_SIZE + 1):i + 1]
        if len(window) < 5:
            continue

        state.transient_signals = {}
        execute_signals_for_candle(signals, window, state, symbol, redis_client=None)

        # Only track events during the evaluation phase (last EVAL_BARS)
        if i >= eval_start:
            accepted = registry.evaluate_all(window, signals, state)
            rejections = registry.get_rejections(clear=True)
            all_accepted.extend(accepted)
            all_rejections.extend(rejections)

    return {
        "accepted": all_accepted,
        "rejections": all_rejections,
        "bar_count": len(df),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScenarioFullPipeline(unittest.TestCase):
    """Run each seed strategy through the full signal pipeline on XAUUSD data."""

    @classmethod
    def setUpClass(cls):
        cls.xauusd_df = _load_fixture("XAUUSD")

    def test_xauusd_trend_cont_produces_results(self):
        """TREND_CONT on XAUUSD real data should produce at least some triggers or rejections."""
        result = _run_replay(self.xauusd_df, [TREND_CONT_CONFIG])
        total_events = len(result["accepted"]) + len(result["rejections"])
        self.assertGreater(total_events, 0, "TREND_CONT produced zero events on XAUUSD data")

    def test_xauusd_session_sweep_produces_results(self):
        result = _run_replay(self.xauusd_df, [SESSION_SWEEP_CONFIG])
        total_events = len(result["accepted"]) + len(result["rejections"])
        self.assertGreater(total_events, 0, "SESSION_SWEEP produced zero events on XAUUSD data")

    def test_xauusd_order_flow_dom_produces_results(self):
        result = _run_replay(self.xauusd_df, [ORDER_FLOW_DOM_CONFIG])
        total_events = len(result["accepted"]) + len(result["rejections"])
        self.assertGreater(total_events, 0, "ORDER_FLOW_DOM produced zero events on XAUUSD data")

    def test_reject_reasons_are_expected(self):
        """All rejection reason_codes must be from the known set."""
        result = _run_replay(self.xauusd_df, ALL_CONFIGS)
        expected_reasons = {
            "CONTEXT_FILTER_FAILED",
            "SEQUENCE_NOT_MATCHED",
            "BACKFILL_NOT_READY",
            "VALIDATION_RULE_FAILED",
            "ORDER_PLAN_INVALID_SHAPE",
            "STRATEGY_EVALUATION_ERROR",
            # validate_entry / build_order_plan rejection codes
            "VALIDATION_REJECTED",
            "SCORE_BELOW_THRESHOLD",
        }
        for rej in result["rejections"]:
            self.assertIn(
                rej["reason_code"],
                expected_reasons,
                f"Unexpected rejection reason: {rej['reason_code']}",
            )

    def test_all_strategies_combined_produce_events(self):
        """Running all 3 strategies together should produce ≥1 event."""
        result = _run_replay(self.xauusd_df, ALL_CONFIGS)
        total = len(result["accepted"]) + len(result["rejections"])
        self.assertGreater(total, 0, "All strategies combined produced zero events")

    def test_scenario_determinism(self):
        """Two independent replays on same data produce identical results."""
        result_a = _run_replay(self.xauusd_df, [TREND_CONT_CONFIG])
        result_b = _run_replay(self.xauusd_df, [TREND_CONT_CONFIG])

        self.assertEqual(
            len(result_a["accepted"]),
            len(result_b["accepted"]),
            f"Accepted count mismatch: {len(result_a['accepted'])} vs {len(result_b['accepted'])}",
        )
        self.assertEqual(
            len(result_a["rejections"]),
            len(result_b["rejections"]),
            f"Rejection count mismatch: {len(result_a['rejections'])} vs {len(result_b['rejections'])}",
        )

        for a, b in zip(result_a["accepted"], result_b["accepted"]):
            self.assertEqual(a["t"], b["t"])
            self.assertEqual(a["strategy"], b["strategy"])


if __name__ == "__main__":
    unittest.main()
