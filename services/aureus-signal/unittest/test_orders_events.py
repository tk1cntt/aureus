"""
Unit tests for orders.py last_tick_events — Story 9.3

Tests:
  - AC1: last_tick_events populated on ORDER_OPENED, SL_HIT, TP_HIT
  - AC2: last_tick_events can be cleared externally (engine caller)
  - AC3: Trade execution logic unchanged
  - AC4: Compatible with has_structural_event()
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.orders import SimulatedTradeManager
from engine.event_filter import has_structural_event


# --- Async helper ---

def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Mock objects ---

class FakeRedis:
    """Minimal async Redis mock."""
    def __init__(self):
        self._sets = {}
        self._streams = []

    async def sismember(self, key, member):
        return member in self._sets.get(key, set())

    async def sadd(self, key, member):
        if key not in self._sets:
            self._sets[key] = set()
        self._sets[key].add(member)

    async def xadd(self, stream, data):
        self._streams.append((stream, data))


class MockState:
    """Minimal SymbolState mock."""
    def __init__(self):
        self.last_candle = {'c': '2000.00', 't': '1709300000', 'o': '1999', 'h': '2001', 'l': '1998', 'v': '100'}
        self.simulated_orders = []
        self.transient_signals = {}
        self.symbol = "XAUUSD"
        self.swing_points = []
        self.atr = 5.0


# --- AC1: Tracking ---

def test_init_has_last_tick_events():
    """AC1: SimulatedTradeManager has last_tick_events list on init."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    assert hasattr(tm, 'last_tick_events'), "Missing last_tick_events attribute"
    assert tm.last_tick_events == [], "Should be empty on init"


def test_order_opened_event():
    """AC1: ORDER_OPENED appended when a new trade is created with ACTIVE status."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    trigger = {
        'strategy_id': 1,
        'strategy': 'test_bull_strategy',
        'origin_timestamp': '1709300000',
        'side': 'BUY',
        'exit_config': {},
    }

    run(tm.process_triggers("XAUUSD", [trigger], state))

    assert "ORDER_OPENED" in tm.last_tick_events, f"Expected ORDER_OPENED, got {tm.last_tick_events}"
    assert len(state.simulated_orders) == 1, "Order should be created"


def test_order_open_payload_contains_bridge_contract_fields():
    """Task 3: outbound ORDER_OPEN payload must preserve bridge contract keys."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    trigger = {
        'strategy_id': 9,
        'strategy': 'test_bull_strategy',
        'origin_timestamp': '1709300000',
        'side': 'BUY',
        'exit_config': {},
    }

    run(tm.process_triggers("XAUUSD", [trigger], state, execution_mode="nautilus"))

    order_open_streams = [entry for entry in r._streams if entry[1].get('type') == 'ORDER_OPEN']
    assert order_open_streams, "Expected ORDER_OPEN stream event"

    _, payload = order_open_streams[-1]
    order_data = json.loads(payload['data'])

    assert order_data['trace_id'] == 'XAUUSD:9:1709300000'
    assert order_data['execution_mode'] == 'nautilus'
    assert isinstance(order_data.get('entry_price'), float)
    assert order_data.get('sl') is not None
    assert order_data.get('tp') is not None


def test_sl_hit_event():
    """AC1: SL_HIT appended when a BUY order hits stop loss."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    # Pre-create an active order
    state.simulated_orders.append({
        'trace_id': 'TEST:1:100',
        'symbol': 'XAUUSD',
        'side': 'BUY',
        'entry_price': 2000.0,
        'sl': 1995.0,
        'tp': 2010.0,
        'status': 'ACTIVE',
        'pnl': 0.0,
        'close_time': None,
        'exit_price': None,
    })

    # Candle that hits SL (low <= 1995)
    candle = {'h': '2001', 'l': '1994', 'c': '1996', 't': '1709300060'}
    run(tm.update_orders("XAUUSD", candle, state))

    assert "SL_HIT" in tm.last_tick_events, f"Expected SL_HIT, got {tm.last_tick_events}"


def test_tp_hit_event():
    """AC1: TP_HIT appended when a BUY order hits take profit."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    state.simulated_orders.append({
        'trace_id': 'TEST:1:100',
        'symbol': 'XAUUSD',
        'side': 'BUY',
        'entry_price': 2000.0,
        'sl': 1995.0,
        'tp': 2010.0,
        'status': 'ACTIVE',
        'pnl': 0.0,
        'close_time': None,
        'exit_price': None,
    })

    # Candle that hits TP (high >= 2010)
    candle = {'h': '2011', 'l': '1999', 'c': '2009', 't': '1709300060'}
    run(tm.update_orders("XAUUSD", candle, state))

    assert "TP_HIT" in tm.last_tick_events, f"Expected TP_HIT, got {tm.last_tick_events}"


