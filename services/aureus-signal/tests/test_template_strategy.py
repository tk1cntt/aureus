import pytest
import pandas as pd
from engine.strategies.template import TemplateStrategy

class MockState:
    def __init__(self):
        self.signal_history = []
        self.log_signal_normalize = []
        self.strategy_progress = {}
        self.symbol = "XAUUSD"

class PureState:
    pass

def create_mock_df(t_val=1000):
    return pd.DataFrame([{"t": t_val}])

def append_normalized_events(state, t_val, *tags):
    state.log_signal_normalize.append({
        "t": t_val,
        "signals": {
            "events": [{"tag": tag} for tag in tags]
        }
    })

def test_sequence_match_perfect():
    config = {
        "name": "test_strat",
        "min_score_threshold": 2.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True}
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    # Step 1
    append_normalized_events(state, 1000, "STEP1")
    result1 = strategy._evaluate_sequence(create_mock_df(1000), state)
    
    assert state.strategy_progress["test_strat"]["progress_pct"] == 50.0
    assert result1["score"] == 1.0
    assert result1["missing_required"] == True

    # Step 2
    append_normalized_events(state, 1060, "STEP2")
    result2 = strategy._evaluate_sequence(create_mock_df(1060), state)
    
    assert state.strategy_progress["test_strat"]["progress_pct"] == 100.0
    assert result2["score"] == 2.0
    assert result2["missing_required"] == False

def test_sequence_reset_priority():
    config = {
        "name": "test_strat",
        "min_score_threshold": 1.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True, "reset_signals": ["RESET_TAG"]}
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    # Step 1
    append_normalized_events(state, 1000, "STEP1")
    strategy._evaluate_sequence(create_mock_df(1000), state)

    assert state.strategy_progress["test_strat"]["progress_pct"] == 50.0

    # Step 2 with simultaneous reset
    # We simulate a "candle" that has multiple tags ending up in history.
    # Wait, history only has one tag per entry? 
    # Actually, in reality, a candle could generate multiple events. Live engine might append multiple items to signal_history per candle.
    # But for O(1), the engine will evaluate on_bar_close. If multiple tags occurred in this candle...
    # Let's assume on_bar_close is called once per candle. The history has multiple entries for this candle.
    # But the O(1) state evaluator only looks at events matching the current candle index? 
    # Let's simplify: the test appends the reset tag, and evaluate handles it.
    
    # Actually, the requirement says "bất kỳ tag nào trong history[-1]" or "nến hiện tại chứa reset_tags".
    # For now, let's just append RESET_TAG to history.
    append_normalized_events(state, 1060, "RESET_TAG")
    strategy._evaluate_sequence(create_mock_df(1060), state)
    
    # Progress should be reset to 0
    assert state.strategy_progress["test_strat"]["progress_pct"] == 0.0

def test_sequence_timeout():
    config = {
        "name": "test_strat",
        "min_score_threshold": 1.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True, "max_wait": 2}
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    append_normalized_events(state, 1000, "STEP1")
    strategy._evaluate_sequence(create_mock_df(1000), state)

    # 1 candle passes (no relevant tag)
    append_normalized_events(state, 1060, "NOISE")
    strategy._evaluate_sequence(create_mock_df(1060), state)

    # 2 candles pass
    append_normalized_events(state, 1120, "NOISE")
    strategy._evaluate_sequence(create_mock_df(1120), state)

    # 3 candles pass -> Timeout should trigger on evaluaton!
    append_normalized_events(state, 1180, "NOISE")
    strategy._evaluate_sequence(create_mock_df(1180), state)
    
    # Progress should be reset
    assert state.strategy_progress["test_strat"]["progress_pct"] == 0.0

