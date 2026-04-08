"""
Test để kiểm tra xem tất cả các seed strategies có được kích hoạt đúng không.
Mục tiêu: Xác định tại sao 2 sequences không được kích hoạt.
"""
import pytest
import pandas as pd
from engine.strategies.template import TemplateStrategy
from engine.strategies.seed_strategies import seed_system_strategies
import json


class MockState:
    """Mock state object cho strategy evaluation."""
    def __init__(self):
        self.signal_history = []
        self.log_signal_normalize = []
        self.strategy_progress = {}
        self.symbol = "XAUUSD"
        # Các thuộc tính cần cho context filters (nếu có)
        self.htf_trend = "BULLISH"
        self.current_session = "LONDON"
        self.obs = []
        self.emas = {21: {"slope": 1.0}}


def create_mock_df(t_val=1000):
    """Tạo DataFrame đơn giản với timestamp."""
    return pd.DataFrame([{"t": t_val}])


def append_events(state, t_val, events):
    """Thêm các events vào log_signal_normalize.
    
    Format giống như engine thật:
    {
        "t": timestamp,
        "signals": {
            "events": [
                {"tag": "choch_up"},
                {"tag": "sweep_bull"}
            ]
        }
    }
    """
    state.log_signal_normalize.append({
        "t": t_val,
        "signals": {
            "events": events
        }
    })


def get_strategy_configs():
    """Lấy tất cả strategy configs từ seed_system_strategies."""
    # Đây là list các strategies được định nghĩa trong seed_strategies.py
    return [
        {
            "name": "TREND_CONT_BULL",
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 2.0},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "TREND_CONT_BEAR",
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 2.0},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "ORDER_FLOW_BULL",
            "description": "Specialized Trend Continuation focusing on Session Liquidity Sweeps with tighter stops.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 2.0},
                    "trailing": {"type": "BREAKEVEN", "activation_pips": 300},
                    "capital_risk_pct": 0.5,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "ORDER_FLOW_BEAR",
            "description": "Specialized Trend Continuation focusing on Session Liquidity Sweeps with tighter stops.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]},
                    {"tag": "sweep_bear", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 2.0},
                    "trailing": {"type": "BREAKEVEN", "activation_pips": 300},
                    "capital_risk_pct": 0.5,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "SESSION_SWEEP_BULL",
            "description": "Dominance-based strategy. Massive OB imbalance with trend alignment and sweep trigger.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 2.0},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.5,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "SESSION_SWEEP_BEAR",
            "description": "Dominance-based strategy. Massive OB imbalance with trend alignment and sweep trigger.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bear", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 4.0},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.5,
                    "early_exits": ["choch_up"]
                }
            }
        }
    ]


