"""Tests for formatters.py"""
import html
from formatters import format_signal_event, format_strategy_match


def test_format_signal_event_basic():
    """Verify output contains emoji, SIGNAL ALERT, symbol, signal bullets."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"zigzag_state": "SWING_HIGH", "ob_state": "BULLISH"},
            "session": "NEW_YORK",
        },
    }
    result = format_signal_event(event)
    assert "📊" in result
    assert "SIGNAL ALERT" in result
    assert "XAUUSD" in result
    assert "• <b>zigzag_state</b>: SWING_HIGH" in result
    assert "• <b>ob_state</b>: BULLISH" in result
    assert "NEW_YORK" in result


def test_format_signal_event_missing_session():
    """Verify session line is absent when session=None."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "BTCUSD",
        "t": 1712345678,
        "data": {
            "signals": {"test": "value"},
            "session": None,
        },
    }
    result = format_signal_event(event)
    assert "Session:" not in result
    assert "📊" in result
    assert "BTCUSD" in result


def test_format_signal_event_empty_signals():
    """Verify (no active signals) shown when signals dict is empty."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "EURUSD",
        "t": 1712345678,
        "data": {
            "signals": {},
            "session": "LONDON",
        },
    }
    result = format_signal_event(event)
    assert result == ""


def test_format_strategy_match_buy():
    """Verify 🟢, BUY, SL/TP values present."""
    event = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "strategy": "CHOCH_UP",
            "strategy_id": 10,
            "side": "BUY",
            "entry_type": "MARKET",
            "sl": 1950.50,
            "tp": 1970.00,
            "size_value": 1.0,
            "reason_code": "OK",
        },
    }
    result = format_strategy_match(event)
    assert "🎯" in result
    assert "STRATEGY MATCH" in result
    assert "🟢" in result
    assert "BUY" in result
    assert "1950.5" in result
    assert "1970.0" in result
    assert "CHOCH_UP" in result
    assert "#10" in result


def test_format_strategy_match_sell():
    """Verify 🔴, SELL present."""
    event = {
        "type": "STRATEGY_MATCH",
        "symbol": "BTCUSD",
        "t": 1712345678,
        "data": {
            "strategy": "CHOCH_DOWN",
            "strategy_id": 11,
            "side": "SELL",
            "entry_type": "LIMIT",
            "sl": 70000.0,
            "tp": 65000.0,
            "size_value": 0.5,
            "reason_code": "OK",
        },
    }
    result = format_strategy_match(event)
    assert "🔴" in result
    assert "SELL" in result


def test_format_strategy_match_missing_sl_tp():
    """Verify N/A for missing SL/TP values."""
    event = {
        "type": "STRATEGY_MATCH",
        "symbol": "ETHUSD",
        "t": 1712345678,
        "data": {
            "strategy": "TEST_STRAT",
            "strategy_id": 99,
            "side": "BUY",
            "entry_type": "MARKET",
            "size_value": 1.0,
            "reason_code": "OK",
        },
    }
    result = format_strategy_match(event)
    assert "SL: N/A" in result
    assert "TP: N/A" in result


def test_format_functions_escape_html():
    """Verify <script> in input becomes &lt;script&gt; in output."""
    event_signal = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"<script>alert('xss')</script>": "value"},
            "session": "LONDON",
        },
    }
    result_signal = format_signal_event(event_signal)
    assert "<script>" not in result_signal
    assert "&lt;script&gt;" in result_signal

    event_strategy = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "strategy": "<script>alert('xss')</script>",
            "strategy_id": 1,
            "side": "BUY",
            "entry_type": "MARKET",
            "sl": 100.0,
            "tp": 200.0,
            "size_value": 1.0,
            "reason_code": "<b>bold</b>",
        },
    }
    result_strategy = format_strategy_match(event_strategy)
    assert "<script>" not in result_strategy
    assert "&lt;script&gt;" in result_strategy


def test_format_functions_under_4096_chars():
    """Verify output length < 4096 (Telegram message limit)."""
    event_signal = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {f"signal_{i}": f"value_{i}" for i in range(50)},
            "session": "NEW_YORK",
        },
    }
    result_signal = format_signal_event(event_signal)
    assert len(result_signal) < 4096

    event_strategy = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "strategy": "CHOCH_UP",
            "strategy_id": 10,
            "side": "BUY",
            "entry_type": "MARKET",
            "sl": 1950.50,
            "tp": 1970.00,
            "size_value": 1.0,
            "reason_code": "OK",
        },
    }
    result_strategy = format_strategy_match(event_strategy)
    assert len(result_strategy) < 4096


def test_format_signal_event_with_indicator_snapshot():
    """SIG-03: Verify indicator snapshot section rendered in message."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"choch_up": {"value": "choch_up"}},
            "session": "NEW_YORK",
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", " 📈", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "BULLISH",
                "tpo_d1": {
                    "POC": 2010.1,
                    "VAH": 2012.3,
                    "VAL": 2008.7,
                    "shape": "D",
                    "shape_confidence_pct": 82.5,
                },
                "tpo_h1": {"POC": 2009.9, "VAH": 2011.0, "VAL": 2008.2},
                "tpo_m30": {"POC": 2010.0, "VAH": 2010.8, "VAL": 2009.1},
            },
        },
    }
    result = format_signal_event(event)
    assert "📈 Indicator Snapshot" in result
    assert "EMA(21/34/55/89/100/200)" in result
    assert "2341.20" in result
    assert "ATR(14)" in result
    assert "12.34" in result
    assert "Vol SMA(20)" in result
    assert "HTF Trend" in result
    assert "TPO" in result
    assert "POC:2010.10" in result
    assert "VAH:2012.30" in result
    assert "VAL:2008.70" in result
    assert "Shape:D (heuristic 82.5%)" in result
    assert "probability" not in result.lower()
    assert "win rate" not in result.lower()
    assert "edge" not in result.lower()
    assert "score contribution" not in result.lower()
    assert "🟢" in result
    assert "📈" in result
    assert len(result) <= 4095