def test_sequence_optional_skip():
    config = {
        "name": "test_strat",
        "min_score_threshold": 1.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": False}, # Optional
            {"tag": "STEP3", "weight": 1.0, "required": True}
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    append_normalized_events(state, 1000, "STEP1")
    strategy._evaluate_sequence(create_mock_df(1000), state)

    # Next tag is STEP3 directly!
    append_normalized_events(state, 1060, "STEP3")
    strategy._evaluate_sequence(create_mock_df(1060), state)

    # Both STEP1 and STEP3 are matched. STEP2 is skipped.
    assert state.strategy_progress["test_strat"]["progress_pct"] == 100.0 * (2/3) # 2 out of 3 steps completed
    assert state.strategy_progress["test_strat"]["sequence"][2]["status"] == "matched"

def test_evaluate_coverage():
    config = {
        "name": "eval_strat",
        "min_score_threshold": 2.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True}
        ],
        "exit_config": {"tp": 100},
        "trade_execution": {
            "direction": "BUY"
        }
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    # Missing required -> None
    append_normalized_events(state, 1000, "STEP1")
    res = strategy.evaluate(create_mock_df(1000), {}, state)
    assert res is None

    # Below score threshold -> None
    # Let's change config min score to 3.0 temporarily
    strategy.min_score = 3.0
    append_normalized_events(state, 1060, "STEP2")
    res = strategy.evaluate(create_mock_df(1060), {}, state)
    assert res is None

    # Full match
    strategy.min_score = 2.0
    res = strategy.evaluate(create_mock_df(1060), {}, state)
    assert res is not None
    assert res["strategy"] == "eval_strat"
    assert res["exit_config"]["tp"] == 100

def test_on_bar_close_coverage():
    config = {"name": "bar_strat", "min_score_threshold": 1.0, "sequence": [{"tag": "T1", "weight": 1.0, "required": True}], "trade_execution": {"direction": "BUY"}}
    strategy = TemplateStrategy(config)
    state = MockState()
    
    # Invalid context
    res = strategy.on_bar_close({})
    assert res["reason_code"] == "INVALID_CONTEXT"
    
    # Backfill not ready
    ctx = {"df": create_mock_df(1000), "state": state, "backfill_status": "SYNCING"}
    res = strategy.on_bar_close(ctx)
    assert res["reason_code"] == "BACKFILL_NOT_READY"
    
    # Sequence not matched
    ctx["backfill_status"] = "READY"
    res = strategy.on_bar_close(ctx)
    assert res["reason_code"] == "SEQUENCE_NOT_MATCHED"
    assert res["sequence_diagnostics"]["mismatch_reason"] == "MISSING_REQUIRED_AND_SCORE_BELOW_THRESHOLD"
    assert res["sequence_diagnostics"]["missing_required_tags"] == ["T1"]
    assert res["sequence_diagnostics"]["current_step_index"] == 0
    assert res["sequence_diagnostics"]["step_status"][0]["tag"] == "T1"
    assert res["sequence_diagnostics"]["step_status"][0]["status"] == "waiting"
    
    # Match OK
    append_normalized_events(state, 1000, "T1")
    res = strategy.on_bar_close(ctx)
    assert res["reason_code"] == "OK"
    assert res["symbol"] == "XAUUSD"

def test_validate_entry_coverage():
    strategy = TemplateStrategy({"name": "val_strat", "trade_execution": {"direction": "BUY"}})

    # Missing intent
    assert strategy.validate_entry(None, {})["reason_code"] == "NO_INTENT"
    
    # Backfill
    assert strategy.validate_entry({"reason_code": "BACKFILL_NOT_READY"}, {})["reason_code"] == "BACKFILL_NOT_READY"
    
    # Not actionable
    assert strategy.validate_entry({"is_actionable": False}, {})["reason_code"] == "UNKNOWN"
    
    # OK
    assert strategy.validate_entry({"is_actionable": True, "reason_code": "OK"}, {})["reason_code"] == "OK"

def test_build_order_plan_coverage():
    strategy = TemplateStrategy({"name": "order_strat", "exit_config": {"tp": 50}, "trade_execution": {"direction": "BUY"}})

    intent = {"direction": "SELL"}
    plan = strategy.build_order_plan(intent, {})
    
    assert plan["direction"] == "SELL"
    assert plan["tp"] == 50
    assert plan["reason_code"] == "OK"

def test_missing_state_init():
    strategy = TemplateStrategy({"name": "init_strat", "sequence": [], "trade_execution": {"direction": "BUY"}})
    state = PureState()
    strategy._evaluate_sequence(create_mock_df(), state)
    assert hasattr(state, "strategy_progress")


