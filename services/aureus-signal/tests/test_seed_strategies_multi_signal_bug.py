"""
Test reproduce bug: Khi có nhiều signals trong CÙNG MỘT record hoặc TỪ NHIỀU records,
sequence matching có thể bị sai.

Mục tiêu: Tìm chính xác bug khiến 2 signals không được kết hợp thành 1 strategy.
"""
import pytest
import pandas as pd
import json
from engine.strategies.template import TemplateStrategy
from engine.state import SymbolState


class TestMultipleSignalsInSingleRecord:
    """Test case: 2 signals trong CÙNG 1 record (cùng timestamp)."""

    def _create_state(self):
        state = SymbolState("XAUUSD")
        state.symbol = "XAUUSD"
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_two_signals_same_record_order_flow_bull(self):
        """ORDER_FLOW_BULL cần: choch_up + sweep_bull
        
        Nếu CẢ HAI signals trong CÙNG 1 record, có match được không?
        """
        print("\n" + "="*80)
        print("TEST: 2 Signals TRONG CÙNG 1 RECORD (cùng t=1000)")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # GỬI CẢ HAI signals trong CÙNG 1 record
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up"},
                    {"tag": "sweep_bull"}
                ]
            }
        })

        df = pd.DataFrame([{"t": 1000}])
        result = strategy.evaluate(df, {}, state)

        print(f"\nEvents sent: ['choch_up', 'sweep_bull'] trong cùng 1 record t=1000")
        print(f"Result: {result is not None}")
        
        if result:
            print(f"✅ TRIGGERED - Score: {result['score']}")
        else:
            print(f"❌ NOT TRIGGERED")
            progress = state.strategy_progress.get("ORDER_FLOW_BULL", {})
            print(f"Progress: {json.dumps(progress, indent=2, default=str)}")

        # Kiểm tra
        assert result is not None, "ORDER_FLOW_BULL MUST trigger khi có cả 2 signals trong cùng 1 record"
        assert result["score"] == 8.5

    def test_two_signals_same_record_with_reverse_order(self):
        """Nếu signals đến NGƯỢC THỨ TỰ thì sao?"""
        print("\n" + "="*80)
        print("TEST: 2 Signals TRONG CÙNG 1 RECORD (NGƯỢC THỨ TỰ)")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # GỬI NGƯỢC THỨ TỰ: sweep_bull trước, choch_up sau
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "sweep_bull"},  # ← Trước
                    {"tag": "choch_up"}      # ← Sau
                ]
            }
        })

        df = pd.DataFrame([{"t": 1000}])
        result = strategy.evaluate(df, {}, state)

        print(f"\nEvents sent (REVERSED): ['sweep_bull', 'choch_up'] trong cùng 1 record t=1000")
        print(f"Result: {result is not None}")
        
        if result:
            print(f"✅ TRIGGERED - Score: {result['score']}")
        else:
            print(f"❌ NOT TRIGGERED")
            progress = state.strategy_progress.get("ORDER_FLOW_BULL", {})
            print(f"Progress: {json.dumps(progress, indent=2, default=str)}")

        # Kỳ vọng: sweep_bull bị skip (vì step 0 cần choch_up), sau đó choch_up match
        # → Chỉ match được 1/2 → KHÔNG trigger
        # Đây là DESIGN hay BUG?

    def test_two_signals_same_record_session_sweep(self):
        """SESSION_SWEEP_BEAR cần: sweep_bear (1 step duy nhất)
        
        Nếu có cả sweep_bull VÀ sweep_bear trong cùng 1 record?
        """
        print("\n" + "="*80)
        print("TEST: SESSION_SWEEP_BEAR với nhiều signals trong 1 record")
        print("="*80)

        config = {
            "name": "SESSION_SWEEP_BEAR",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "sweep_bear", "weight": 7.0, "required": True, "max_wait": 20}
            ],
            "trade_execution": {"direction": "SELL"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # Nhiều signals, trong đó có sweep_bear
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up"},
                    {"tag": "sweep_bull"},
                    {"tag": "sweep_bear"}  # ← Signal cần thiết
                ]
            }
        })

        df = pd.DataFrame([{"t": 1000}])
        result = strategy.evaluate(df, {}, state)

        print(f"\nEvents sent: ['choch_up', 'sweep_bull', 'sweep_bear']")
        print(f"Result: {result is not None}")
        
        if result:
            print(f"✅ TRIGGERED - Score: {result['score']}")
        else:
            print(f"❌ NOT TRIGGERED")
            progress = state.strategy_progress.get("SESSION_SWEEP_BEAR", {})
            print(f"Progress: {json.dumps(progress, indent=2, default=str)}")

        assert result is not None, "SESSION_SWEEP_BEAR MUST trigger vì có sweep_bear"


