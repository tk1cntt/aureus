#!/usr/bin/env python
"""
Debug script: Extract signal data for ORDER_FLOW_BULL on ETHUSD
Investigates why sweep_bull events in transient_signals are not matching
"""
import json
import redis
import sys
import os
from datetime import datetime

# Load .env
from dotenv import load_dotenv
load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT" if os.getenv("EXECUTION_MODE") == "production" else "DEV_REDIS_PORT", 6380))

def connect_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def extract_recent_signals(symbol="ETHUSD", limit=20):
    """Extract recent signal data from Redis streams."""
    r = connect_redis()
    
    stream_key = f"aureus:stream:{symbol}:signals"
    
    # Get recent entries
    entries = r.xrevrange(stream_key, count=limit)
    
    results = []
    for entry_id, data in entries:
        payload = json.loads(data.get("payload", "{}"))
        results.append({
            "entry_id": entry_id,
            "t": payload.get("t"),
            "timestamp": datetime.fromtimestamp(payload.get("t", 0)).strftime("%Y-%m-%d %H:%M:%S") if payload.get("t") else "N/A",
            "log_signal_normalize_count": len(payload.get("log_signal_normalize", [])),
            "transient_signals_keys": list(payload.get("transient_signals", {}).keys()),
            "current_signal_events": payload.get("current_signal", {}).get("signals", {}).get("events", []),
        })
        
        # Check for sweep events in log_signal_normalize
        sweep_in_log = []
        for rec in payload.get("log_signal_normalize", []):
            events = rec.get("signals", {}).get("events", [])
            for ev in events:
                if "sweep" in str(ev.get("tag", "")).lower() or "sweep" in str(ev.get("value", "")).lower():
                    sweep_in_log.append({
                        "t": rec.get("t"),
                        "tag": ev.get("tag"),
                        "value": ev.get("value"),
                    })
        
        results[-1]["sweep_events_in_log"] = sweep_in_log
        results[-1]["transient_sweep_data"] = payload.get("transient_signals", {}).get("sweep", {})
    
    return results

def analyze_order_flow_bull_config():
    """Get ORDER_FLOW_BULL strategy config."""
    import asyncpg
    import asyncio
    
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
    
    async def fetch_config():
        conn = await asyncpg.connect(db_dsn)
        try:
            config = await conn.fetchrow(
                "SELECT config FROM aureus_strategy_templates WHERE name = 'ORDER_FLOW_BULL'"
            )
            return config["config"] if config else None
        finally:
            await conn.close()
    
    return asyncio.run(fetch_config())

def main():
    print("="*80)
    print("ORDER_FLOW_BULL Debug - ETHUSD Signal Analysis")
    print("="*80)
    
    # Get strategy config
    print("\n📋 Fetching ORDER_FLOW_BULL config...")
    try:
        config = analyze_order_flow_bull_config()
        if config:
            print(f"   Sequence: {json.dumps(config.get('sequence', []), indent=6)}")
            print(f"   Min Score: {config.get('min_score_threshold', 'N/A')}")
        else:
            print("   ❌ Strategy config not found!")
    except Exception as e:
        print(f"   ⚠️  Could not fetch config: {e}")
    
    # Extract recent signals
    print("\n🔍 Extracting recent signals from Redis...")
    try:
        results = extract_recent_signals("ETHUSD", limit=10)
        
        output_file = "debug_order_flow_bull_ethusd.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"   ✅ Extracted {len(results)} signal entries")
        print(f"   💾 Saved to: {output_file}")
        
        # Print analysis
        print("\n📊 Analysis:")
        for i, entry in enumerate(results[:5]):  # Show first 5
            print(f"\n   [{i}] t={entry['t']} ({entry['timestamp']})")
            print(f"       log_signal_normalize: {entry['log_signal_normalize_count']} records")
            print(f"       transient_signals: {entry['transient_signals_keys']}")
            
            # Check if sweep_bull is in log
            if entry['sweep_events_in_log']:
                print(f"       ✅ sweep in log: {entry['sweep_events_in_log']}")
            else:
                print(f"       ❌ sweep NOT in log_signal_normalize!")
            
            # Check transient sweep
            if entry['transient_sweep_data']:
                ts_data = entry['transient_sweep_data']
                print(f"       📦 transient sweep: value={ts_data.get('value')}, status={ts_data.get('status')}")
            
            # Check current_signal events
            if entry['current_signal_events']:
                event_tags = [ev.get('tag') for ev in entry['current_signal_events']]
                print(f"       🎯 current_signal events: {event_tags}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("Investigation complete")
    print("="*80)

if __name__ == "__main__":
    main()
