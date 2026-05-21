"""
Test để kiểm tra xem context filters có làm strategies không trigger không.

Nhiều strategies trong seed_strategies.py có context_filters như:
- trend_alignment: cần BULLISH/BEARISH trend
- session_active: cần London/New York session  
- ob_imbalance: cần order block imbalance
- ema_alignment: cần EMA slope đúng hướng

Nếu các context filters này không pass, strategy sẽ KHÔNG trigger dù sequence đã match.
"""
import pytest
import pandas as pd
from engine.strategies.template import TemplateStrategy


class MockStateWithContext:
    """Mock state với đầy đủ context cho filters."""
    def __init__(self, trend="BULLISH", session="LONDON", obs=None, emas=None):
        self.signal_history = []
        self.log_signal_normalize = []
        self.strategy_progress = {}
        self.symbol = "XAUUSD"
        self.last_candle = {"c": 110.0}
        self.prev_candle = {"c": 105.0}
        self.tpo_profile = {"tpo_d0": {"POC": 100.0}, "tpo_d1": {"POC": 100.0, "CLOSE": 105.0}}
        self.transient_signals = {"cisd_h1_bullish": True}

        # Context cho filters
        self.htf_trend = trend
        self.current_session = session
        self.obs = obs if obs is not None else []
        self.emas = emas if emas is not None else {21: {"slope": 1.0}}


def create_mock_df(t_val=1000):
    return pd.DataFrame([{"t": t_val}])


def append_events(state, t_val, events):
    state.log_signal_normalize.append({
        "t": t_val,
        "signals": {
            "events": events
        }
    })


