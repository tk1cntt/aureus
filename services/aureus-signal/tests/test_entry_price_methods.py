"""Regression tests for live order entry price no-fallback semantics."""
import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.orders import SimulatedTradeManager
from engine.snapshot_utils import VALID_ENTRY_METHODS


class FakeRedis:
    def __init__(self):
        self.members = set()
        self.stream_events = []

    async def sismember(self, key, value):
        return (key, value) in self.members

    async def sadd(self, key, value):
        self.members.add((key, value))

    async def xadd(self, key, payload):
        self.stream_events.append((key, payload))


class MockState:
    def __init__(self, symbol="EURUSD"):
        self.symbol = symbol
        self.last_candle = {"t": 1712500000, "o": 1.08500, "h": 1.08550, "l": 1.08480, "c": 1.08520, "v": 100}
        self.simulated_orders = []
        self.order_rejections = []
        self.swing_points = []
        self.obs = []
        self.emas = {}


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def base_trigger(entry_method="CURRENT", side="BUY"):
    return {
        "strategy_id": 42,
        "strategy": "TEST_LIMIT_BULL" if side == "BUY" else "TEST_LIMIT_BEAR",
        "origin_timestamp": 1712499998,
        "side": side,
        "order_plan": {
            "entry_type": "LIMIT",
            "entry_method": entry_method,
            "entry_policy": "IMMEDIATE",
            "size_mode": "FIXED_UNITS",
            "size": 0.01,
            "sl": {"mode": "FIXED_PIPS", "value": 20},
            "tp": {"mode": "RR", "value": 2.0},
        },
    }


class TestCalculateEntryPriceLive:
    def _manager(self):
        return SimulatedTradeManager(r=None)

    def test_current_returns_close(self):
        result = self._manager()._calculate_entry_price("BUY", MockState(), "CURRENT")
        assert result == 1.08520

    @pytest.mark.parametrize("method", ["INVALID_METHOD", "OB_EDGE", "EMA_TOUCH", "FIXED_OFFSET", "PULLBACK_50", "ENTRY_PIVOT_LIMIT", "ENTRY_FVG_FROM_CHOCH_PIVOT"])
    def test_methods_without_valid_data_return_none(self, method):
        result = self._manager()._calculate_entry_price("BUY", MockState(), method, entry_value=-5)
        assert result is None

    def test_pullback_50_buy_uses_unbroken_ll_midpoint(self):
        state = MockState()
        state.swing_points = [{"t": 1712499900, "price": 1.08400, "is_high": False, "type": "LL", "broken": False}]
        result = self._manager()._calculate_entry_price("BUY", state, "PULLBACK_50")
        assert result == pytest.approx((1.08400 + 1.08550) / 2)

    def test_pullback_50_sell_uses_unbroken_hh_midpoint(self):
        state = MockState()
        state.last_candle["c"] = 1.08500
        state.swing_points = [{"t": 1712499900, "price": 1.08600, "is_high": True, "type": "HH", "broken": False}]
        result = self._manager()._calculate_entry_price("SELL", state, "PULLBACK_50")
        assert result == pytest.approx((1.08600 + 1.08480) / 2)

    def test_entry_pivot_limit_uses_unbroken_pivot_on_correct_side(self):
        state = MockState()
        state.swing_points = [{"t": 1712499900, "price": 1.08400, "is_high": False, "type": "LL", "broken": False}]
        result = self._manager()._calculate_entry_price("BUY", state, "ENTRY_PIVOT_LIMIT")
        assert result == pytest.approx(1.08400)

    def test_entry_fvg_from_choch_pivot_buy_uses_first_bullish_fvg_after_ll(self):
        state = MockState()
        state.swing_points = [{"t": 100, "price": 1.08000, "is_high": False, "type": "LL", "broken": False}]
        state.fvgs = [
            {"t": 90, "direction": "BULLISH", "top": 1.0820, "bottom": 1.0810},
            {"t": 110, "direction": "BULLISH", "top": 1.0830, "bottom": 1.0820},
            {"t": 120, "direction": "BULLISH", "top": 1.0840, "bottom": 1.0830},
        ]
        result = self._manager()._calculate_entry_price("BUY", state, "ENTRY_FVG_FROM_CHOCH_PIVOT")
        assert result == pytest.approx(1.0825)

    def test_entry_fvg_from_choch_pivot_sell_uses_first_bearish_fvg_after_hh(self):
        state = MockState()
        state.swing_points = [{"t": 100, "price": 1.09000, "is_high": True, "type": "HH", "broken": False}]
        state.fvgs = [
            {"t_start": 90, "direction": "BEARISH", "top": 1.0880, "bottom": 1.0870},
            {"t_start": 110, "direction": "BEARISH", "top": 1.0860, "bottom": 1.0850},
        ]
        result = self._manager()._calculate_entry_price("SELL", state, "ENTRY_FVG_FROM_CHOCH_PIVOT")
        assert result == pytest.approx(1.0855)

    def test_entry_fvg_from_choch_pivot_ignores_broken_and_before_pivot_fvg(self):
        state = MockState()
        state.swing_points = [{"t": 100, "price": 1.08000, "is_high": False, "type": "LL", "broken": False}]
        state.fvgs = [
            {"t": 90, "direction": "BULLISH", "top": 1.0820, "bottom": 1.0810},
            {"t": 110, "direction": "BULLISH", "top": 1.0830, "bottom": 1.0820, "state": "BROKEN"},
            {"t": 120, "direction": "BULLISH", "top": 1.0840, "bottom": 1.0830},
        ]
        result = self._manager()._calculate_entry_price("BUY", state, "ENTRY_FVG_FROM_CHOCH_PIVOT")
        assert result == pytest.approx(1.0835)


@pytest.mark.parametrize("entry_method", ["EMA_TOUCH", "ENTRY_FVG_FROM_CHOCH_PIVOT"])
def test_entry_failure_rejects_order_without_history_or_order(entry_method):
    redis = FakeRedis()
    manager = SimulatedTradeManager(redis)
    state = MockState()

    run(manager.process_triggers("EURUSD", [base_trigger(entry_method)], state))

    assert state.simulated_orders == []
    assert redis.members == set()
    assert len(state.order_rejections) == 1
    assert state.order_rejections[0]["reason_code"] == "ORDER_PLAN_INCOMPLETE"
    assert state.order_rejections[0]["entry_method"] == entry_method
    assert redis.stream_events[0][1]["type"] == "ORDER_REJECTED"
    payload = json.loads(redis.stream_events[0][1]["data"])
    assert payload["entry_error"] == "ENTRY_PRICE_UNAVAILABLE"


def test_valid_entry_methods_include_fvg_from_choch_pivot():
    assert "ENTRY_PIVOT_LIMIT" in VALID_ENTRY_METHODS
    assert "ENTRY_FVG_FROM_CHOCH_PIVOT" in VALID_ENTRY_METHODS