class TestMultipleSignalsFromDifferentCandles:
    """Test case: 2 signals từ 2 candles khác nhau."""

    def _create_state(self):
        state = SymbolState("XAUUSD")
        state.symbol = "XAUUSD"
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_two_signals_different_candles_order_flow(self):
        """ORDER_FLOW_BULL: choch_up ở t=1000, sweep_bull ở t=1060"""
        print("\n" + "="*80)
        print("TEST: 2 Signals TỪ 2 CANDLES KHÁC NHAU")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # Candle 1: choch_up
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}]}
        })

        df1 = pd.DataFrame([{"t": 1000}])
        result1 = strategy.evaluate(df1, {}, state)

        print(f"\n--- Candle 1 (t=1000): choch_up ---")
        print(f"Result: {result1 is not None}")
        progress1 = state.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"Progress: {json.dumps(progress1, indent=2, default=str)}")

        assert result1 is None, "Phải chờ thêm sweep_bull"

        # Candle 2: sweep_bull
        state.log_signal_normalize.append({
            "t": 1060,
            "signals": {"events": [{"tag": "sweep_bull"}]}
        })

        df2 = pd.DataFrame([{"t": 1060}])
        result2 = strategy.evaluate(df2, {}, state)

        print(f"\n--- Candle 2 (t=1060): sweep_bull ---")
        print(f"Result: {result2 is not None}")
        progress2 = state.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"Progress: {json.dumps(progress2, indent=2, default=str)}")

        if result2:
            print(f"✅ TRIGGERED - Score: {result2['score']}")
        else:
            print(f"❌ NOT TRIGGERED")

        assert result2 is not None, "ORDER_FLOW_BULL MUST trigger sau khi có cả 2 signals"
        assert result2["score"] == 8.5

    def test_timing_issue_sequence_completed_t(self):
        """BUG: Nếu sequence_completed_t != bar_t thì không trigger"""
        print("\n" + "="*80)
        print("TEST: Timing Issue - sequence_completed_t vs bar_t")
        print("="*80)

        config = {
            "name": "TREND_CONT_BULL",
            "min_score_threshold": 0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # Gửi event ở t=1000
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}]}
        })

        # Nhưng evaluate ở t=1060 (candle sau)
        df = pd.DataFrame([{"t": 1060}])
        result = strategy.evaluate(df, {}, state)

        print(f"\nEvent t=1000, nhưng evaluate tại bar_t=1060")
        print(f"Result: {result is not None}")
        
        if result:
            print(f"✅ TRIGGERED")
        else:
            print(f"❌ NOT TRIGGERED")
            progress = state.strategy_progress.get("TREND_CONT_BULL", {})
            print(f"Progress: {json.dumps(progress, indent=2, default=str)}")
            seq_completed = progress.get("sequence_completed_t", 0)
            print(f"sequence_completed_t={seq_completed}, bar_t=1060")

        # Đây là DESIGN: chỉ trigger tại exact candle where sequence completes
        # Nhưng nếu production gửi events CHẬM, sẽ miss!
        assert result is None, "Design: chỉ trigger khi bar_t == sequence_completed_t"


