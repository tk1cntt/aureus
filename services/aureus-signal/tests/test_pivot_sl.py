"""Tests for PIVOT_POINT SL mechanism (Phase 41)."""
import os
import sys
import pytest
from unittest.mock import MagicMock

# Add engine package to path so imports work when running pytest from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.orders import SimulatedTradeManager


class TestFindPivotForSl:
    """Tests for _find_pivot_for_sl() method."""

    def setup_method(self):
        self.tm = SimulatedTradeManager(MagicMock())
        self.state = MagicMock()

    def _make_swing_points(self, points):
        """Helper: tạo swing points list từ dict shorthand."""
        self.state.swing_points = points

    def test_buy_finds_nearest_ll(self):
        """BUY tìm LL gần nhất chưa broken."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 200, "price": 2010.0, "is_high": True, "type": "HH"},
            {"t": 300, "price": 2005.0, "is_high": False, "type": "LL", "broken": False},
        ])
        result = self.tm._find_pivot_for_sl("BUY", self.state)
        assert result == 2005.0  # LL gần nhất (t=300)

    def test_sell_finds_nearest_hh(self):
        """SELL tìm HH gần nhất chưa broken."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": True, "type": "HH", "broken": False},
            {"t": 200, "price": 1990.0, "is_high": False, "type": "LL"},
            {"t": 300, "price": 2015.0, "is_high": True, "type": "HH", "broken": False},
        ])
        result = self.tm._find_pivot_for_sl("SELL", self.state)
        assert result == 2015.0  # HH gần nhất (t=300)

    def test_skips_broken_pivots(self):
        """Bỏ qua pivot đã broken, tìm pivot trước đó."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 200, "price": 2005.0, "is_high": False, "type": "LL", "broken": True},
        ])
        result = self.tm._find_pivot_for_sl("BUY", self.state)
        assert result == 2000.0  # Pivot t=200 bị broken, lùi về t=100

    def test_returns_none_if_no_swing_points(self):
        """Return None khi swing_points rỗng."""
        self.state.swing_points = []
        result = self.tm._find_pivot_for_sl("BUY", self.state)
        assert result is None

    def test_returns_none_if_no_matching_type(self):
        """Return None khi không có swing point cùng loại (HH cho SELL, LL cho BUY)."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": True, "type": "HH"},
            {"t": 200, "price": 2010.0, "is_high": True, "type": "HH"},
        ])
        result = self.tm._find_pivot_for_sl("BUY", self.state)
        assert result is None  # Không có LL nào

    def test_skips_wrong_type(self):
        """Bỏ qua LH cho BUY, HL cho SELL (strict SMC)."""
        self._make_swing_points([
            {"t": 100, "price": 2005.0, "is_high": False, "type": "LH"},  # LH, không phải LL
            {"t": 200, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ])
        result = self.tm._find_pivot_for_sl("BUY", self.state)
        assert result == 2000.0  # Bỏ qua LH, lấy LL


class TestCalculateSlTpPivotPoint:
    """Tests for PIVOT_POINT branch trong _calculate_sl_tp()."""

    def setup_method(self):
        self.tm = SimulatedTradeManager(MagicMock())
        self.state = MagicMock()
        self.state.symbol = "XAUUSD"
        self.state.last_candle = {"t": 1000, "c": 2010.0, "h": 2020.0, "l": 2000.0}
        self.trigger = {"strategy": "TEST_STRAT", "side": "BUY"}

    def test_pivot_point_buy_sl_below_pivot(self):
        """BUY: SL = pivot_price - offset."""
        self.state.swing_points = [
            {"t": 900, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 5}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        # point_size cho XAUUSD từ symbols.json (thường 0.01)
        # SL = 2000.0 - (5 * 0.01) = 1999.95
        assert sl is not None
        assert sl < 2000.0  # SL phải dưới pivot

    def test_pivot_point_sell_sl_above_pivot(self):
        """SELL: SL = pivot_price + offset."""
        self.trigger["side"] = "SELL"
        self.state.swing_points = [
            {"t": 900, "price": 2020.0, "is_high": True, "type": "HH", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 5}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is not None
        assert sl > 2020.0  # SL phải trên pivot

    def test_pivot_point_no_pivot_rejects(self):
        """Không tìm thấy pivot → reject (None, None)."""
        self.state.swing_points = []
        config = {"sl": {"type": "PIVOT_POINT"}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)
        assert sl is None
        assert tp is None

    def test_pivot_point_zero_offset(self):
        """offset_pips=0 → SL = đúng giá pivot (không buffer)."""
        self.state.swing_points = [
            {"t": 900, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        # SL = pivot_price - 0 = pivot_price
        assert sl == 2000.0

    def test_pivot_point_missing_offset_defaults_zero(self):
        """Không có offset_pips trong config → default = 0."""
        self.state.swing_points = [
            {"t": 900, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT"}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        # SL = pivot_price - 0 = pivot_price (same as offset_pips=0)
        assert sl == 2000.0

    def test_fixed_pips_unchanged(self):
        """FIXED_PIPS vẫn hoạt động bình thường (backward compatibility)."""
        self.state.swing_points = []  # Không có swing points
        config = {"sl": {"type": "FIXED_PIPS"}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is not None  # FIXED_PIPS không cần swing points
        assert tp is not None