def test_sequence_fallback_to_signal_history_when_normalized_empty():
    # TEST BEHAVIOR UPDATE: We NO LONGER fallback to signal_history.
    # If events are not in log_signal_normalize, sequence matcher ignores them.
    strategy = TemplateStrategy({
        "name": "fallback_strat",
        "min_score_threshold": 2.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True},
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    })
    state = MockState()

    # Appending to legacy signal_history ONLY
    state.signal_history.append({"tag": "STEP1", "t": 1000})
    state.signal_history.append({"tag": "STEP2", "t": 1060})

    result = strategy._evaluate_sequence(create_mock_df(1060), state)

    # Sequence progress should NOT advance since source_records=log_signal_normalize=[]
    assert result["score"] == 0.0
    assert result["missing_required"] is True
    assert result["matched_steps"] == 0


def test_sequence_prioritizes_normalized_over_signal_history():
    strategy = TemplateStrategy({
        "name": "priority_strat",
        "min_score_threshold": 1.0,
        "sequence": [{"tag": "TARGET", "weight": 1.0, "required": True}],
        "trade_execution": {
            "direction": "BUY"
        }
    })
    state = MockState()

    state.signal_history.append({"tag": "WRONG", "t": 1000})
    append_normalized_events(state, 1000, "TARGET")

    result = strategy._evaluate_sequence(create_mock_df(1000), state)

    assert result["score"] == 1.0
    assert result["missing_required"] is False


def test_sequence_normalized_records_processed_in_ascending_time_order():
    strategy = TemplateStrategy({
        "name": "sorted_time_strat",
        "min_score_threshold": 2.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True},
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    })
    state = MockState()

    append_normalized_events(state, 1060, "STEP2")
    append_normalized_events(state, 1000, "STEP1")

    result = strategy._evaluate_sequence(create_mock_df(1060), state)

    assert result["score"] == 2.0
    assert result["missing_required"] is False
    progress = state.strategy_progress["sorted_time_strat"]
    assert progress["origin_timestamp"] == 1000
    assert progress["sequence"][0]["time"] == 1000
    assert progress["sequence"][1]["time"] == 1060

def test_sequence_resets_upon_new_step0_when_complete():
    strategy = TemplateStrategy({
        "name": "reset_strat",
        "min_score_threshold": 2.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True},
        ],
        "trade_execution": {
            "direction": "BUY"
        }
    })
    state = MockState()

    # Match full sequence first
    append_normalized_events(state, 1000, "STEP1")
    append_normalized_events(state, 1060, "STEP2")
    res1 = strategy._evaluate_sequence(create_mock_df(1060), state)

    assert res1["score"] == 2.0
    assert res1["missing_required"] is False
    assert res1["matched_steps"] == 2
    
    # Progress is at len(sequence) = 2. Now a new STEP1 arrives: it should reset and match step 0
    append_normalized_events(state, 1100, "STEP1")
    res2 = strategy._evaluate_sequence(create_mock_df(1100), state)

    # Score should be 1.0 because it's only matched STEP1 of the new cycle
    assert res2["score"] == 1.0
    assert res2["missing_required"] is True
    assert res2["matched_steps"] == 1
    
    progress = state.strategy_progress["reset_strat"]
    assert progress["origin_timestamp"] == 1100
    assert progress["current_step_index"] == 1
    assert progress["sequence"][0]["time"] == 1100


def test_direction_required():
    """Direction must be explicitly provided in trade_execution config."""
    config = {
        "name": "test_strat",
        "min_score_threshold": 1.0,
        "sequence": [],
        "trade_execution": {}  # No direction
    }
    with pytest.raises(ValueError, match="direction.*must be.*BUY.*SELL"):
        TemplateStrategy(config)


def test_direction_invalid_value():
    """Direction must be BUY or SELL, not arbitrary values."""
    config = {
        "name": "test_strat",
        "min_score_threshold": 1.0,
        "sequence": [],
        "trade_execution": {"direction": "HEDGE"}
    }
    with pytest.raises(ValueError, match="direction.*must be.*BUY.*SELL"):
        TemplateStrategy(config)


def test_direction_case_insensitive():
    """Direction should be normalized to uppercase."""
    config = {
        "name": "test_strat",
        "min_score_threshold": 1.0,
        "sequence": [],
        "trade_execution": {"direction": "buy"}
    }
    strategy = TemplateStrategy(config)
    assert strategy.direction == "BUY"

    config["trade_execution"]["direction"] = "Sell"
    strategy2 = TemplateStrategy(config)
    assert strategy2.direction == "SELL"