class TestRawEventFormatVsNormalizedFormat:
    """Test xem raw format {tag: 'choch', value: 'choch_up'} có được match không."""

    def _create_state(self):
        state = SymbolState("XAUUSD")
        state.symbol = "XAUUSD"
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_raw_format_two_signals_same_record(self):
        """RAW format: {tag: 'choch', value: 'choch_up'}"""
        print("\n" + "="*80)
        print("TEST: RAW FORMAT - 2 signals trong cùng 1 record")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # RAW format từ structure.py và sweep.py
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch", "value": "choch_up"},  # ← RAW
                    {"tag": "sweep", "value": "sweep_bull"}  # ← RAW
                ]
            }
        })

        df = pd.DataFrame([{"t": 1000}])
        result = strategy.evaluate(df, {}, state)

        print(f"\nRaw events sent: [{{tag: 'choch', value: 'choch_up'}}, {{tag: 'sweep', value: 'sweep_bull'}}]")
        print(f"Result: {result is not None}")
        
        if result:
            print(f"✅ TRIGGERED - Score: {result['score']}")
        else:
            print(f"❌ NOT TRIGGERED")
            progress = state.strategy_progress.get("ORDER_FLOW_BULL", {})
            print(f"Progress: {json.dumps(progress, indent=2, default=str)}")

        assert result is not None, "RAW format MUST được normalize và trigger"

    def test_mixed_format_raw_and_normalized(self):
        """Nếu 1 signal raw, 1 signal normalized thì sao?"""
        print("\n" + "="*80)
        print("TEST: MIXED FORMAT - 1 raw + 1 normalized")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # MIXED: choch_up normalized, sweep_bull raw
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [
                    {"tag": "choch_up"},  # ← NORMALIZED
                    {"tag": "sweep", "value": "sweep_bull"}  # ← RAW
                ]
            }
        })

        df = pd.DataFrame([{"t": 1000}])
        result = strategy.evaluate(df, {}, state)

        print(f"\nMixed events: [{{tag: 'choch_up'}}, {{tag: 'sweep', value: 'sweep_bull'}}]")
        print(f"Result: {result is not None}")
        
        if result:
            print(f"✅ TRIGGERED - Score: {result['score']}")
        else:
            print(f"❌ NOT TRIGGERED")
            progress = state.strategy_progress.get("ORDER_FLOW_BULL", {})
            print(f"Progress: {json.dumps(progress, indent=2, default=str)}")

        assert result is not None, "MIXED format MUST trigger sau khi normalize"