# --- AC2: Reset ---

def test_clear_events_externally():
    """AC2: Engine caller can clear last_tick_events."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    tm.last_tick_events.append("ORDER_OPENED")

    # Engine clears after checking event filter
    tm.last_tick_events = []
    assert tm.last_tick_events == []


# --- AC3: No Side Effect ---

def test_trade_execution_unchanged():
    """AC3: Trade creation still works correctly with events tracking."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    trigger = {
        'strategy_id': 1,
        'strategy': 'test_bear_strategy',
        'origin_timestamp': '1709300000',
        'side': 'SELL',
        'exit_config': {},
    }

    run(tm.process_triggers("XAUUSD", [trigger], state))

    # Verify order was created correctly
    assert len(state.simulated_orders) == 1
    order = state.simulated_orders[0]
    assert order['side'] == 'SELL'
    assert order['status'] == 'ACTIVE'
    assert order['entry_price'] == 2000.0


def test_sl_tp_calculation_unchanged():
    """AC3: SL/TP calculation still works correctly."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    trigger = {
        'strategy_id': 1,
        'strategy': 'test_bull_strategy',
        'origin_timestamp': '1709300000',
        'side': 'BUY',
        'exit_config': {},
    }

    run(tm.process_triggers("XAUUSD", [trigger], state))
    order = state.simulated_orders[0]
    assert order['sl'] is not None
    assert order['tp'] is not None
    assert order['sl'] < order['entry_price']  # BUY: SL below entry
    assert order['tp'] > order['entry_price']  # BUY: TP above entry


# --- AC4: Compatible API ---

def test_compatible_with_event_filter():
    """AC4: has_structural_event() works with live trade_manager."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    # No events — should return False
    assert has_structural_event(state, tm) is False

    # Add trade event
    tm.last_tick_events.append("ORDER_OPENED")
    assert has_structural_event(state, tm) is True

    # Clear and verify
    tm.last_tick_events = []
    assert has_structural_event(state, tm) is False


def test_no_event_on_no_hit():
    """No SL/TP event when active order is NOT hit."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    state.simulated_orders.append({
        'trace_id': 'TEST:1:100',
        'symbol': 'XAUUSD',
        'side': 'BUY',
        'entry_price': 2000.0,
        'sl': 1990.0,
        'tp': 2020.0,
        'status': 'ACTIVE',
        'pnl': 0.0,
        'close_time': None,
        'exit_price': None,
    })

    # Candle within SL/TP range — no hit
    candle = {'h': '2005', 'l': '1995', 'c': '2003', 't': '1709300060'}
    run(tm.update_orders("XAUUSD", candle, state))

    assert tm.last_tick_events == [], f"Expected no events, got {tm.last_tick_events}"


def test_pending_ai_no_order_opened():
    """PENDING_AI status should NOT emit ORDER_OPENED (not yet active)."""
    r = FakeRedis()
    tm = SimulatedTradeManager(r)
    state = MockState()

    trigger = {
        'strategy_id': 1,
        'strategy': 'test_strategy',
        'origin_timestamp': '1709300000',
        'side': 'BUY',
        'exit_config': {},
        'ai_validation': True,
    }

    # With ai_validator present, status = PENDING_AI
    run(tm.process_triggers("XAUUSD", [trigger], state, ai_validator="mock"))

    assert "ORDER_OPENED" not in tm.last_tick_events, \
        f"PENDING_AI should not emit ORDER_OPENED, got {tm.last_tick_events}"


# --- Runner ---

if __name__ == "__main__":
    tests = [
        test_init_has_last_tick_events,
        test_order_opened_event,
        test_order_open_payload_contains_bridge_contract_fields,
        test_sl_hit_event,
        test_tp_hit_event,
        test_clear_events_externally,
        test_trade_execution_unchanged,
        test_sl_tp_calculation_unchanged,
        test_compatible_with_event_filter,
        test_no_event_on_no_hit,
        test_pending_ai_no_order_opened,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1

    print(f"\n--- Results: {passed} PASSED, {failed} FAILED ---")
