"""
Integration test mô phỏng production environment để debug seed strategies.

Test này kiểm tra toàn bộ flow:
1. Signal detectors (structure.py, sweep.py) tạo events
2. Events được normalize vào log_signal_normalize
3. Strategy executor nhận events từ Redis stream
4. evaluate() và on_bar_close() xử lý events
5. Context filters có được kiểm tra đúng không

Mục tiêu: Xác định chính xác tại sao 2 sequences không trigger trong production.
"""
import pytest
import pandas as pd
import json
from unittest.mock import Mock, MagicMock
from engine.strategies.template import TemplateStrategy
from engine.strategies.registry import StrategyRegistry
from engine.state import SymbolState


class TestProductionEnvironmentSimulation:
    """Test mô phỏng production environment."""

    def _create_minimal_candle_df(self, base_t=1000, num_candles=10):
        """Tạo candle DataFrame tối giản."""
        candles = []
        for i in range(num_candles):
            candles.append({
                "t": base_t + (i * 60),  # 1 phút mỗi nến
                "o": 2000.0 + i,
                "h": 2010.0 + i,
                "l": 1990.0 + i,
                "c": 2005.0 + i,
                "v": 100
            })
        return pd.DataFrame(candles)

    def _create_state_with_context(self, symbol="XAUUSD"):
        """Tạo state object với đầy đủ context cho filters."""
        state = SymbolState(symbol)
        state.symbol = symbol
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_context_filters_blocking_strategies(self):
        """Test xem context filters có blocking strategies không."""
        print("\n" + "="*80)
        print("TEST: Context Filters Blocking")
        print("="*80)

        # Strategy với context filters nghiêm ngặt
        config = {
            "name": "TEST_CONTEXT_FILTER",
            "min_score_threshold": 0,
            "context_filters": [
                {
                    "type": "trend_alignment",
                    "required_trend": "BULLISH"
                },
                {
                    "type": "session_active",
                    "allowed": ["LONDON", "NEW_YORK"]
                }
            ],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }

        strategy = TemplateStrategy(config)

        # Test 1: Context ĐÚNG - Phải trigger
        print("\n--- Test 1: Context ĐÚNG ---")
        state1 = self._create_state_with_context()
        state1.htf_trend = "BULLISH"  # Đúng trend
        state1.current_session = "LONDON"  # Đúng session

        state1.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "choch_up"}]
            }
        })

        df1 = self._create_minimal_candle_df(1000, 1)
        result1 = strategy.evaluate(df1, {}, state1)

        print(f"  Context: htf_trend={state1.htf_trend}, session={state1.current_session}")
        print(f"  Result: {result1 is not None}")
        if result1:
            print(f"  Score: {result1['score']}")

        assert result1 is not None, "Strategy SHOULD trigger with correct context"

        # Test 2: Context SAI - Phải block
        print("\n--- Test 2: Context SAI (trend mismatch) ---")
        state2 = self._create_state_with_context()
        state2.htf_trend = "BEARISH"  # Sai trend!
        state2.current_session = "LONDON"

        state2.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "choch_up"}]
            }
        })

        df2 = self._create_minimal_candle_df(1000, 1)
        result2 = strategy.evaluate(df2, {}, state2)

        print(f"  Context: htf_trend={state2.htf_trend}, session={state2.current_session}")
        print(f"  Result: {result2 is not None}")

        assert result2 is None, "Strategy MUST NOT trigger with wrong context"

        # Test 3: Context SAI - Session không đúng
        print("\n--- Test 3: Context SAI (session mismatch) ---")
        state3 = self._create_state_with_context()
        state3.htf_trend = "BULLISH"
        state3.current_session = "ASIA"  # Session không được allowed!

        state3.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "choch_up"}]
            }
        })

        df3 = self._create_minimal_candle_df(1000, 1)
        result3 = strategy.evaluate(df3, {}, state3)

        print(f"  Context: htf_trend={state3.htf_trend}, session={state3.current_session}")
        print(f"  Result: {result3 is not None}")

        assert result3 is None, "Strategy MUST NOT trigger with wrong session"

        print("\n" + "="*80)
        print("✅ Context filters đang hoạt động ĐÚNG!")
        print("="*80)

    def test_event_format_normalization_in_production(self):
        """Test xem event format từ signal detectors có được normalize đúng không."""
        print("\n" + "="*80)
        print("TEST: Event Format Normalization (Raw → Normalized)")
        print("="*80)

        config = {
            "name": "TEST_EVENT_FORMAT",
            "min_score_threshold": 0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }

        # Test 1: Raw format từ structure.py và sweep.py
        print("\n--- Test 1: RAW format từ signal detectors ---")
        print("  Format: {tag: 'choch', value: 'choch_up'}")

        strategy1 = TemplateStrategy(config)
        state1 = self._create_state_with_context()

        # Structure.py tạo: {"tag": "choch", "value": "choch_up"}
        state1.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch", "value": "choch_up"},
                    {"tag": "sweep", "value": "sweep_bull"}
                ]
            }
        })

        df1 = self._create_minimal_candle_df(1000, 1)
        result1 = strategy1.evaluate(df1, {}, state1)

        print(f"  Result: {result1 is not None}")
        if result1:
            print(f"  Score: {result1['score']}")
            print(f"  Progress: {json.dumps(state1.strategy_progress.get('TEST_EVENT_FORMAT'), indent=4, default=str)}")

        # Test 2: Normalized format
        print("\n--- Test 2: NORMALIZED format ---")
        print("  Format: {tag: 'choch_up'}")

        strategy2 = TemplateStrategy(config)
        state2 = self._create_state_with_context()

        state2.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up"},
                    {"tag": "sweep_bull"}
                ]
            }
        })

        df2 = self._create_minimal_candle_df(1000, 1)
        result2 = strategy2.evaluate(df2, {}, state2)

        print(f"  Result: {result2 is not None}")
        if result2:
            print(f"  Score: {result2['score']}")

        # So sánh
        print("\n" + "="*80)
        print("SO SÁNH KẾT QUẢ:")
        print("="*80)
        print(f"Raw format triggered: {result1 is not None}")
        print(f"Normalized format triggered: {result2 is not None}")

        if result1 and result2:
            print(f"✅ CẢ HAI formats đều trigger!")
            print(f"   Raw score: {result1['score']}")
            print(f"   Normalized score: {result2['score']}")
        elif result2 and not result1:
            print(f"⚠️  CHỈ normalized format trigger!")
            print(f"   → BUG: Signal detectors tạo raw format nhưng strategy cần normalized!")
            print(f"   → FIX: Kiểm tra signal_factory.py hoặc aggregator có normalize không")
        else:
            print(f"❌ CẢ HAI đều không trigger - Có bug khác!")

        assert result2 is not None, "Normalized format MUST trigger"

    def test_seed_strategies_with_context_filters(self):
        """Test 6 seed strategies với context filters thực tế."""
        print("\n" + "="*80)
        print("TEST: Seed Strategies với Context Filters Thực Tế")
        print("="*80)

        seed_configs = [
            {
                "name": "TREND_CONT_BULL",
                "min_score_threshold": 0,
                "context_filters": [],  # Không có filters
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
                ],
                "trade_execution": {"direction": "BUY"}
            },
            {
                "name": "ORDER_FLOW_BULL",
                "min_score_threshold": 6.0,
                "context_filters": [
                    {"type": "trend_alignment", "required_trend": "BULLISH"}
                ],
                "sequence": [
                    {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
                ],
                "trade_execution": {"direction": "BUY"}
            },
            {
                "name": "SESSION_SWEEP_BULL",
                "min_score_threshold": 6.0,
                "context_filters": [
                    {"type": "session_active", "allowed": ["LONDON", "NEW_YORK"]}
                ],
                "sequence": [
                    {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20}
                ],
                "trade_execution": {"direction": "BUY"}
            }
        ]

        results = {}

        for config in seed_configs:
            name = config["name"]
            print(f"\n--- Testing {name} ---")

            # Tạo state với context ĐÚNG
            state = self._create_state_with_context()
            state.htf_trend = "BULLISH"
            state.current_session = "LONDON"

            # Tạo events từ sequence
            events = [{"tag": step["tag"]} for step in config["sequence"]]
            state.log_signal_normalize.append({
                "t": 1000,
                "signals": {"events": events}
            })

            df = self._create_minimal_candle_df(1000, 1)
            strategy = TemplateStrategy(config)
            result = strategy.evaluate(df, {}, state)

            results[name] = {
                "triggered": result is not None,
                "score": result["score"] if result else None,
                "context_filters": config["context_filters"],
                "events_sent": events
            }

            print(f"  Context: htf_trend={state.htf_trend}, session={state.current_session}")
            print(f"  Events: {events}")
            print(f"  Triggered: {result is not None}")
            if result:
                print(f"  Score: {result['score']}")

        # Summary
        print("\n" + "="*80)
        print("SUMMARY:")
        print("="*80)
        for name, result in results.items():
            status = "✅ TRIGGERED" if result["triggered"] else "❌ NOT TRIGGERED"
            print(f"{status} - {name}")
            print(f"   Score: {result['score']}, Filters: {result['context_filters']}")

        not_triggered = [n for n, r in results.items() if not r["triggered"]]
        if not_triggered:
            print(f"\n⚠️  Strategies không trigger: {not_triggered}")
            print("   → Kiểm tra xem context filters có bị fail không")

    def test_timing_issues_sequence_completed_t(self):
        """Test timing issues với sequence_completed_t."""
        print("\n" + "="*80)
        print("TEST: Timing Issues (sequence_completed_t vs bar_t)")
        print("="*80)

        config = {
            "name": "TEST_TIMING",
            "min_score_threshold": 0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        # Test 1: Event tại candle 1000, evaluate tại candle 1000 → Phải trigger
        print("\n--- Test 1: Evaluate ĐÚNG timing ---")
        strategy1 = TemplateStrategy(config)
        state1 = self._create_state_with_context()

        state1.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}]}
        })

        df1 = self._create_minimal_candle_df(1000, 1)  # bar_t = 1000
        result1 = strategy1.evaluate(df1, {}, state1)

        print(f"  Event t=1000, bar_t=1000")
        print(f"  Result: {result1 is not None}")

        assert result1 is not None, "MUST trigger when bar_t == sequence_completed_t"

        # Test 2: Event tại candle 1000, evaluate tại candle 1060 → KHÔNG trigger
        print("\n--- Test 2: Evaluate SAI timing (late evaluation) ---")
        strategy2 = TemplateStrategy(config)
        state2 = self._create_state_with_context()

        state2.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}]}
        })

        df2 = self._create_minimal_candle_df(1060, 1)  # bar_t = 1060 (khác 1000!)
        result2 = strategy2.evaluate(df2, {}, state2)

        print(f"  Event t=1000, bar_t=1060")
        print(f"  Result: {result2 is not None}")

        assert result2 is None, "MUST NOT trigger when bar_t != sequence_completed_t"

        print("\n" + "="*80)
        print("✅ Timing logic đang hoạt động ĐÚNG!")
        print("   → Strategy chỉ trigger tại exact candle where sequence completes")
        print("="*80)

    def test_production_executor_flow(self):
        """Test mô phỏng toàn bộ production executor flow."""
        print("\n" + "="*80)
        print("TEST: Production Executor Flow (Full Pipeline)")
        print("="*80)

        # Tạo registry với seed strategies
        registry = StrategyRegistry()

        seed_configs = [
            {
                "name": "TREND_CONT_BULL",
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
                ],
                "trade_execution": {"direction": "BUY"}
            },
            {
                "name": "ORDER_FLOW_BULL",
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
                ],
                "trade_execution": {"direction": "BUY"}
            }
        ]

        for config in seed_configs:
            strat = TemplateStrategy(config)
            registry.register(strat)

        print(f"\n✅ Registered {len(registry._strategies)} strategies")

        # Mô phỏng payload từ Redis stream
        state = self._create_state_with_context()
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up"},
                    {"tag": "sweep_bull"}
                ]
            }
        })

        df = self._create_minimal_candle_df(1000, 1)
        signals_snapshot = {}

        # Evaluate như production
        results = registry.evaluate_all(df, signals_snapshot, state)

        print(f"\n📊 Results:")
        print(f"  Accepted: {len(results)}")
        print(f"  Rejections: {len(registry.get_rejections())}")

        for result in results:
            print(f"  ✅ {result['strategy']} - Score: {result['score']}")

        rejections = registry.get_rejections()
        for rej in rejections:
            print(f"  ❌ {rej['strategy_name']} - Reason: {rej['reason_code']}")

        # Kiểm tra
        assert len(results) > 0, "At least one strategy should trigger"

        print("\n" + "="*80)
        print("✅ Production executor flow hoạt động!")
        print("="*80)


