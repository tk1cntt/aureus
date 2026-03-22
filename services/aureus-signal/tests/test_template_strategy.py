import pytest
import pandas as pd
from engine.strategies.template import TemplateStrategy

class MockState:
    def __init__(self):
        self.signal_history = []
        self.strategy_progress = {}

class PureState:
    pass

def create_mock_df(t_val=1000):
    return pd.DataFrame([{"t": t_val}])

def test_sequence_match_perfect():
    config = {
        "name": "test_strat",
        "min_score_threshold": 2.0,
        "sequence": [
            {"tag": "STEP1", "weight": 1.0, "required": True},
            {"tag": "STEP2", "weight": 1.0, "required": True}
        ]
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    # Step 1
    state.signal_history.append({"tag": "STEP1", "t": 1000})
    result1 = strategy._evaluate_sequence(create_mock_df(1000), state)
    
    assert state.strategy_progress["test_strat"]["progress_pct"] == 50.0
    assert result1["score"] == 1.0
    assert result1["missing_required"] == True

    # Step 2
    state.signal_history.append({"tag": "STEP2", "t": 1060})
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
        ]
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    # Step 1
    state.signal_history.append({"tag": "STEP1", "t": 1000})
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
    state.signal_history.append({"tag": "RESET_TAG", "t": 1060})
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
        ]
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    state.signal_history.append({"tag": "STEP1", "t": 1000})
    strategy._evaluate_sequence(create_mock_df(1000), state)

    # 1 candle passes (no relevant tag)
    state.signal_history.append({"tag": "NOISE", "t": 1060})
    strategy._evaluate_sequence(create_mock_df(1060), state)

    # 2 candles pass
    state.signal_history.append({"tag": "NOISE", "t": 1120})
    strategy._evaluate_sequence(create_mock_df(1120), state)

    # 3 candles pass -> Timeout should trigger on evaluaton!
    state.signal_history.append({"tag": "NOISE", "t": 1180})
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
        ]
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    state.signal_history.append({"tag": "STEP1", "t": 1000})
    strategy._evaluate_sequence(create_mock_df(1000), state)

    # Next tag is STEP3 directly!
    state.signal_history.append({"tag": "STEP3", "t": 1060})
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
        "exit_config": {"tp": 100}
    }
    strategy = TemplateStrategy(config)
    state = MockState()

    # Missing required -> None
    state.signal_history.append({"tag": "STEP1", "t": 1000})
    res = strategy.evaluate(create_mock_df(1000), {}, state)
    assert res is None

    # Below score threshold -> None
    # Let's change config min score to 3.0 temporarily
    strategy.min_score = 3.0
    state.signal_history.append({"tag": "STEP2", "t": 1060})
    res = strategy.evaluate(create_mock_df(1060), {}, state)
    assert res is None

    # Full match
    strategy.min_score = 2.0
    res = strategy.evaluate(create_mock_df(1060), {}, state)
    assert res is not None
    assert res["strategy"] == "eval_strat"
    assert res["exit_config"]["tp"] == 100

def test_on_bar_close_coverage():
    config = {"name": "bar_strat", "min_score_threshold": 1.0, "sequence": [{"tag": "T1", "weight": 1.0, "required": True}]}
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
    
    # Match OK
    state.signal_history.append({"tag": "T1", "t": 1000})
    res = strategy.on_bar_close(ctx)
    assert res["reason_code"] == "OK"

def test_validate_entry_coverage():
    strategy = TemplateStrategy({"name": "val_strat"})
    
    # Missing intent
    assert strategy.validate_entry(None, {})["reason_code"] == "NO_INTENT"
    
    # Backfill
    assert strategy.validate_entry({"reason_code": "BACKFILL_NOT_READY"}, {})["reason_code"] == "BACKFILL_NOT_READY"
    
    # Not actionable
    assert strategy.validate_entry({"is_actionable": False}, {})["reason_code"] == "SEQUENCE_NOT_MATCHED"
    
    # OK
    assert strategy.validate_entry({"is_actionable": True, "reason_code": "OK"}, {})["reason_code"] == "OK"

def test_build_order_plan_coverage():
    strategy = TemplateStrategy({"name": "order_strat", "exit_config": {"tp": 50}})
    
    intent = {"direction": "SELL"}
    plan = strategy.build_order_plan(intent, {})
    
    assert plan["direction"] == "SELL"
    assert plan["tp"] == 50
    assert plan["reason_code"] == "OK"

def test_missing_state_init():
    strategy = TemplateStrategy({"name": "init_strat", "sequence": []})
    state = PureState()
    strategy._evaluate_sequence(create_mock_df(), state)
    assert hasattr(state, "strategy_progress")

