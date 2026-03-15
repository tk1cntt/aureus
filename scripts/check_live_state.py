"""Check Redis state directly for signal data."""
import redis
import json
import os
import sys

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=int(os.getenv("REDIS_PORT", 6380)), decode_responses=True)

symbol = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"

# 1. Check state key
state_raw = r.get(f"aureus:state:{symbol}")
if state_raw:
    state = json.loads(state_raw)
    print(f"✅ aureus:state:{symbol} EXISTS")
    print(f"   OBs: {len(state.get('obs', []))}")
    print(f"   FVGs: {len(state.get('fvgs', []))}")
    print(f"   Swing Points: {len(state.get('swing_points', []))}")
    print(f"   Signal History: {len(state.get('signal_history', []))}")
    print(f"   Last Candle: {state.get('last_candle', {}).get('t', 'N/A')}")
    print(f"   Candle Actors: {len(state.get('candle_actors', {}))}")
    print(f"   Active Orders: {len(state.get('active_orders', []))}")
    
    if state.get('obs'):
        print(f"\n   Sample OB: {json.dumps(state['obs'][0], indent=4)}")
    if state.get('swing_points') and len(state['swing_points']) > 0:
        print(f"\n   Last 3 Swing Points:")
        for sp in state['swing_points'][-3:]:
            print(f"     {sp.get('type','?')} @ {sp.get('price','?')} t={sp.get('t','?')}")
    if state.get('signal_history'):
        print(f"\n   Last 5 Signals:")
        for sig in state['signal_history'][:5]:
            print(f"     {sig.get('tag','?')} @ t={sig.get('t','?')}")
else:
    print(f"❌ aureus:state:{symbol} NOT FOUND IN REDIS")

# 2. Check checkpoint
cp_raw = r.get(f"aureus:checkpoint:{symbol}")
if cp_raw:
    cp = json.loads(cp_raw)
    print(f"\n✅ Checkpoint: last_processed_time={cp.get('last_processed_time')}")
else:
    print(f"\nℹ️  No checkpoint for {symbol}")

# 3. List all state keys
all_state_keys = list(r.scan_iter("aureus:state:*"))
print(f"\n📋 All state keys in Redis: {all_state_keys}")
