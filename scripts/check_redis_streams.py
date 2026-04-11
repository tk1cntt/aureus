#!/usr/bin/env python
"""
Debug script: Check Redis stream state and consumer groups
"""
import redis
import os
import json
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT" if os.getenv("EXECUTION_MODE") == "production" else "DEV_REDIS_PORT", 6380))

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    symbols = os.getenv("SYMBOLS", "XAUUSD,BTCUSD,ETHUSD").split(",")
    group_name = "aureus-strategy-executor-group"
    
    print("="*80)
    print("Redis Stream State Analysis")
    print("="*80)
    
    for symbol in symbols:
        stream_key = f"aureus:stream:{symbol}:signals"
        
        print(f"\n📊 {symbol}:")
        
        # Stream length
        stream_len = r.xlen(stream_key)
        print(f"   Stream length: {stream_len} entries")
        
        # Check consumer group
        try:
            groups = r.xinfo_groups(stream_key)
            for group in groups:
                if group['name'] == group_name:
                    print(f"   Consumer Group: {group_name}")
                    print(f"     - Pending entries: {group['pending']}")
                    print(f"     - Last delivered ID: {group['last-delivered-id']}")
                    print(f"     - Consumers: {group['consumers']}")
        except redis.exceptions.ResponseError:
            print(f"   ⚠️  No consumer group found")
        
        # Check pending messages
        try:
            pending = r.xpending(stream_key, group_name)
            if pending['pending'] > 0:
                print(f"   🚨 PENDING MESSAGES: {pending['pending']}")
                # Get details of pending messages
                pending_details = r.xpending_range(stream_key, group_name, min='-', max='+', count=10)
                for pd in pending_details[:5]:
                    print(f"     - ID: {pd['message_id']}, consumer: {pd['consumer']}, times_delivered: {pd['times_delivered']}")
        except Exception as e:
            print(f"   No pending info: {e}")
        
        # Last 3 entries
        if stream_len > 0:
            last_entries = r.xrevrange(stream_key, count=3)
            print(f"   📝 Last {len(last_entries)} entries:")
            for entry_id, data in last_entries:
                payload = json.loads(data.get('payload', '{}'))
                print(f"     - {entry_id}: t={payload.get('t', 'N/A')}")
    
    print("\n" + "="*80)
    print("Analysis complete")
    print("="*80)
    
    # Recommendations
    print("\n💡 Recommendations:")
    print("   1. If 'Pending entries' > 0: Service crashed before ACKing messages")
    print("   2. If stream length is large: Aggregator writing faster than consumption")
    print("   3. Consider: Delete consumer group on restart to clear pending state")

if __name__ == "__main__":
    main()
