import asyncio
import json
import logging
import sys
from unittest.mock import MagicMock, AsyncMock
import pandas as pd

from engine.strategies.registry import StrategyRegistry
from engine.strategies.template import TemplateStrategy
from engine.state import SymbolState, CandleRecord
from engine.orders import SimulatedTradeManager

logging.basicConfig(level=logging.DEBUG)

async def run_test():
    config = {
        "name": "TREND_CONT_BULL",
        "description": "High-probability SMC Trend Continuation.",
        "min_score_threshold": 0,
        "context_filters": [],
        "sequence": [
            {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
        ],
        "trade_execution": {
            "size": 2.0,
            "sl": {"type": "FIXED_PIPS", "value": 500},
            "tp": {"type": "RR_RATIO", "value": 3.0},
            "trailing": {"type": "SWING_LOW", "activation_pips": 300},
            "capital_risk_pct": 1.0,
            "early_exits": ["choch_down"]
        }
    }
    
    config["min_score_threshold"] = 3.0
    strategy = TemplateStrategy(config)
    registry = StrategyRegistry()
    registry.register(strategy)
    
    state = SymbolState("EURUSD")
    state.last_candle = {"t": 1000, "c": 1.1}
    
    r_mock = AsyncMock()
    r_mock.sismember.return_value = False
    manager = SimulatedTradeManager(r_mock)
    
    # ================= Candle 1 =================
    record = CandleRecord(t=1000, price=1.1)
    state.map_signal_to_candle_record(record, tag="choch_up", value="choch", data={"test": 1})
    state.log_signal_normalize_add(record)
    
    df1 = pd.DataFrame([{"t": 1000, "c": 1.1}])
    print("\n--- Candle 1 ---")
    res1 = registry.evaluate_all(df1, {}, state)
    if res1:
        await manager.process_triggers("EURUSD", res1, state)
    print("simulated orders candle 1:", len(state.simulated_orders))
        
    # ================= Candle 2 =================
    # Simulate candle 2 with choch_up again
    state.last_candle = {"t": 1060, "c": 1.2}
    record2 = CandleRecord(t=1060, price=1.2)
    state.map_signal_to_candle_record(record2, tag="choch_up", value="choch", data={"test": 2})
    state.log_signal_normalize_add(record2)
    
    df2 = pd.DataFrame([{"t": 1000, "c": 1.1}, {"t": 1060, "c": 1.2}])
    print("\n--- Candle 2 ---")
    res2 = registry.evaluate_all(df2, {}, state)
    if res2:
        await manager.process_triggers("EURUSD", res2, state)
        
    print("\nTotal simulated orders:", len(state.simulated_orders))
    for order in state.simulated_orders:
        print(f"Order trace_id: {order['trace_id']}, time: {order['open_time']}")

if __name__ == "__main__":
    asyncio.run(run_test())