class TestSignalDetectorEventFormats:
    """Test xem signal detectors tạo events với format nào."""

    def test_structure_signal_format(self):
        """Test structure.py signal format."""
        print("\n" + "="*80)
        print("TEST: Structure Signal Format")
        print("="*80)

        # Structure.py tạo signal như thế nào?
        # Từ code structure.py line ~220:
        # return {
        #     "tag": "choch",
        #     "t": int(candle['t']),
        #     "value": tag,  # tag = "choch_up" hoặc "choch_down"
        #     "data": {...}
        # }

        expected_raw_format = {
            "tag": "choch",
            "value": "choch_up",
            "t": 1000,
            "data": {"price": 2000.0}
        }

        print(f"Structure.py tạo RAW format:")
        print(f"  {json.dumps(expected_raw_format, indent=2)}")

        # Signal factory phải normalize thành:
        expected_normalized = {
            "tag": "choch_up",
            "t": 1000
        }

        print(f"\nPhải được normalize thành:")
        print(f"  {json.dumps(expected_normalized, indent=2)}")

        print("\n⚠️  Kiểm tra signal_factory.py để xem có normalize không!")

    def test_sweep_signal_format(self):
        """Test sweep.py signal format."""
        print("\n" + "="*80)
        print("TEST: Sweep Signal Format")
        print("="*80)

        # Sweep.py tạo signal như thế nào?
        # Từ code sweep.py line ~170:
        # triggered_sweep = {
        #     "tag": "sweep",
        #     "value": status_tag,  # VD: "sweep_bull", "stop_hunt_bear"
        #     "t": c_t,
        #     "data": {...}
        # }

        expected_raw_format = {
            "tag": "sweep",
            "value": "sweep_bull",
            "t": 1000,
            "data": {
                "price_swept": 1990.0,
                "source_type": "OB_BULLISH",
                "status": "SWEEP"
            }
        }

        print(f"Sweep.py tạo RAW format:")
        print(f"  {json.dumps(expected_raw_format, indent=2)}")

        expected_normalized = {
            "tag": "sweep_bull",
            "t": 1000
        }

        print(f"\nPhải được normalize thành:")
        print(f"  {json.dumps(expected_normalized, indent=2)}")

        print("\n⚠️  Kiểm tra signal_factory.py để xem có normalize không!")


