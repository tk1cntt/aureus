"""Tests for PIVOT_POINT SL mechanism (Phase 41)."""
import os
import sys
import pytest
from unittest.mock import MagicMock

# Add engine package to path so imports work when running pytest from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.orders import SimulatedTradeManager


class TestFindPivotForSl:
    """Tests for _find_pivot_for_sl_candidates() method."""

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
        result = self.tm._find_pivot_for_sl_candidates("BUY", self.state)
        assert result and result[0]["price"] == 2000.0
        assert result[1]["price"] == 2005.0  # carries t metadata for caller-side time sort

    def test_sell_finds_nearest_hh(self):
        """SELL tìm HH gần nhất chưa broken."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": True, "type": "HH", "broken": False},
            {"t": 200, "price": 1990.0, "is_high": False, "type": "LL"},
            {"t": 300, "price": 2015.0, "is_high": True, "type": "HH", "broken": False},
        ])
        result = self.tm._find_pivot_for_sl_candidates("SELL", self.state)
        assert result and result[0]["price"] == 2000.0
        assert result[1]["price"] == 2015.0  # carries t metadata for caller-side time sort

    def test_skips_broken_pivots(self):
        """Bỏ qua pivot đã broken, tìm pivot trước đó."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 200, "price": 2005.0, "is_high": False, "type": "LL", "broken": True},
        ])
        result = self.tm._find_pivot_for_sl_candidates("BUY", self.state)
        assert result and result[0]["price"] == 2000.0  # Pivot t=200 bị broken, lùi về t=100

    def test_returns_empty_if_no_swing_points(self):
        """Return [] khi swing_points rỗng."""
        self.state.swing_points = []
        result = self.tm._find_pivot_for_sl_candidates("BUY", self.state)
        assert result == []

    def test_returns_none_if_no_matching_type(self):
        """Return None khi không có swing point cùng loại (HH cho SELL, LL cho BUY)."""
        self._make_swing_points([
            {"t": 100, "price": 2000.0, "is_high": True, "type": "HH"},
            {"t": 200, "price": 2010.0, "is_high": True, "type": "HH"},
        ])
        result = self.tm._find_pivot_for_sl_candidates("BUY", self.state)
        assert result == []  # Không có LL nào

    def test_skips_wrong_type(self):
        """Bỏ qua LH cho BUY, HL cho SELL (strict SMC)."""
        self._make_swing_points([
            {"t": 100, "price": 2005.0, "is_high": False, "type": "LH"},  # LH, không phải LL
            {"t": 200, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ])
        result = self.tm._find_pivot_for_sl_candidates("BUY", self.state)
        assert result and result[0]["price"] == 2000.0  # Bỏ qua LH, lấy LL


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
        self.state.last_candle = {"t": 1000, "c": 2009.95, "h": 2020.0, "l": 2000.0}
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
        self.state.last_candle = {"t": 1000, "c": 2010.05, "h": 2020.0, "l": 2000.0}
        self.state.swing_points = [
            {"t": 900, "price": 2020.0, "is_high": True, "type": "HH", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 5}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is not None
        assert sl > 2020.0  # SL phải trên pivot

    def test_pivot_point_no_pivot_rejects_without_fixed_pips_fallback(self):
        """Không tìm thấy pivot → không fallback FIXED_PIPS."""
        self.state.swing_points = []
        config = {"sl": {"type": "PIVOT_POINT"}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)
        assert sl is None
        assert tp is None

    def test_pivot_point_pivot_index_applies_after_filter(self):
        """pivot_index=2 chọn candidate hợp lệ thứ hai sau filter 5 nến và sort theo thời gian."""
        self.state.swing_points = [
            {"t": 700, "price": 1980.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 900, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 800, "price": 1990.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0, "pivot_index": 2}, "tp": {"type": "RR", "value": 2.0}}
        recent_candles = [
            {"h": 2015, "l": 1998},
            {"h": 2016, "l": 2001},
            {"h": 2017, "l": 2002},
            {"h": 2018, "l": 2003},
            {"h": 2019, "l": 2004},
        ]
        sl, tp = self.tm._calculate_sl_tp(
            self.trigger,
            self.state,
            config,
            entry_price_override=1990.0,
            recent_candles=recent_candles,
        )
        assert sl == 1980.0
        assert tp is not None

    def test_pivot_point_buy_selects_newest_valid_pivot_by_time(self):
        """BUY: unordered swing_points, pivot_index=1 chọn LL mới nhất, không theo giá/list order."""
        self.state.swing_points = [
            {"t": 900, "price": 1990.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 700, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 800, "price": 1980.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0, "pivot_index": 1}, "tp": {"type": "RR", "value": 2.0}}
        recent_candles = [
            {"h": 2015, "l": 2001},
            {"h": 2016, "l": 2002},
            {"h": 2017, "l": 2003},
            {"h": 2018, "l": 2004},
            {"h": 2019, "l": 2005},
        ]
        sl, tp = self.tm._calculate_sl_tp(
            self.trigger,
            self.state,
            config,
            entry_price_override=2000.0,
            recent_candles=recent_candles,
        )

        assert sl == 1990.0
        assert tp is not None

    def test_pivot_point_sell_selects_newest_valid_pivot_by_time(self):
        """SELL: unordered swing_points, pivot_index=1 chọn HH mới nhất, không theo giá/list order."""
        self.trigger["side"] = "SELL"
        self.state.swing_points = [
            {"t": 900, "price": 2030.0, "is_high": True, "type": "HH", "broken": False},
            {"t": 700, "price": 2020.0, "is_high": True, "type": "HH", "broken": False},
            {"t": 800, "price": 2040.0, "is_high": True, "type": "HH", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0, "pivot_index": 1}, "tp": {"type": "RR", "value": 2.0}}
        recent_candles = [
            {"h": 2015, "l": 2001},
            {"h": 2016, "l": 2002},
            {"h": 2017, "l": 2003},
            {"h": 2018, "l": 2004},
            {"h": 2019, "l": 2005},
        ]
        sl, tp = self.tm._calculate_sl_tp(
            self.trigger,
            self.state,
            config,
            entry_price_override=2020.0,
            recent_candles=recent_candles,
        )

        assert sl == 2030.0
        assert tp is not None

    def test_pivot_point_pivot_index_applies_after_time_sort(self):
        """pivot_index=2 chọn candidate thứ hai sau sort thời gian, không theo giá/list order."""
        self.state.swing_points = [
            {"t": 800, "price": 1980.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 700, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 900, "price": 1990.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0, "pivot_index": 2}, "tp": {"type": "RR", "value": 2.0}}
        recent_candles = [
            {"h": 2015, "l": 2001},
            {"h": 2016, "l": 2002},
            {"h": 2017, "l": 2003},
            {"h": 2018, "l": 2004},
            {"h": 2019, "l": 2005},
        ]
        sl, tp = self.tm._calculate_sl_tp(
            self.trigger,
            self.state,
            config,
            entry_price_override=1988.0,
            recent_candles=recent_candles,
        )

        assert sl == 1980.0
        assert tp is not None

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

    def test_pivot_point_buy_skips_invalid_pivot_and_uses_next(self):
        """BUY: nếu low 5 nến <= pivot thì bỏ pivot đó, chọn pivot kế tiếp."""
        self.state.swing_points = [
            {"t": 800, "price": 1990.0, "is_high": False, "type": "LL", "broken": False},
            {"t": 900, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        recent_candles = [
            {"h": 2015, "l": 2002},
            {"h": 2016, "l": 2001},
            {"h": 2017, "l": 1998},
            {"h": 2018, "l": 2003},
            {"h": 2019, "l": 2004},
        ]
        sl, tp = self.tm._calculate_sl_tp(
            self.trigger,
            self.state,
            config,
            entry_price_override=1999.0,
            recent_candles=recent_candles,
        )

        assert sl == 1990.0
        assert tp is not None

    def test_pivot_point_sell_skips_invalid_pivot_and_uses_next(self):
        """SELL: nếu high 5 nến >= pivot thì bỏ pivot đó, chọn pivot kế tiếp."""
        self.trigger["side"] = "SELL"
        self.state.swing_points = [
            {"t": 800, "price": 2030.0, "is_high": True, "type": "HH", "broken": False},
            {"t": 900, "price": 2020.0, "is_high": True, "type": "HH", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        recent_candles = [
            {"h": 2025, "l": 2001},
            {"h": 2024, "l": 2002},
            {"h": 2022, "l": 2000},
            {"h": 2023, "l": 2003},
            {"h": 2021, "l": 2004},
        ]
        sl, tp = self.tm._calculate_sl_tp(
            self.trigger,
            self.state,
            config,
            entry_price_override=2021.0,
            recent_candles=recent_candles,
        )

        assert sl == 2030.0
        assert tp is not None

    def test_pivot_point_xau_rejects_sl_distance_greater_than_limit(self):
        """XAU PIVOT_POINT reject khi distance > 10.0."""
        self.state.swing_points = [
            {"t": 900, "price": 1999.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is None
        assert tp is None

    def test_pivot_point_xau_allows_sl_distance_equal_to_limit(self):
        """XAU PIVOT_POINT allow khi distance == 10.0."""
        self.state.swing_points = [
            {"t": 900, "price": 2000.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is not None
        assert tp is not None

    def test_pivot_point_ustec_rejects_sl_distance_greater_than_limit(self):
        """USTEC PIVOT_POINT reject khi distance > 50.0."""
        self.state.symbol = "USTEC"
        self.state.last_candle = {"t": 1000, "c": 15000.0, "h": 15020.0, "l": 14980.0}
        self.trigger["side"] = "SELL"
        self.state.swing_points = [
            {"t": 900, "price": 15051.0, "is_high": True, "type": "HH", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is None
        assert tp is None

    def test_pivot_point_btc_rejects_sl_distance_greater_than_limit(self):
        """BTC PIVOT_POINT reject khi distance > 500.0."""
        self.state.symbol = "BTCUSD"
        self.state.last_candle = {"t": 1000, "c": 70000.0, "h": 70100.0, "l": 69900.0}
        self.state.swing_points = [
            {"t": 900, "price": 69499.0, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is None
        assert tp is None

    def test_pivot_point_forex_uses_pivot_without_distance_limit(self):
        """Forex PIVOT_POINT vẫn dùng pivot bình thường, không áp dụng guard 20 * point_size."""
        self.state.symbol = "EURUSD"
        self.state.last_candle = {"t": 1000, "c": 1.10000, "h": 1.10100, "l": 1.09900}
        self.state.swing_points = [
            {"t": 900, "price": 1.09979, "is_high": False, "type": "LL", "broken": False},
        ]
        config = {"sl": {"type": "PIVOT_POINT", "offset_pips": 0}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl == 1.09979
        assert tp is not None

    def test_fixed_pips_unchanged(self):
        """FIXED_PIPS vẫn hoạt động bình thường (backward compatibility)."""
        self.state.swing_points = []  # Không có swing points
        config = {"sl": {"type": "FIXED_PIPS"}, "tp": {"type": "RR", "value": 2.0}}
        sl, tp = self.tm._calculate_sl_tp(self.trigger, self.state, config)

        assert sl is not None  # FIXED_PIPS không cần swing points
        assert tp is not None
