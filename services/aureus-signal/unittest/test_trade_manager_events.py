import unittest
import asyncio
from unittest.mock import MagicMock
from engine.simulated_orders import SimulatedTradeManager

class TestSimulatedTradeManagerEvents(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.r = MagicMock()
        self.r.sismember = MagicMock(return_value=asyncio.Future())
        self.r.sismember.return_value.set_result(False)
        self.r.sadd = MagicMock(return_value=asyncio.Future())
        self.r.sadd.return_value.set_result(True)
        
        self.tm = SimulatedTradeManager(r=self.r, run_id="test_run")

    async def test_order_opened_event(self):
        # Mock state object
        state = MagicMock()
        state.last_candle = {'t': 1000, 'c': 2000}
        state.symbol = "XAUUSD"
        
        # Trigger an order
        triggers = [{
            'strategy_id': 1,
            'strategy': 'TestStrategy',
            'origin_timestamp': 1000,
            'side': 'BUY',
            'exit_config': {'sl': {'mode': 'FIXED_PIPS', 'value': 100}, 'tp': {'mode': 'RR', 'value': 2}}
        }]
        
        await self.tm.process_triggers("XAUUSD", triggers, state)
        
        self.assertIn("ORDER_OPENED", self.tm.last_tick_events)

    async def test_sl_tp_hit_events(self):
        # Setup an active order
        order = {
            "trace_id": "XAUUSD:1:1000",
            "symbol": "XAUUSD",
            "side": "BUY",
            "entry_price": 2000,
            "sl": 1900,
            "tp": 2200,
            "open_time": 1000,
            "status": "ACTIVE"
        }
        self.tm.active_orders = [order]
        
        # Candle hitting SL
        candle_sl = {'t': 1001, 'o': 2000, 'h': 2005, 'l': 1850, 'c': 1860, 'v': 100}
        self.tm.update_orders("XAUUSD", candle_sl, MagicMock())
        self.assertIn("SL_HIT", self.tm.last_tick_events)
        
        # Reset and check TP
        self.tm.last_tick_events = []
        self.tm.active_orders = [order] # Re-add for test
        candle_tp = {'t': 1002, 'o': 2000, 'h': 2300, 'l': 1950, 'c': 2250, 'v': 100}
        self.tm.update_orders("XAUUSD", candle_tp, MagicMock())
        self.assertIn("TP_HIT", self.tm.last_tick_events)

if __name__ == '__main__':
    unittest.main()