class TestDebugLoggingHelper:
    """Tạo debug logging để trace execution flow."""

    def _create_state_with_context(self, symbol="XAUUSD"):
        state = SymbolState(symbol)
        state.symbol = symbol
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_add_debug_logging_to_evaluate(self):
        """Test debug logging trong evaluate()."""
        print("\n" + "="*80)
        print("DEBUG LOGGING: Enhanced evaluate() tracing")
        print("="*80)

        config = {
            "name": "DEBUG_TEST",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state_with_context()

        # Step 1: choch_up
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}]}
        })

        df1 = pd.DataFrame([{"t": 1000}])
        result1 = strategy.evaluate(df1, {}, state)

        print("\n--- Step 1: choch_up ---")
        print(f"  log_signal_normalize entries: {len(state.log_signal_normalize)}")
        print(f"  strategy_progress: {json.dumps(state.strategy_progress.get('DEBUG_TEST'), indent=4, default=str)}")
        print(f"  Result: {result1}")

        # Step 2: sweep_bull
        state.log_signal_normalize.append({
            "t": 1060,
            "signals": {"events": [{"tag": "sweep_bull"}]}
        })

        df2 = pd.DataFrame([{"t": 1060}])
        result2 = strategy.evaluate(df2, {}, state)

        print("\n--- Step 2: sweep_bull ---")
        print(f"  log_signal_normalize entries: {len(state.log_signal_normalize)}")
        print(f"  strategy_progress: {json.dumps(state.strategy_progress.get('DEBUG_TEST'), indent=4, default=str)}")
        print(f"  Result: {result2}")

        # Debug info
        print("\n" + "="*80)
        print("DEBUG INFO:")
        print("="*80)
        progress = state.strategy_progress.get("DEBUG_TEST", {})
        print(f"  current_step_index: {progress.get('current_step_index')}")
        print(f"  matched_timestamps: {progress.get('matched_timestamps')}")
        print(f"  last_processed_t: {progress.get('last_processed_t')}")
        print(f"  sequence_completed_t: {progress.get('sequence_completed_t', 0)}")
        print(f"  triggered_t: {progress.get('triggered_t', 0)}")

        if result2:
            print(f"\n✅ Strategy triggered at t={result2['t']}")
            print(f"   Score: {result2['score']}")
        else:
            print(f"\n❌ Strategy NOT triggered")
            print(f"   → Kiểm tra sequence_completed_t vs bar_t")
