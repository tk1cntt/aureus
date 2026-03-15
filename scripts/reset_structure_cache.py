"""
Reset CHOCH/BOS/OB Cache in Redis
==================================
Clears stale structure metadata from Redis state that was generated
by the buggy CHOCH/BOS logic. After clearing, the signal engine will
re-detect all CHOCH/BOS events from scratch on next candle processing.

Usage: Run inside aureus-signal container or locally with Redis access.
  python reset_structure_cache.py
"""
import redis
import json
import sys

import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))

# Fields to strip from each swing point
STRUCTURE_FIELDS = [
    'is_choch', 'choch_type', 'breakout_t',
    'chochConfirmingPointIndex', 'chochZoneBasePointIndex',
    'is_bos', 'bos_type'
]

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    try:
        r.ping()
        print(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except redis.ConnectionError:
        print(f"❌ Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        sys.exit(1)
    
    # Find all symbol state keys
    keys = list(r.scan_iter("aureus:state:*"))
    if not keys:
        print("⚠️  No aureus:state:* keys found in Redis")
        return
    
    print(f"📋 Found {len(keys)} symbol states: {[k.split(':')[-1] for k in keys]}")
    
    total_cleaned = 0
    total_obs_removed = 0
    
    for key in keys:
        symbol = key.split(':')[-1]
        raw = r.get(key)
        if not raw:
            print(f"  ⏭️  {symbol}: empty state, skipping")
            continue
        
        state = json.loads(raw)
        swing_points = state.get('swing_points', [])
        
        # --- Clean swing points ---
        sp_cleaned = 0
        for sp in swing_points:
            changed = False
            for field in STRUCTURE_FIELDS:
                if field in sp:
                    del sp[field]
                    changed = True
            if changed:
                sp_cleaned += 1
        
        # --- Remove ALL OBs (they were created by potentially wrong CHOCH/BOS logic) ---
        obs_before = len(state.get('obs', []))
        state['obs'] = []
        
        # --- Clear sweep targets (derived from OBs) ---
        if 'sweep_targets' in state:
            state['sweep_targets'] = []
        
        # --- Clear candle actors related to CHOCH/BOS ---
        actors = state.get('candle_actors', {})
        actors_to_remove = []
        for t_key, actor in actors.items():
            if actor.get('type') in ('CHOCH_BREAKOUT', 'BOS_BREAKOUT'):
                actors_to_remove.append(t_key)
        for t_key in actors_to_remove:
            del actors[t_key]
        
        # Save back to Redis
        r.set(key, json.dumps(state))
        
        total_cleaned += sp_cleaned
        total_obs_removed += obs_before
        
        print(f"  ✅ {symbol}: cleaned {sp_cleaned}/{len(swing_points)} swing points, "
              f"removed {obs_before} OBs, {len(actors_to_remove)} actors")
    
    print(f"\n{'='*50}")
    print(f"✅ DONE: {total_cleaned} swing points cleaned, {total_obs_removed} OBs removed")
    print(f"🔄 Signal engine will re-detect CHOCH/BOS on next candle cycle")
    print(f"💡 To force immediate recalculation, restart the signal engine:")
    print(f"   docker restart aureus-signal")

if __name__ == "__main__":
    main()