def test_format_signal_event_tpo_shape_low_confidence_safe_wording():
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"choch_up": {"value": "choch_up"}},
            "indicator_snapshot": {
                "emas": {"periods": [21], "values": [2341.20], "cross_markers": [""]},
                "tpo_d1": {"POC": 2010.1, "VAH": 2012.3, "VAL": 2008.7, "shape": "b", "shape_confidence_pct": 41.2},
                "tpo_h1": {"POC": 2009.9, "VAH": 2011.0, "VAL": 2008.2, "shape": None, "shape_confidence_pct": 18.0},
                "tpo_m30": {"POC": 2010.0, "VAH": 2010.8, "VAL": 2009.1},
            },
        },
    }
    result = format_signal_event(event)
    assert "Shape:b (heuristic 41.2%)" in result
    assert "probability" not in result.lower()
    assert "win rate" not in result.lower()
    assert "buy confidence" not in result.lower()
    assert "sell confidence" not in result.lower()


def test_format_signal_event_no_indicator_snapshot():
    """SIG-04: Backward compatible — old payloads without indicator_snapshot still format."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"choch_up": {"value": "choch_up"}},
            "session": "LONDON",
        },
    }
    result = format_signal_event(event)
    assert "📊" in result
    assert "SIGNAL ALERT" in result
    assert "Active Signals" in result
    assert "Indicator Snapshot" not in result
    assert len(result) <= 4095


def test_format_signal_event_indicator_snapshot_none_values():
    """D-13: Verify None values displayed as em dash (—)."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"sweep_bull": {"value": "sweep_bull"}},
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [None, None, None, None, None, None],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": None,
                "vol_sma_20": None,
                "htf_trend": None,
                "tpo_d1": None,
                "tpo_h1": None,
                "tpo_m30": None,
            },
        },
    }
    result = format_signal_event(event)
    assert "—" in result


def test_format_signal_event_bearish_trend():
    """Verify BEARISH trend shows red circle emoji."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"choch_down": {"value": "choch_down"}},
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2370.10, 2360.00, 2350.00, 2340.00, 2335.00, 2320.00],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 15.0,
                "vol_sma_20": 2000.0,
                "htf_trend": "BEARISH",
            },
        },
    }
    result = format_signal_event(event)
    assert "🔴" in result
    assert "BEARISH" in result


def test_format_signal_event_indicator_section_escapes_html():
    """Verify indicator values are HTML-escaped (T-40-04)."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"sweep_bear": {"value": "sweep_bear"}},
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "<script>alert('xss')</script>",
            },
        },
    }
    result = format_signal_event(event)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_format_signal_event_message_under_4095_with_snapshot():
    """D-10: Verify message with indicator snapshot stays under 4095 chars."""
    signals = {f"signal_{i}": f"value_{i}" for i in range(30)}
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": signals,
            "session": "NEW_YORK",
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "BULLISH",
            },
        },
    }
    result = format_signal_event(event)
    assert len(result) <= 4095