class TestSeedStrategiesActivation:
    """Test xem các seed strategies có được kích hoạt không."""

    def test_trend_cont_bull_single_step(self):
        """TREND_CONT_BULL: Chỉ cần 1 step - choch_up với weight=4.0 >= min_score_threshold=0"""
        config = {
            "name": "TREND_CONT_BULL",
            "min_score_threshold": 0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }
        
        strategy = TemplateStrategy(config)
        state = MockState()
        
        # Gửi event choch_up
        append_events(state, 1000, [{"tag": "choch_up"}])
        df = create_mock_df(1000)
        
        intent = strategy.evaluate(df, {}, state)
        
        print(f"\nTREND_CONT_BULL:")
        print(f"  Intent: {intent}")
        print(f"  Progress: {state.strategy_progress.get('TREND_CONT_BULL')}")
        
        assert intent is not None, "TREND_CONT_BULL should trigger with single choch_up event"
        assert intent["strategy"] == "TREND_CONT_BULL"
        assert intent["score"] == 4.0

    def test_trend_cont_bear_single_step(self):
        """TREND_CONT_BEAR: Chỉ cần 1 step - choch_down với weight=4.0 >= min_score_threshold=0"""
        config = {
            "name": "TREND_CONT_BEAR",
            "min_score_threshold": 0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30 }
            ],
            "trade_execution": {
                "direction": "SELL"
            }
        }
        
        strategy = TemplateStrategy(config)
        state = MockState()
        
        # Gửi event choch_down
        append_events(state, 1000, [{"tag": "choch_down"}])
        df = create_mock_df(1000)
        
        intent = strategy.evaluate(df, {}, state)
        
        print(f"\nTREND_CONT_BEAR:")
        print(f"  Intent: {intent}")
        print(f"  Progress: {state.strategy_progress.get('TREND_CONT_BEAR')}")
        
        assert intent is not None, "TREND_CONT_BEAR should trigger with single choch_down event"
        assert intent["strategy"] == "TREND_CONT_BEAR"
        assert intent["score"] == 4.0

    def test_order_flow_bull_two_steps(self):
        """ORDER_FLOW_BULL: Cần 2 steps - choch_up(3.5) + sweep_bull(5.0) = 8.5 >= 6.0"""
        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }
        
        strategy = TemplateStrategy(config)
        state = MockState()
        
        # Step 1: choch_up
        append_events(state, 1000, [{"tag": "choch_up"}])
        df1 = create_mock_df(1000)
        intent1 = strategy.evaluate(df1, {}, state)
        
        print(f"\nORDER_FLOW_BULL - Step 1:")
        print(f"  Intent after choch_up: {intent1}")
        print(f"  Progress: {state.strategy_progress.get('ORDER_FLOW_BULL')}")
        
        assert intent1 is None, "Should not trigger after step 1 only"
        
        # Step 2: sweep_bull
        append_events(state, 1060, [{"tag": "sweep_bull"}])
        df2 = create_mock_df(1060)
        intent2 = strategy.evaluate(df2, {}, state)
        
        print(f"\nORDER_FLOW_BULL - Step 2:")
        print(f"  Intent after sweep_bull: {intent2}")
        print(f"  Progress: {state.strategy_progress.get('ORDER_FLOW_BULL')}")
        
        assert intent2 is not None, "ORDER_FLOW_BULL should trigger after both steps"
        assert intent2["strategy"] == "ORDER_FLOW_BULL"
        assert intent2["score"] == 8.5

    def test_order_flow_bear_two_steps(self):
        """ORDER_FLOW_BEAR: Cần 2 steps - choch_down(3.5) + sweep_bear(5.0) = 8.5 >= 6.0"""
        config = {
            "name": "ORDER_FLOW_BEAR",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_down", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]},
                {"tag": "sweep_bear", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_up"]}
            ],
            "trade_execution": {
                "direction": "SELL"
            }
        }
        
        strategy = TemplateStrategy(config)
        state = MockState()
        
        # Step 1: choch_down
        append_events(state, 1000, [{"tag": "choch_down"}])
        df1 = create_mock_df(1000)
        intent1 = strategy.evaluate(df1, {}, state)
        
        print(f"\nORDER_FLOW_BEAR - Step 1:")
        print(f"  Intent after choch_down: {intent1}")
        print(f"  Progress: {state.strategy_progress.get('ORDER_FLOW_BEAR')}")
        
        assert intent1 is None, "Should not trigger after step 1 only"
        
        # Step 2: sweep_bear
        append_events(state, 1060, [{"tag": "sweep_bear"}])
        df2 = create_mock_df(1060)
        intent2 = strategy.evaluate(df2, {}, state)
        
        print(f"\nORDER_FLOW_BEAR - Step 2:")
        print(f"  Intent after sweep_bear: {intent2}")
        print(f"  Progress: {state.strategy_progress.get('ORDER_FLOW_BEAR')}")
        
        assert intent2 is not None, "ORDER_FLOW_BEAR should trigger after both steps"
        assert intent2["strategy"] == "ORDER_FLOW_BEAR"
        assert intent2["score"] == 8.5

    def test_session_sweep_bull_single_step(self):
        """SESSION_SWEEP_BULL: Chỉ cần 1 step - sweep_bull với weight=7.0 >= 6.0"""
        config = {
            "name": "SESSION_SWEEP_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }
        
        strategy = TemplateStrategy(config)
        state = MockState()
        
        # Gửi event sweep_bull
        append_events(state, 1000, [{"tag": "sweep_bull"}])
        df = create_mock_df(1000)
        
        intent = strategy.evaluate(df, {}, state)
        
        print(f"\nSESSION_SWEEP_BULL:")
        print(f"  Intent: {intent}")
        print(f"  Progress: {state.strategy_progress.get('SESSION_SWEEP_BULL')}")
        
        assert intent is not None, "SESSION_SWEEP_BULL should trigger with single sweep_bull event"
        assert intent["strategy"] == "SESSION_SWEEP_BULL"
        assert intent["score"] == 7.0

    def test_session_sweep_bear_single_step(self):
        """SESSION_SWEEP_BEAR: Chỉ cần 1 step - sweep_bear với weight=7.0 >= 6.0"""
        config = {
            "name": "SESSION_SWEEP_BEAR",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "sweep_bear", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]}
            ],
            "trade_execution": {
                "direction": "SELL"
            }
        }
        
        strategy = TemplateStrategy(config)
        state = MockState()
        
        # Gửi event sweep_bear
        append_events(state, 1000, [{"tag": "sweep_bear"}])
        df = create_mock_df(1000)
        
        intent = strategy.evaluate(df, {}, state)
        
        print(f"\nSESSION_SWEEP_BEAR:")
        print(f"  Intent: {intent}")
        print(f"  Progress: {state.strategy_progress.get('SESSION_SWEEP_BEAR')}")
        
        assert intent is not None, "SESSION_SWEEP_BEAR should trigger with single sweep_bear event"
        assert intent["strategy"] == "SESSION_SWEEP_BEAR"
        assert intent["score"] == 7.0


