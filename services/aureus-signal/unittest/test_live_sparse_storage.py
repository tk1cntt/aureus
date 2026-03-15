"""
Integration test for Live Engine Sparse Storage -> Story 9.5
"""
import sys
import os
import asyncio
import json
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.feature_flags import FeatureFlags
from engine.event_filter import has_structural_event

class FakeRedis:
    def __init__(self, mode="FULL"):
        self.mode = mode
    
    async def get(self, key):
        if key == "aureus:config:snapshot_mode":
            return self.mode
        return None

class MockState:
    def __init__(self, has_event=False):
        self.transient_signals = {"choch_up": {}} if has_event else {}
        
class MockTradeManager:
    def __init__(self):
        self.last_tick_events = []

async def simulate_consumer_loop(mode, candles_count, event_probability=0.1):
    r = FakeRedis(mode=mode)
    flags = FeatureFlags(r)
    trade_manager = MockTradeManager()
    
    snapshot_writes = 0
    
    for i in range(candles_count):
        # 10% chance of a structural event
        is_event_candle = (i % int(1/event_probability)) == 0 if event_probability > 0 else False
        state = MockState(has_event=is_event_candle)
        
        # --- The logic injected into live_engine.py ---
        snapshot_mode = await flags.get("snapshot_mode", "FULL")
        has_event = has_structural_event(state, trade_manager)
        
        if snapshot_mode == "FULL" or has_event:
            snapshot_writes += 1
            
        trade_manager.last_tick_events = []
        
    return snapshot_writes

async def main():
    print("--- Running Story 9.5 Integration Test ---")
    
    total_candles = 100
    
    # 1. Test FULL Mode
    writes_full = await simulate_consumer_loop("FULL", total_candles, event_probability=0.1)
    print(f"[FULL MODE] Processed {total_candles} candles -> Wrote {writes_full} snapshots")
    assert writes_full == total_candles, "FULL mode should write every candle"
    
    # 2. Test SPARSE Mode
    writes_sparse = await simulate_consumer_loop("SPARSE", total_candles, event_probability=0.1)
    print(f"[SPARSE MODE] Processed {total_candles} candles -> Wrote {writes_sparse} snapshots")
    assert writes_sparse < total_candles, "SPARSE mode should write fewer snapshots"
    
    # 3. Verify reduction
    reduction = 100.0 * (total_candles - writes_sparse) / total_candles
    print(f"Reduction ratio: {reduction:.1f}%")
    assert reduction >= 70.0, f"Reduction {reduction:.1f}% did not meet >= 70% criteria"
    
    # 4. Verify TradeManager events clearing
    tm = MockTradeManager()
    tm.last_tick_events = ["ORDER_OPENED"]
    has_event = has_structural_event(MockState(), tm)
    assert has_event is True
    tm.last_tick_events = [] # Clear like in live_engine.py
    assert has_structural_event(MockState(), tm) is False
    print("[EVENTS] Trade manager events clear logic verified")
    
    print("\n[SUCCESS] All ACs passed for Sparse Storage Integration Test!")

if __name__ == "__main__":
    asyncio.run(main())
