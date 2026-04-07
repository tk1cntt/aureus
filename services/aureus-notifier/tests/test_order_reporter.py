"""Tests for order_reporter module — format output and message generation."""
import pytest
from order_reporter import OrderStatusReporter


class TestFormatReport:
    """Test _format_report message generation."""

    def _make_reporter(self):
        """Create reporter with mock dependencies (only _format_report is pure)."""
        return OrderStatusReporter(
            redis_client=None,
            sender=None,
            chat_id="test_chat",
        )

    def test_empty_positions_and_trades_returns_empty(self):
        reporter = self._make_reporter()
        result = reporter._format_report([], [])
        assert result == ""

    def test_single_open_position_buy(self):
        reporter = self._make_reporter()
        positions = [{
            "ticket": 12345,
            "symbol": "XAUUSD",
            "magic": 100,
            "direction": "BUY",
            "volume": 0.01,
            "open_price": 2300.0,
            "current_price": 2302.5,
            "profit": 2.5,
            "swap": 0.0,
            "sl": 2295.0,
            "tp": 2310.0,
            "pips": 25.0,
            "open_time": 1712500000000,
        }]
        result = reporter._format_report(positions, [])
        assert "XAUUSD" in result
        assert "+2.50$" in result
        assert "+25.0 pips" in result
        assert "0.01" in result
        assert "Total P/L: +2.50$" in result
        assert "📊" in result

    def test_single_open_position_sell_negative(self):
        reporter = self._make_reporter()
        positions = [{
            "ticket": 99999,
            "symbol": "EURUSD",
            "magic": 200,
            "direction": "SELL",
            "volume": 0.05,
            "open_price": 1.08500,
            "current_price": 1.08700,
            "profit": -10.0,
            "swap": -0.5,
            "sl": 1.09000,
            "tp": 1.08000,
            "pips": -20.0,
            "open_time": 1712500000000,
        }]
        result = reporter._format_report(positions, [])
        assert "EURUSD" in result
        assert "-10.50$" in result
        assert "-20.0 pips" in result
        assert "0.05" in result
        assert "Total P/L: -10.50$" in result

    def test_multiple_positions_total_profit(self):
        reporter = self._make_reporter()
        positions = [
            {"symbol": "XAUUSD", "direction": "BUY", "volume": 0.01,
             "profit": 5.0, "swap": 0.0, "pips": 10.0},
            {"symbol": "BTCUSD", "direction": "SELL", "volume": 0.02,
             "profit": -3.0, "swap": -0.5, "pips": -15.0},
        ]
        result = reporter._format_report(positions, [])
        # Total should be 5.0 + (-3.0 + -0.5) = 1.5
        assert "Total P/L: +1.50$" in result

    def test_closed_trades_section(self):
        reporter = self._make_reporter()
        closed = [{
            "ticket": 55555,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "volume": 0.02,
            "entry_price": 1.26500,
            "exit_price": 1.26700,
            "profit": 4.0,
            "commission": -0.5,
            "swap": 0.0,
            "pips": 25.5, # Explicit pips from MT5
        }]
        result = reporter._format_report([], closed)
        assert "Closed (1m)" in result
        assert "GBPUSD" in result
        assert "+3.50$" in result
        assert "25.5 pips" in result

    def test_combined_positions_and_closed_trades(self):
        reporter = self._make_reporter()
        positions = [{
            "symbol": "XAUUSD", "direction": "BUY", "volume": 0.01,
            "profit": 2.0, "swap": 0.0, "pips": 5.0,
        }]
        closed = [{
            "symbol": "EURUSD", "direction": "SELL", "volume": 0.05,
            "entry_price": 1.08500, "exit_price": 1.08300,
            "profit": 10.0, "commission": -1.0, "swap": 0.0,
        }]
        result = reporter._format_report(positions, closed)
        assert "Open Positions" in result
        assert "Closed (1m)" in result
        assert "XAUUSD" in result
        assert "EURUSD" in result

    def test_no_positions_shows_no_open_message(self):
        reporter = self._make_reporter()
        closed = [{
            "symbol": "USDJPY", "direction": "BUY", "volume": 0.1,
            "entry_price": 150.500, "exit_price": 151.000,
            "profit": 33.0, "commission": -2.0, "swap": 0.0,
        }]
        result = reporter._format_report([], closed)
        assert "No open positions" in result

    def test_message_under_telegram_limit(self):
        reporter = self._make_reporter()
        # Create many positions
        positions = [
            {"symbol": f"SYM{i}", "direction": "BUY", "volume": 0.01,
             "profit": float(i), "swap": 0.0, "pips": float(i)}
            for i in range(50)
        ]
        result = reporter._format_report(positions, [])
        assert len(result) <= 4095

class TestWaitForResponse:
    """Test _wait_for_response handles pubsub message retrieval and timeout correctly."""

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout_returns_empty(self):
        reporter = OrderStatusReporter(
            redis_client=None,
            sender=None,
            chat_id="test_chat",
            response_timeout=0.1
        )
        
        import time
        from unittest.mock import AsyncMock
        
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message.return_value = None
        
        start_time = time.time()
        result = await reporter._wait_for_response(mock_pubsub, "POSITION_REPORT", "positions")
        duration = time.time() - start_time
        
        assert result == []
        assert duration >= 0.1
        assert duration < 0.5  # Ensure it doesn't hang indefinitely

    @pytest.mark.asyncio
    async def test_wait_for_response_gets_message(self):
        reporter = OrderStatusReporter(
            redis_client=None,
            sender=None,
            chat_id="test_chat",
            response_timeout=1.0
        )
        
        from unittest.mock import AsyncMock
        import json
        
        mock_pubsub = AsyncMock()
        mock_pubsub.get_message.return_value = {
            "type": "message",
            "data": json.dumps({"type": "POSITION_REPORT", "positions": ["test_pos"]})
        }
        
        result = await reporter._wait_for_response(mock_pubsub, "POSITION_REPORT", "positions")
        
        assert result == ["test_pos"]