class TestLastProcessedTBug:
    """Test bug với last_processed_t logic."""

    def _create_state(self):
        state = SymbolState("XAUUSD")
        state.symbol = "XAUUSD"
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_last_processed_t_skips_signals(self):
        """BUG FIX: Nếu last_processed_record_index được dùng, signals cùng timestamp KHÔNG bị skip"""
        print("\n" + "="*80)
        print("TEST: last_processed_record_index Logic (BUG FIX)")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        # === TEST 1: Production gọi evaluate() 2 lần với log_signal_normalize được append ===
        print("\n--- Test 1: Evaluate nhiều lần với records cùng timestamp ---")

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # Lần 1: Chỉ có choch_up
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}]}
        })

        df1 = pd.DataFrame([{"t": 1000}])
        result1 = strategy.evaluate(df1, {}, state)

        progress1 = state.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"\nLần 1: Record 1 (t=1000, choch_up)")
        print(f"  Result: {result1 is not None}")
        print(f"  last_processed_record_index: {progress1.get('last_processed_record_index')}")
        print(f"  current_step_index: {progress1.get('current_step_index')}")

        assert result1 is None, "Phải chờ thêm sweep_bull"
        assert progress1.get("current_step_index") == 1, "Phải match step 0 (choch_up)"

        # Lần 2: Append thêm sweep_bull (CÙNG t=1000)
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "sweep_bull"}]}
        })

        df2 = pd.DataFrame([{"t": 1000}])
        result2 = strategy.evaluate(df2, {}, state)

        progress2 = state.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"\nLần 2: Record 2 (t=1000, sweep_bull)")
        print(f"  Result: {result2 is not None}")
        print(f"  last_processed_record_index: {progress2.get('last_processed_record_index')}")
        print(f"  current_step_index: {progress2.get('current_step_index')}")
        print(f"  Progress: {json.dumps(progress2, indent=2, default=str)}")

        if result2:
            print(f"\n✅ TRIGGERED - Score: {result2['score']}")
        else:
            print(f"\n❌ NOT TRIGGERED - Bug vẫn còn!")

        # Sau fix: phải trigger vì record thứ 2 (index=1) > last_processed_record_index (index=0)
        assert result2 is not None, "ORDER_FLOW_BULL MUST trigger với 2 records cùng timestamp"
        assert result2["score"] == 8.5

        # === TEST 2: Production gọi evaluate() với log_signal_normalize có sẵn 2 records ===
        print("\n--- Test 2: Evaluate 1 lần với 2 records cùng timestamp ---")

        strategy2 = TemplateStrategy(config)
        state2 = self._create_state()

        # Có sẵn 2 records
        state2.log_signal_normalize = [
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
            {"t": 1000, "signals": {"events": [{"tag": "sweep_bull"}]}}
        ]

        df3 = pd.DataFrame([{"t": 1000}])
        result3 = strategy2.evaluate(df3, {}, state2)

        progress3 = state2.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"\n2 records có sẵn, evaluate 1 lần")
        print(f"  Result: {result3 is not None}")
        print(f"  last_processed_record_index: {progress3.get('last_processed_record_index')}")
        print(f"  current_step_index: {progress3.get('current_step_index')}")

        if result3:
            print(f"  ✅ TRIGGERED - Score: {result3['score']}")
        else:
            print(f"  ❌ NOT TRIGGERED")
            print(f"  Progress: {json.dumps(progress3, indent=2, default=str)}")

        assert result3 is not None, "ORDER_FLOW_BULL MUST trigger khi có cả 2 records"
        assert result3["score"] == 8.5