class TestEventFormatNormalization:
    """Kiểm tra xem events có được normalize đúng từ format {tag: 'choch', value: 'choch_up'} không."""
    
    def test_event_format_raw_vs_normalized(self):
        """So sánh 2 cách gửi events: raw format vs normalized format."""
        
        # Strategy cần 2 steps
        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }
        
        # Test 1: Raw format (tag=choch, value=choch_up)
        strategy1 = TemplateStrategy(config)
        state1 = MockState()
        
        print("\n" + "="*80)
        print("TEST 1: RAW FORMAT - {'tag': 'choch', 'value': 'choch_up'}")
        print("="*80)
        
        # Step 1: Raw format
        state1.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch", "value": "choch_up"},  # RAW FORMAT
                    {"tag": "sweep", "value": "sweep_bull"}  # RAW FORMAT
                ]
            }
        })
        df1 = create_mock_df(1000)
        intent1 = strategy1.evaluate(df1, {}, state1)
        
        print(f"Intent: {intent1}")
        print(f"Progress: {json.dumps(state1.strategy_progress.get('ORDER_FLOW_BULL'), indent=2, default=str)}")
        
        # Test 2: Normalized format (tag=choch_up)
        strategy2 = TemplateStrategy(config)
        state2 = MockState()
        
        print("\n" + "="*80)
        print("TEST 2: NORMALIZED FORMAT - {'tag': 'choch_up'}")
        print("="*80)
        
        state2.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up"},  # NORMALIZED FORMAT
                    {"tag": "sweep_bull"}  # NORMALIZED FORMAT
                ]
            }
        })
        df2 = create_mock_df(1000)
        intent2 = strategy2.evaluate(df2, {}, state2)
        
        print(f"Intent: {intent2}")
        print(f"Progress: {json.dumps(state2.strategy_progress.get('ORDER_FLOW_BULL'), indent=2, default=str)}")
        
        # So sánh kết quả
        print("\n" + "="*80)
        print("SO SÁNH KẾT QUẢ:")
        print("="*80)
        print(f"Raw format triggered: {intent1 is not None}")
        print(f"Normalized format triggered: {intent2 is not None}")
        
        if intent1:
            print(f"  Raw format score: {intent1['score']}")
        if intent2:
            print(f"  Normalized format score: {intent2['score']}")
        
        # Cả 2 format đều phải trigger
        assert intent1 is not None, "Raw format should trigger after normalization"
        assert intent2 is not None, "Normalized format should trigger"
        assert intent1["score"] == intent2["score"], "Both formats should produce same score"

    def test_all_strategies_with_raw_event_format(self):
        """Test tất cả strategies với raw event format (tag + value)."""
        strategies_configs = get_strategy_configs()
        results = {}
        
        print("\n" + "="*80)
        print("TEST VỚI RAW EVENT FORMAT: {'tag': 'choch', 'value': 'choch_up'}")
        print("="*80)
        
        for strat_config in strategies_configs:
            name = strat_config["name"]
            config = strat_config["config"]
            config["name"] = name
            
            strategy = TemplateStrategy(config)
            state = MockState()
            
            # Lấy các tags từ sequence
            sequence = config.get("sequence", [])
            
            # Tạo raw events với format {tag: base_tag, value: specific_tag}
            raw_events = []
            for step in sequence:
                tag = step["tag"]
                # Map từ specific tag sang base tag + value
                if tag in ["choch_up", "choch_down"]:
                    raw_events.append({"tag": "choch", "value": tag})
                elif tag in ["sweep_bull", "sweep_bear"]:
                    raw_events.append({"tag": "sweep", "value": tag})
                else:
                    # Giữ nguyên nếu không phải special tag
                    raw_events.append({"tag": tag})
            
            # Gửi raw events
            state.log_signal_normalize.append({
                "t": 1000,
                "signals": {
                    "events": raw_events
                }
            })
            df = create_mock_df(1000)
            
            intent = strategy.evaluate(df, {}, state)
            
            results[name] = {
                "triggered": intent is not None,
                "score": intent["score"] if intent else None,
                "min_score_threshold": config.get("min_score_threshold"),
                "sequence_length": len(sequence),
                "raw_events_sent": raw_events,
                "intent": intent
            }
            
            print(f"\n{name}:")
            print(f"  Raw events: {raw_events}")
            print(f"  Triggered: {intent is not None}")
            print(f"  Score: {intent['score'] if intent else 'N/A'}")
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY - RAW EVENT FORMAT:")
        print("="*80)
        triggered_count = sum(1 for r in results.values() if r["triggered"])
        not_triggered_count = sum(1 for r in results.values() if not r["triggered"])
        
        print(f"Triggered: {triggered_count}/{len(results)}")
        print(f"Not Triggered: {not_triggered_count}/{len(results)}")
        
        for name, result in results.items():
            status = "✅ TRIGGERED" if result["triggered"] else "❌ NOT TRIGGERED"
            print(f"  {status} - {name} (score={result['score']}, threshold={result['min_score_threshold']})")
        
        # Kiểm tra
        not_triggered = [name for name, result in results.items() if not result["triggered"]]
        assert len(not_triggered) == 0, f"Các strategies KHÔNG trigger với raw format: {not_triggered}"