def test_format_signal_event_cisd_mtf_display():
    """Verify CISD MTF status is rendered in indicator snapshot."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"choch_up": {"value": "choch_up"}},
            "session": "NEW_YORK",
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "BULLISH",
                "cisd_mtf": {
                    "M5": "bullish",
                    "M15": "bearish",
                },
            },
        },
    }
    result = format_signal_event(event)
    assert "CISD MTF" in result
    assert "M5:" in result
    assert "M15:" in result
    assert "🟢" in result
    assert "🔴" in result
    assert "Bullish" in result
    assert "Bearish" in result


def test_format_signal_event_cisd_mtf_four_timeframes():
    """Verify all 4 TFs (M5/M15/M30/H1) rendered."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"sweep_bull": {"value": "sweep_bull"}},
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "NEUTRAL",
                "cisd_mtf": {
                    "M5": "bullish",
                    "M15": "bullish",
                    "M30": "bearish",
                    "H1": "bearish",
                },
            },
        },
    }
    result = format_signal_event(event)
    assert "CISD MTF" in result
    assert "M5:" in result
    assert "M15:" in result
    assert "M30:" in result
    assert "H1:" in result


def test_format_signal_event_cisd_mtf_all_dashes_when_no_tracking():
    """Verify CISD MTF still shown with em dashes when no TFs are tracking."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {"cisd": {"value": "bullish"}},
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "BULLISH",
                "cisd_mtf": None,
            },
        },
    }
    result = format_signal_event(event)
    assert "CISD MTF" in result
    assert "M5:" in result
    assert "H1:" in result
    assert "—" in result


def test_format_signal_event_cisd_mtf_filtered_from_active_signals():
    """Verify CISD MTF tags are hidden from Active Signals (shown in Indicator Snapshot)."""
    event = {
        "type": "SIGNAL_EVENT",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "signals": {
                "choch_up": {"value": "choch_up"},
                "cisd_m5_bullish": {"tf": "M5", "status": "bullish"},
                "cisd_m15_bearish": {"tf": "M15", "status": "bearish"},
                "cisd_m30_bullish": {"tf": "M30", "status": "bullish"},
                "cisd_h1_bearish": {"tf": "H1", "status": "bearish"},
            },
            "session": "NEW_YORK",
            "indicator_snapshot": {
                "emas": {
                    "periods": [21, 34, 55, 89, 100, 200],
                    "values": [2341.20, 2343.50, 2346.80, 2351.00, 2355.40, 2370.10],
                    "cross_markers": ["", "", "", "", "", ""],
                },
                "atr_14": 12.34,
                "vol_sma_20": 1500.0,
                "htf_trend": "BULLISH",
                "cisd_mtf": {
                    "M5": "bullish",
                    "M15": "bearish",
                    "M30": "bullish",
                    "H1": "bearish",
                },
            },
        },
    }
    result = format_signal_event(event)
    active_signals_section = result.split("📈 Indicator Snapshot:")[0]
    assert "cisd_m5" not in active_signals_section
    assert "cisd_m15" not in active_signals_section
    assert "cisd_m30" not in active_signals_section
    assert "cisd_h1" not in active_signals_section
    assert "choch_up" in active_signals_section


def test_format_strategy_match_reasoning_bank_section_escaped_and_trimmed():
    event = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "strategy": "STRAT_A",
            "strategy_id": 10,
            "side": "BUY",
            "entry_type": "MARKET",
            "sl": 1950.50,
            "tp": 1970.00,
            "size_value": 1.0,
            "reason_code": "OK",
            "reasoning_bank": {
                "sample_size": 4,
                "success_rate": 0.75,
                "avg_reward": 1.5,
                "avg_pnl_pips": 12.25,
                "recent_lessons": ["A lesson <b>safe</b>", "B lesson", "C lesson", "D lesson"],
            },
        },
    }
    result = format_strategy_match(event)
    assert "<b>Reasoning Bank</b>" in result
    assert "success=75.0%" in result
    assert "avg reward=1.50" in result
    assert "avg pips=12.2" in result
    assert "A lesson &lt;b&gt;safe&lt;/b&gt;" in result
    assert "D lesson" not in result
    assert len(result) <= 4095


def test_format_strategy_match_without_reasoning_bank_unchanged_section_absent():
    event = {
        "type": "STRATEGY_MATCH",
        "symbol": "XAUUSD",
        "t": 1712345678,
        "data": {
            "strategy": "STRAT_A",
            "strategy_id": 10,
            "side": "BUY",
            "entry_type": "MARKET",
            "sl": 1950.50,
            "tp": 1970.00,
            "size_value": 1.0,
            "reason_code": "OK",
        },
    }
    result = format_strategy_match(event)
    assert "Reasoning Bank" not in result
