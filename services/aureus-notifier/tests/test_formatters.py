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
    assert "• zigzag_state: SWING_HIGH" in result
    assert "• ob_state: BULLISH" in result
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
    assert "(no active signals)" in result


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