class TestAllStrategiesTogether:
    """Test tất cả strategies cùng lúc để xem cái nào KHÔNG trigger."""
    
    def test_all_strategies_activation(self):
        """Kiểm tra xem strategies nào trigger và không trigger."""
        strategies_configs = get_strategy_configs()
        results = {}
        
        for strat_config in strategies_configs:
            name = strat_config["name"]
            config = strat_config["config"]
            config["name"] = name
            
            strategy = TemplateStrategy(config)
            state = MockState()
            
            # Lấy các tags cần thiết từ sequence
            sequence = config.get("sequence", [])
            tags_needed = [step["tag"] for step in sequence]
            
            # Gửi tất cả events cùng lúc
            events = [{"tag": tag} for tag in tags_needed]
            append_events(state, 1000, events)
            df = create_mock_df(1000)
            
            intent = strategy.evaluate(df, {}, state)
            
            results[name] = {
                "triggered": intent is not None,
                "score": intent["score"] if intent else None,
                "min_score_threshold": config.get("min_score_threshold"),
                "sequence_length": len(sequence),
                "tags_needed": tags_needed,
                "intent": intent
            }
            
            print(f"\n{name}:")
            print(f"  Triggered: {intent is not None}")
            print(f"  Score: {intent['score'] if intent else 'N/A'}")
            print(f"  Min Score Threshold: {config.get('min_score_threshold')}")
            print(f"  Sequence: {tags_needed}")
        
        # In summary
        print("\n" + "="*80)
        print("SUMMARY - Strategies Activation:")
        print("="*80)
        triggered_count = sum(1 for r in results.values() if r["triggered"])
        not_triggered_count = sum(1 for r in results.values() if not r["triggered"])
        
        print(f"Triggered: {triggered_count}/{len(results)}")
        print(f"Not Triggered: {not_triggered_count}/{len(results)}")
        
        for name, result in results.items():
            status = "✅ TRIGGERED" if result["triggered"] else "❌ NOT TRIGGERED"
            print(f"  {status} - {name} (score={result['score']}, threshold={result['min_score_threshold']})")
        
        # Kiểm tra xem có strategy nào không trigger không
        not_triggered = [name for name, result in results.items() if not result["triggered"]]
        
        if not_triggered:
            print(f"\n⚠️  Strategies KHÔNG trigger được:")
            for name in not_triggered:
                print(f"  - {name}")
                print(f"    Tags cần: {results[name]['tags_needed']}")
                print(f"    Min score threshold: {results[name]['min_score_threshold']}")
