"""Tests for order_reporter module — event-driven ORDER_CLOSED notification formatting."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from order_reporter import OrderStatusReporter


class TestFormatClose:
    """Test _format_close message generation for ORDER_CLOSED events."""

    def _make_reporter(self):
        return OrderStatusReporter(
            redis_client=None,
            sender=None,
            chat_id="test_chat",
        )

    def test_buy_order_profit(self):
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "XAUUSD",
            "ticket": 12345,
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 2300.0,
            "close_price": 2305.0,
            "profit": 5.0,
            "commission": -0.5,
            "swap": 0.0,
            "digits": 5,
            "t": 1712500000000,
        }
        result = reporter._format_close(event)
        assert "Order Closed" in result
        assert "XAUUSD" in result
        assert "BUY" in result
        assert "4.50$" in result  # 5.0 - 0.5 = 4.5
        assert "2300.0" in result  # entry
        assert "2305.0" in result  # exit
        assert "0.01" in result  # volume
        assert "12345" in result  # ticket

    def test_sell_order_loss(self):
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "EURUSD",
            "ticket": 99999,
            "direction": "SELL",
            "volume": 0.05,
            "open_price": 1.08500,
            "close_price": 1.08700,
            "profit": -10.0,
            "commission": -0.5,
            "swap": 0.0,
            "digits": 5,
            "t": 1712500000000,
        }
        result = reporter._format_close(event)
        assert "EURUSD" in result
        assert "SELL" in result
        assert "-10.50$" in result  # -10.0 - 0.5
        assert "0.05" in result

    def test_pips_calculation_buy_5digits(self):
        """BUY 5-digit: (exit - entry) * 10000."""
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 1.08500,
            "close_price": 1.08700,
            "profit": 20.0,
            "commission": 0,
            "swap": 0,
            "digits": 5,
        }
        result = reporter._format_close(event)
        # (1.08700 - 1.08500) * 10000 = 20.0 pips
        assert "20.0 pips" in result

    def test_pips_calculation_sell_5digits(self):
        """SELL 5-digit: (entry - exit) * 10000."""
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "EURUSD",
            "direction": "SELL",
            "volume": 0.01,
            "open_price": 1.08700,
            "close_price": 1.08500,
            "profit": 20.0,
            "commission": 0,
            "swap": 0,
            "digits": 5,
        }
        result = reporter._format_close(event)
        # (1.08700 - 1.08500) * 10000 = 20.0 pips
        assert "20.0 pips" in result

    def test_pips_calculation_3digits(self):
        """3-digit (JPY): (close - open) * 100 for BUY."""
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "USDJPY",
            "direction": "BUY",
            "volume": 0.1,
            "open_price": 150.500,
            "close_price": 151.000,
            "profit": 33.0,
            "commission": 0,
            "swap": 0,
            "digits": 3,
        }
        result = reporter._format_close(event)
        # (151.000 - 150.500) * 100 = 50.0 pips
        assert "50.0 pips" in result

    def test_net_profit_includes_commission_swap(self):
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 2300.0,
            "close_price": 2302.0,
            "profit": 2.0,
            "commission": -0.5,
            "swap": -0.3,
            "digits": 5,
        }
        result = reporter._format_close(event)
        # net = 2.0 - 0.5 - 0.3 = 1.2
        assert "1.20$" in result

    def test_message_under_telegram_limit(self):
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "X" * 100,  # very long symbol
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 100.0,
            "close_price": 100.0,
            "profit": 0.0,
            "commission": 0.0,
            "swap": 0.0,
            "digits": 5,
        }
        result = reporter._format_close(event)
        assert len(result) <= 4095

    def test_html_escape_in_symbol(self):
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "EUR<TEST>",  # should be escaped
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 1.0,
            "close_price": 1.0,
            "profit": 0.0,
            "commission": 0.0,
            "swap": 0.0,
            "digits": 5,
        }
        result = reporter._format_close(event)
        assert "&lt;TEST&gt;" in result

    def test_pips_na_when_entry_zero(self):
        """EA gửi open_price=0 khi không query được position → pips = N/A."""
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "BTCUSD",
            "ticket": 1589935582,
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 0.0,
            "close_price": 74285.22,
            "profit": -1.8,
            "commission": 0.0,
            "swap": 0.0,
            "digits": 5,
        }
        result = reporter._format_close(event)
        assert "N/A" in result
        assert "-1.80$" in result
        # pips text should be exactly "N/A" — no numeric value
        assert "(N/A)" in result

    def test_pips_from_explicit_field(self):
        """Khi EA gửi sẵn pips trong event → dùng giá trị đó."""
        reporter = self._make_reporter()
        event = {
            "type": "ORDER_CLOSED",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 0.0,  # entry bị 0
            "close_price": 2305.0,
            "profit": 5.0,
            "commission": 0,
            "swap": 0,
            "pips": 50.0,  # EA đã tính sẵn
        }
        result = reporter._format_close(event)
        assert "+50.0 pips" in result