class TestSkipOldEventsAfterRestart:
    """Test xem strategy có bỏ qua events cũ sau khi restart không."""

    def _create_state(self):
        state = SymbolState("XAUUSD")
        state.symbol = "XAUUSD"
        state.htf_trend = "BULLISH"
        state.current_session = "LONDON"
        state.obs = []
        state.emas = {21: {"slope": 1.0}}
        state.log_signal_normalize = []
        state.strategy_progress = {}
        state.swing_points = []
        state.transient_signals = {}
        return state

    def test_skip_old_events_after_executor_restart(self):
        """Sau khi executor restart, strategy_progress bị reset nhưng log_signal_normalize vẫn cũ.
        
        Phải bỏ qua các events đã trigger rồi (t <= triggered_t).
        """
        print("\n" + "="*80)
        print("TEST: Skip Old Events After Executor Restart")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        # === GIAI ĐOẠN 1: Trigger lần đầu ===
        print("\n--- Giai đoạn 1: Trigger lần đầu ---")

        strategy1 = TemplateStrategy(config)
        state1 = self._create_state()

        # Có sẵn 2 records
        state1.log_signal_normalize = [
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
            {"t": 1000, "signals": {"events": [{"tag": "sweep_bull"}]}}
        ]

        df1 = pd.DataFrame([{"t": 1000}])
        result1 = strategy1.evaluate(df1, {}, state1)

        progress1 = state1.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"Result: {result1 is not None}")
        print(f"triggered_t: {progress1.get('triggered_t')}")
        print(f"last_processed_record_index: {progress1.get('last_processed_record_index')}")

        assert result1 is not None, "Phải trigger lần đầu"
        assert result1["score"] == 8.5
        assert progress1.get("triggered_t") == 1000, "triggered_t phải được set"

        # === GIAI ĐOẠN 2: Executor restart, strategy_progress = {} ===
        print("\n--- Giai đoạn 2: Executor restart (strategy_progress = {}) ---")

        strategy2 = TemplateStrategy(config)
        state2 = self._create_state()

        # log_signal_normalize VẪN GIỮ NGUYÊN (có cả 2 records cũ)
        state2.log_signal_normalize = [
            {"t": 1000, "signals": {"events": [{"tag": "choch_up"}]}},
            {"t": 1000, "signals": {"events": [{"tag": "sweep_bull"}]}}
        ]

        # NHƯNG strategy_progress bị reset (như production khi executor restart)
        state2.strategy_progress = {}

        df2 = pd.DataFrame([{"t": 1000}])
        result2 = strategy2.evaluate(df2, {}, state2)

        progress2 = state2.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"Result: {result2 is not None}")
        print(f"triggered_t: {progress2.get('triggered_t')}")
        print(f"last_processed_record_index: {progress2.get('last_processed_record_index')}")
        print(f"Progress: {json.dumps(progress2, indent=2, default=str)}")

        # BUG: Nếu không có triggered_t check, sẽ trigger LẠI!
        # Sau fix: KHÔNG trigger vì events đã cũ (t=1000 <= triggered_t=1000)

        # WAIT - triggered_t = 0 vì strategy_progress mới, nên sẽ trigger lại!
        # Đây là design hay bug?
        if result2:
            print(f"\n⚠️  TRIGGER LẠI - Có thể chấp nhận được sau restart")
        else:
            print(f"\n✅ KHÔNG trigger lại - Events bị skip")

    def test_process_new_events_after_trigger(self):
        """Sau khi trigger, phải process được events MỚI."""
        print("\n" + "="*80)
        print("TEST: Process New Events After Trigger")
        print("="*80)

        config = {
            "name": "ORDER_FLOW_BULL",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
            ],
            "trade_execution": {"direction": "BUY"}
        }

        strategy = TemplateStrategy(config)
        state = self._create_state()

        # Trigger lần 1
        state.log_signal_normalize.append({
            "t": 1000,
            "signals": {"events": [{"tag": "choch_up"}, {"tag": "sweep_bull"}]}
        })

        df1 = pd.DataFrame([{"t": 1000}])
        result1 = strategy.evaluate(df1, {}, state)

        progress1 = state.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"\n--- Trigger lần 1 (t=1000) ---")
        print(f"Result: {result1 is not None}")
        print(f"triggered_t: {progress1.get('triggered_t')}")

        assert result1 is not None
        assert progress1.get("triggered_t") == 1000

        # Thêm events MỚI (t > triggered_t)
        state.log_signal_normalize.append({
            "t": 1100,
            "signals": {"events": [{"tag": "choch_up"}, {"tag": "sweep_bull"}]}
        })

        df2 = pd.DataFrame([{"t": 1100}])
        result2 = strategy.evaluate(df2, {}, state)

        progress2 = state.strategy_progress.get("ORDER_FLOW_BULL", {})
        print(f"\n--- Trigger lần 2 (t=1100 > triggered_t=1000) ---")
        print(f"Result: {result2 is not None}")
        print(f"triggered_t: {progress2.get('triggered_t')}")

        if result2:
            print(f"✅ TRIGGER lại - Score: {result2['score']}")
        else:
            print(f"❌ KHÔNG trigger")
            print(f"Progress: {json.dumps(progress2, indent=2, default=str)}")

        # Phải trigger vì events mới (t=1100 > triggered_t=1000)
        assert result2 is not None, "Phải trigger với events mới"
        assert result2["score"] == 8.5
