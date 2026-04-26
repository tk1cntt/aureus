import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.simulated_orders import SimulatedTradeManager


class FakeRedis:
    def __init__(self):
        self._sets = {}

    async def sismember(self, key, member):
        return member in self._sets.get(key, set())

    async def sadd(self, key, member):
        self._sets.setdefault(key, set()).add(member)


class MockState:
    def __init__(self, close='2000'):
        self.last_candle = {'c': close, 't': '1709300000', 'o': '1999', 'h': '2001', 'l': '1998', 'v': '100'}
        self.symbol = 'XAUUSD'
        self.swing_points = [
            {'t': '1709299900', 'price': '1990', 'is_high': False, 'type': 'LL'},
        ]


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def pullback_trigger(side='BUY', strategy='LIMIT_PULLBACK_BULL'):
    return {
        'strategy_id': 101,
        'strategy': strategy,
        'origin_timestamp': '1709300000',
        'side': side,
        'entry_method': 'PULLBACK_50',
        'exit_config': {},
    }


def test_simulated_pullback_50_buy_uses_ll_to_trigger_high_midpoint():
    tm = SimulatedTradeManager(FakeRedis(), run_id='run-1')
    state = MockState(close='2000')

    opened = run(tm.process_triggers('XAUUSD', [pullback_trigger()], state))

    assert opened == 1
    assert tm.active_orders[0]['entry_price'] == 1995.5


def test_simulated_pullback_50_sell_uses_same_ll_to_trigger_high_midpoint():
    tm = SimulatedTradeManager(FakeRedis(), run_id='run-1')
    state = MockState(close='1994')

    opened = run(tm.process_triggers('XAUUSD', [pullback_trigger(side='SELL', strategy='LIMIT_PULLBACK_BEAR')], state))

    assert opened == 1
    assert tm.active_orders[0]['entry_price'] == 1995.5


def test_simulated_pullback_50_missing_ll_skips_order():
    tm = SimulatedTradeManager(FakeRedis(), run_id='run-1')
    state = MockState(close='2000')
    state.swing_points = []

    opened = run(tm.process_triggers('XAUUSD', [pullback_trigger()], state))

    assert opened == 0
    assert tm.active_orders == []


def test_simulated_pullback_50_wrong_side_skips_order():
    tm = SimulatedTradeManager(FakeRedis(), run_id='run-1')
    state = MockState(close='1995')

    opened = run(tm.process_triggers('XAUUSD', [pullback_trigger()], state))

    assert opened == 0
    assert tm.active_orders == []