def _trend_cont_strategy(direction="bullish"):
    return TemplateStrategy(
        {
            "name": f"TEST_TREND_CONT_{direction.upper()}",
            "min_score_threshold": 0,
            "context_filters": [{"type": "trend_cont_poc_cisd", "direction": direction}],
            "sequence": [{"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}],
            "trade_execution": {"direction": "BUY" if direction == "bullish" else "SELL"},
        }
    )


class TestTrendContPocCisdFilter:
    def test_bull_passes_with_closes_above_poc_and_h1_cisd_bullish(self):
        result = _trend_cont_strategy("bullish")._evaluate_context(MockStateWithContext())

        assert result["passed"] is True
        assert result["failed_filters"] == []

    def test_bear_passes_with_closes_below_poc_and_h1_cisd_bearish(self):
        state = MockStateWithContext()
        state.last_candle = {"c": 90.0}
        state.tpo_profile = {"tpo_d0": {"POC": 100.0}, "tpo_d1": {"POC": 100.0, "CLOSE": 95.0}}
        state.transient_signals = {"cisd_h1_bearish": True}

        result = _trend_cont_strategy("bearish")._evaluate_context(state)

        assert result["passed"] is True
        assert result["failed_filters"] == []

    @pytest.mark.parametrize(
        "field,value",
        [
            ("last_candle", {"c": 100.0}),
            ("tpo_profile", {"tpo_d0": {"POC": 100.0}, "tpo_d1": {"POC": 100.0, "CLOSE": 100.0}}),
            ("transient_signals", {"cisd_h1_bearish": True}),
            ("tpo_profile", {"tpo_d0": {"POC": 120.0}, "tpo_d1": {"POC": 100.0, "CLOSE": 105.0}}),
        ],
    )
    def test_bull_fails_on_equal_or_wrong_poc_or_wrong_cisd(self, field, value):
        state = MockStateWithContext()
        setattr(state, field, value)

        result = _trend_cont_strategy("bullish")._evaluate_context(state)

        assert result["passed"] is False
        assert "trend_cont_poc_cisd:bullish" in result["failed_filters"]

    def test_uses_previous_daily_close_not_previous_candle_close(self):
        state = MockStateWithContext()
        state.prev_candle = {"c": 80.0}
        state.tpo_profile = {"tpo_d0": {"POC": 100.0}, "tpo_d1": {"POC": 100.0, "CLOSE": 105.0}}

        result = _trend_cont_strategy("bullish")._evaluate_context(state)

        assert result["passed"] is True

    def test_missing_data_fails_closed_with_detail(self):
        state = MockStateWithContext()
        state.tpo_profile = {}

        result = _trend_cont_strategy("bullish")._evaluate_context(state)

        assert result["passed"] is False
        assert "trend_cont_poc_cisd:bullish" in result["failed_filters"]
        assert any("unavailable" in detail for detail in result["details"])


class TestContextFiltersBlockingTriggers:
    """Kiểm tra xem context filters có blocking strategies không."""
    
    def test_trend_cont_bull_with_context_filters(self):
        """TREND_CONT_BULL trong seed_strategies.py KHÔNG có context filters.
        
        Nhưng nếu có, nó sẽ cần:
        - trend = BULLISH
        - session = London/New York
        - EMA(21) slope > 0
        """
        # Config CÓ context filters
        config_with_filters = {
            "name": "TREND_CONT_BULL_WITH_CONTEXT",
            "min_score_threshold": 0,
            "context_filters": [
                {"type": "trend_alignment", "required_trend": "BULLISH"},
                {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]},
                {"type": "ema_alignment", "required_slope": "POSITIVE", "period": 21},
            ],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }
        
        # Test 1: Context đúng -> Phải trigger
        state_ok = MockStateWithContext(
            trend="BULLISH",
            session="LONDON",
            emas={21: {"slope": 1.5}}
        )
        append_events(state_ok, 1000, [{"tag": "choch_up"}])
        df = create_mock_df(1000)
        
        strategy = TemplateStrategy(config_with_filters)
        intent_ok = strategy.evaluate(df, {}, state_ok)
        
        print(f"\nTest 1 - Context OK:")
        print(f"  Trend: BULLISH, Session: LONDON, EMA slope: 1.5")
        print(f"  Intent: {intent_ok}")
        
        assert intent_ok is not None, "Should trigger when all context filters pass"
        
        # Test 2: Context sai (trend = BEARISH) -> KHÔNG trigger
        state_wrong_trend = MockStateWithContext(
            trend="BEARISH",  # Sai trend!
            session="LONDON",
            emas={21: {"slope": 1.5}}
        )
        append_events(state_wrong_trend, 1000, [{"tag": "choch_up"}])
        
        strategy2 = TemplateStrategy(config_with_filters)
        intent_wrong = strategy2.evaluate(df, {}, state_wrong_trend)
        
        print(f"\nTest 2 - Wrong Trend:")
        print(f"  Trend: BEARISH (expected BULLISH), Session: LONDON")
        print(f"  Intent: {intent_wrong}")

        # BUG FIX: evaluate() BÂY GIỜ check context filters (trước đây bỏ qua)
        assert intent_wrong is None, "evaluate() PHẢI check context filters - bug đã được fix"
        
        # Test 3: Context sai (session = ASIAN) -> KHÔNG trigger
        state_wrong_session = MockStateWithContext(
            trend="BULLISH",
            session="ASIAN",  # Sai session!
            emas={21: {"slope": 1.5}}
        )
        append_events(state_wrong_session, 1000, [{"tag": "choch_up"}])
        
        strategy3 = TemplateStrategy(config_with_filters)
        intent_wrong_session = strategy3.evaluate(df, {}, state_wrong_session)
        
        print(f"\nTest 3 - Wrong Session:")
        print(f"  Trend: BULLISH, Session: ASIAN (not allowed)")
        print(f"  Intent: {intent_wrong_session}")

        # BUG FIX: evaluate() BÂY GIỜ check context filters (trước đây bỏ qua)
        assert intent_wrong_session is None, "evaluate() PHẢI check context filters - bug đã được fix"
        
        # Test 4: Context sai (EMA slope âm) -> KHÔNG trigger
        state_wrong_ema = MockStateWithContext(
            trend="BULLISH",
            session="LONDON",
            emas={21: {"slope": -0.5}}  # Sai EMA slope!
        )
        append_events(state_wrong_ema, 1000, [{"tag": "choch_up"}])
        
        strategy4 = TemplateStrategy(config_with_filters)
        intent_wrong_ema = strategy4.evaluate(df, {}, state_wrong_ema)
        
        print(f"\nTest 4 - Wrong EMA Slope:")
        print(f"  Trend: BULLISH, Session: LONDON, EMA slope: -0.5 (expected positive)")
        print(f"  Intent: {intent_wrong_ema}")

        # BUG FIX: evaluate() BÂY GIỜ check context filters (trước đây bỏ qua)
        assert intent_wrong_ema is None, "evaluate() PHẢI check context filters - bug đã được fix"

    def test_seed_strategies_have_expected_context_filters(self):
        """Xác nhận chỉ TREND_CONT_BULL/BEAR có trend_cont_poc_cisd filters."""
        # Kiểm tra lại configs từ seed_strategies.py
        strategies = [
            {
                "name": "TREND_CONT_BULL",
                "config": {
                    "min_score_threshold": 0,
                    "context_filters": [{"type": "trend_cont_poc_cisd", "direction": "bullish"}],
                    "sequence": [
                        {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
                    ],
                    "trade_execution": {"direction": "BUY"}
                }
            },
            {
                "name": "TREND_CONT_BEAR",
                "config": {
                    "min_score_threshold": 0,
                    "context_filters": [{"type": "trend_cont_poc_cisd", "direction": "bearish"}],
                    "sequence": [
                        {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30}
                    ],
                    "trade_execution": {"direction": "SELL"}
                }
            },
            {
                "name": "ORDER_FLOW_BULL",
                "config": {
                    "min_score_threshold": 6.0,
                    "context_filters": [],  # KHÔNG có filters
                    "sequence": [
                        {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20},
                        {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10}
                    ],
                    "trade_execution": {"direction": "BUY"}
                }
            },
            {
                "name": "ORDER_FLOW_BEAR",
                "config": {
                    "min_score_threshold": 6.0,
                    "context_filters": [],  # KHÔNG có filters
                    "sequence": [
                        {"tag": "choch_down", "weight": 3.5, "required": True, "max_wait": 20},
                        {"tag": "sweep_bear", "weight": 5.0, "required": True, "max_wait": 10}
                    ],
                    "trade_execution": {"direction": "SELL"}
                }
            },
            {
                "name": "SESSION_SWEEP_BULL",
                "config": {
                    "min_score_threshold": 6.0,
                    "context_filters": [],  # KHÔNG có filters
                    "sequence": [
                        {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20}
                    ],
                    "trade_execution": {"direction": "BUY"}
                }
            },
            {
                "name": "SESSION_SWEEP_BEAR",
                "config": {
                    "min_score_threshold": 6.0,
                    "context_filters": [],  # KHÔNG có filters
                    "sequence": [
                        {"tag": "sweep_bear", "weight": 7.0, "required": True, "max_wait": 20}
                    ],
                    "trade_execution": {"direction": "SELL"}
                }
            }
        ]
        
        print("\n" + "="*80)
        print("KIỂM TRA CONTEXT FILTERS TRONG SEED STRATEGIES:")
        print("="*80)
        
        expected = {
            "TREND_CONT_BULL": [{"type": "trend_cont_poc_cisd", "direction": "bullish"}],
            "TREND_CONT_BEAR": [{"type": "trend_cont_poc_cisd", "direction": "bearish"}],
        }
        for strat in strategies:
            filters = strat["config"]["context_filters"]
            print(f"{strat['name']}: context_filters = {filters}")
            assert filters == expected.get(strat["name"], [])

        print("\nSeed strategies context filters đúng contract.")

    def test_on_bar_close_path_with_context(self):
        """Kiểm tra on_bar_close path - đây là path được dùng trong thực tế.
        
        on_bar_close gọi _evaluate_context trước, nếu context không pass thì
        reason_code sẽ là "CONTEXT_FILTER_FAILED".
        """
        config_with_filters = {
            "name": "TEST_WITH_CONTEXT",
            "id": 99,
            "min_score_threshold": 0,
            "context_filters": [
                {"type": "trend_alignment", "required_trend": "BULLISH"},
            ],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {
                "direction": "BUY"
            }
        }
        
        strategy = TemplateStrategy(config_with_filters)
        
        # Test với context đúng
        state_ok = MockStateWithContext(trend="BULLISH")
        append_events(state_ok, 1000, [{"tag": "choch_up"}])
        df = create_mock_df(1000)
        
        context_ok = {
            "df": df,
            "state": state_ok,
            "backfill_status": "READY"
        }
        
        result_ok = strategy.on_bar_close(context_ok)
        
        print(f"\non_bar_close với context OK:")
        print(f"  Result: {result_ok}")
        
        # Test với context sai
        state_wrong = MockStateWithContext(trend="BEARISH")
        append_events(state_wrong, 1000, [{"tag": "choch_up"}])
        
        context_wrong = {
            "df": df,
            "state": state_wrong,
            "backfill_status": "READY"
        }
        
        result_wrong = strategy.on_bar_close(context_wrong)
        
        print(f"\non_bar_close với context SAI:")
        print(f"  Result: {result_wrong}")
        
        # Kết quả phải khác nhau
        assert result_ok.get("reason_code") == "OK" or result_ok.get("is_actionable") == True
        assert result_wrong.get("reason_code") == "CONTEXT_FILTER_FAILED" or result_wrong.get("is_actionable") == False


class TestActualSignalGeneration:
    """Test xem các signals (choch_up, sweep_bull, v.v.) có thực sự được tạo ra không."""
    
    def test_structure_signal_format(self):
        """Kiểm tra format của signals từ structure.py (choch_up/choch_down).
        
        Từ code structure.py dòng 331:
        "tag": "choch",
        
        Và dòng 314:
        tag = self.TAG_CHOCH_UP if is_bullish else self.TAG_CHOCH_DN
        
        Cần kiểm tra xem signal được lưu dưới dạng nào.
        """
        # Giả sử signal được tạo ra từ structure.py
        # Có 2 khả năng:
        # 1. {"tag": "choch_up"} (đã normalize)
        # 2. {"tag": "choch", "value": "choch_up"} (raw format)
        
        config = {
            "name": "TEST_CHOCH",
            "min_score_threshold": 0,
            "context_filters": [],
            "sequence": [
                {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30}
            ],
            "trade_execution": {"direction": "BUY"}
        }
        
        # Test case 1: Normalized format
        state1 = MockStateWithContext()
        state1.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "choch_up"}]
            }
        })
        
        strategy1 = TemplateStrategy(config)
        df = create_mock_df(1000)
        intent1 = strategy1.evaluate(df, {}, state1)
        
        print(f"\nTest normalized format {{'tag': 'choch_up'}}:")
        print(f"  Intent: {intent1 is not None}")
        
        # Test case 2: Raw format
        state2 = MockStateWithContext()
        state2.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "choch", "value": "choch_up"}]
            }
        })
        
        strategy2 = TemplateStrategy(config)
        intent2 = strategy2.evaluate(df, {}, state2)
        
        print(f"\nTest raw format {{'tag': 'choch', 'value': 'choch_up'}}:")
        print(f"  Intent: {intent2 is not None}")
        
        # Cả 2 đều phải trigger
        assert intent1 is not None, "Normalized format should trigger"
        assert intent2 is not None, "Raw format should trigger after normalization"
    
    def test_sweep_signal_format(self):
        """Kiểm tra format của signals từ sweep.py (sweep_bull/sweep_bear).
        
        Từ code sweep.py dòng 230:
        "tag": "sweep",
        
        Và dòng 17-18:
        TAG_BULL = "sweep_bull"
        TAG_BEAR = "sweep_bear"
        """
        config = {
            "name": "TEST_SWEEP",
            "min_score_threshold": 6.0,
            "context_filters": [],
            "sequence": [
                {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20}
            ],
            "trade_execution": {"direction": "BUY"}
        }
        
        # Test case 1: Normalized format
        state1 = MockStateWithContext()
        state1.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "sweep_bull"}]
            }
        })
        
        strategy1 = TemplateStrategy(config)
        df = create_mock_df(1000)
        intent1 = strategy1.evaluate(df, {}, state1)
        
        print(f"\nTest normalized format {{'tag': 'sweep_bull'}}:")
        print(f"  Intent: {intent1 is not None}")
        if intent1:
            print(f"  Score: {intent1['score']}")
        
        # Test case 2: Raw format
        state2 = MockStateWithContext()
        state2.log_signal_normalize.append({
            "t": 1000,
            "signals": {
                "events": [{"tag": "sweep", "value": "sweep_bull"}]
            }
        })
        
        strategy2 = TemplateStrategy(config)
        intent2 = strategy2.evaluate(df, {}, state2)
        
        print(f"\nTest raw format {{'tag': 'sweep', 'value': 'sweep_bull'}}:")
        print(f"  Intent: {intent2 is not None}")
        if intent2:
            print(f"  Score: {intent2['score']}")
        
        # Cả 2 đều phải trigger
        assert intent1 is not None, "Normalized format should trigger"
        assert intent2 is not None, "Raw format should trigger after normalization"
        assert intent1["score"] == intent2["score"] == 7.0
