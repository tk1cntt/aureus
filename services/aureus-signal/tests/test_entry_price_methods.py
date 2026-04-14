"""Tests for multi-method entry_price calculation."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.orders import SimulatedTradeManager
from engine.simulated_orders import SimulatedTradeManager as BacktestTradeManager
from engine.snapshot_utils import VALID_ENTRY_METHODS


class _MockState:
    """Minimal mock of SymbolState for testing entry price methods."""
    def __init__(self, symbol="EURUSD"):
        self.symbol = symbol
        self.last_candle = {
            "t": 1712500000,
            "o": 1.08500,
            "h": 1.08550,
            "l": 1.08480,
            "c": 1.08520,
            "v": 100,
        }
        self.emas = {
            21: {"value": 1.08510, "slope": 0.00001, "direction": "up"},
            34: {"value": 1.08490, "slope": -0.00001, "direction": "down"},
            55: {"value": 1.08460, "slope": 0.00002, "direction": "up"},
        }
        self.obs = [
            {
                "ob_type": "BULLISH",
                "top": 1.08530,
                "bottom": 1.08490,
                "mitigated": False,
                "broken": False,
            },
            {
                "ob_type": "BEARISH",
                "top": 1.08560,
                "bottom": 1.08530,
                "mitigated": False,
                "broken": False,
            },
        ]


class TestCalculateEntryPriceLive:
    """Test _calculate_entry_price on live SimulatedTradeManager."""

    def _manager(self):
        return SimulatedTradeManager(r=None)

    def test_current_returns_close(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "CURRENT")
        assert result == 1.08520

    def test_unknown_method_falls_back(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "INVALID_METHOD")
        assert result == 1.08520

    def test_pullback_50(self):
        """Midpoint of candle range: l + (h-l)*0.5 = 0.08480 + 0.00070*0.5 = 0.08515."""
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "PULLBACK_50")
        assert result == pytest.approx(1.08515)

    def test_ob_edge_buy_uses_bottom(self):
        """BUY → first unmitigated BULLISH OB bottom = 1.08490."""
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "OB_EDGE")
        assert result == pytest.approx(1.08490)

    def test_ob_edge_sell_uses_top(self):
        """SELL → first unmitigated BEARISH OB top = 1.08560."""
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("SELL", state, "OB_EDGE")
        assert result == pytest.approx(1.08560)

    def test_ob_edge_falls_back_no_obs(self):
        mgr = self._manager()
        state = _MockState()
        state.obs = []
        result = mgr._calculate_entry_price("BUY", state, "OB_EDGE")
        assert result == 1.08520

    def test_ob_edge_falls_back_all_mitigated(self):
        mgr = self._manager()
        state = _MockState()
        for ob in state.obs:
            ob["mitigated"] = True
        result = mgr._calculate_entry_price("BUY", state, "OB_EDGE")
        assert result == 1.08520

    def test_ob_edge_skips_wrong_type_for_buy(self):
        """BUY should not use BEARISH OB."""
        mgr = self._manager()
        state = _MockState()
        state.obs = [
            {"ob_type": "BEARISH", "top": 1.08560, "bottom": 1.08530,
             "mitigated": False, "broken": False},
        ]
        result = mgr._calculate_entry_price("BUY", state, "OB_EDGE")
        assert result == 1.08520

    def test_ema_touch_21(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "EMA_TOUCH", entry_value=21)
        assert result == pytest.approx(1.08510)

    def test_ema_touch_55(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "EMA_TOUCH", entry_value=55)
        assert result == pytest.approx(1.08460)

    def test_ema_touch_default_period(self):
        """When entry_value is None, defaults to period 21."""
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "EMA_TOUCH", entry_value=None)
        assert result == pytest.approx(1.08510)

    def test_ema_touch_falls_back_when_missing(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "EMA_TOUCH", entry_value=200)
        assert result == 1.08520

    def test_fixed_offset_buy_subtracts(self):
        """BUY: close - pips * point. EURUSD point=0.00001, 10 pips = 0.00010."""
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "FIXED_OFFSET", entry_value=10)
        assert result == pytest.approx(1.08510)

    def test_fixed_offset_sell_adds(self):
        """SELL: close + pips * point."""
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("SELL", state, "FIXED_OFFSET", entry_value=10)
        assert result == pytest.approx(1.08530)

    def test_fixed_offset_falls_back_on_invalid_value(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "FIXED_OFFSET", entry_value=-5)
        assert result == 1.08520

    def test_fixed_offset_falls_back_on_none(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "FIXED_OFFSET", entry_value=None)
        assert result == 1.08520


class TestCalculateEntryPriceBacktest:
    """Test _calculate_entry_price on backtest SimulatedTradeManager."""

    def _manager(self):
        return BacktestTradeManager()

    def test_current_returns_close(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "CURRENT")
        assert result == 1.08520

    def test_pullback_50(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "PULLBACK_50")
        assert result == pytest.approx(1.08515)

    def test_ob_edge_buy(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "OB_EDGE")
        assert result == pytest.approx(1.08490)

    def test_ema_touch(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "EMA_TOUCH", entry_value=34)
        assert result == pytest.approx(1.08490)

    def test_fixed_offset_buy(self):
        mgr = self._manager()
        state = _MockState()
        result = mgr._calculate_entry_price("BUY", state, "FIXED_OFFSET", entry_value=20)
        # 1.08520 - 20 * 0.00001 = 1.08500
        assert result == pytest.approx(1.08500)


class TestEntryMethodConstants:
    """Validate constant definitions."""

    def test_valid_entry_methods_contains_all(self):
        expected = {"CURRENT", "PULLBACK_50", "OB_EDGE", "EMA_TOUCH", "FIXED_OFFSET"}
        assert set(VALID_ENTRY_METHODS) == expected
