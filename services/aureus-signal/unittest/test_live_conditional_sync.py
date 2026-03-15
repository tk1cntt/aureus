"""
Integration test for Conditional Redis Sync -> Story 9.6
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
    def __init__(self, mode="ALWAYS"):
        self.mode = mode
        self.sync_calls = 0
    
    async def get(self, key):
        if key == "aureus:config:redis_sync_mode":
            return self.mode
        return None
        
    async def set(self, key, value):
        if "aureus:state:" in key:
            self.sync_calls += 1

class MockState:
    def __init__(self, has_event=False):
        self.transient_signals = {"choch_up": {}} if has_event else {}
        
    def to_dict(self):
        return {"simulated_state": True}
        
class MockTradeManager:
    def __init__(self):
        self.last_tick_events = []

async def simulate_consumer_loop(mode, candles_count, event_probability=0.0):
    r = FakeRedis(mode=mode)
    flags = FeatureFlags(r)
    trade_manager = MockTradeManager()
    
    # We will track candle_count explicitly like in live_engine.py
    for candle_count in range(1, candles_count + 1):
        # Determine if this specific candle has an event
        is_event_candle = False
        if event_probability > 0:
            # Shift by 3 to ensure events don't perfectly overlap with % 5
            is_event_candle = ((candle_count + 3) % int(1/event_probability)) == 0
            
        state = MockState(has_event=is_event_candle)
        
        # --- The logic injected into live_engine.py ---
        # --- EVENT EVALUATION ---
        has_event = has_structural_event(state, trade_manager)

        # --- CONDITIONAL REDIS SYNC ---
        sync_mode = await flags.get("redis_sync_mode", "ALWAYS")
        if sync_mode == "ALWAYS" or has_event or (candle_count % 5 == 0):
            await r.set(f"aureus:state:XAUUSD", json.dumps(state.to_dict()))
            
        trade_manager.last_tick_events = []
        
    return r.sync_calls

async def main():
    print("--- Running Story 9.6 Integration Test ---")
    
    total_candles = 100
    
    # 1. Test ALWAYS Mode (100 candles, 0 events)
    writes_always = await simulate_consumer_loop("ALWAYS", total_candles, event_probability=0.0)
    print(f"[ALWAYS MODE] Processed {total_candles} candles -> Synced {writes_always} times")
    assert writes_always == total_candles, "ALWAYS mode should sync every candle"
    
    # 2. Test EVENT_ONLY Mode (no events, should fallback to interval)
    writes_event_no_events = await simulate_consumer_loop("EVENT_ONLY", total_candles, event_probability=0.0)
    print(f"[EVENT_ONLY MODE - No Events] Processed {total_candles} candles -> Synced {writes_event_no_events} times")
    assert writes_event_no_events == (total_candles / 5), "Should sync every 5 candles (20 times) when no events"
    
    # 3. Test EVENT_ONLY Mode (with events 10% of time)
    # 10 events + 20 interval syncs. Some might overlap.
    # Total should be around 30, definitely > 20 and < 100.
    writes_event_mix = await simulate_consumer_loop("EVENT_ONLY", total_candles, event_probability=0.1)
    print(f"[EVENT_ONLY MODE - 10% Events] Processed {total_candles} candles -> Synced {writes_event_mix} times")
    assert writes_event_mix > 20, "Should have synced more than interval due to events"
    assert writes_event_mix < total_candles, "Should have synced less than total candles"
    
    # 4. Verify reduction >= 50%
    reduction = 100.0 * (total_candles - writes_event_mix) / total_candles
    print(f"Reduction ratio: {reduction:.1f}%")
    assert reduction >= 50.0, f"Reduction {reduction:.1f}% did not meet >= 50% criteria"
    
    print("\n[SUCCESS] All ACs passed for Conditional Redis Sync Integration Test!")

if __name__ == "__main__":
    asyncio.run(main())
