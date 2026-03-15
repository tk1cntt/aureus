"""
Clear ALL live signal data — Redis state + DB snapshots + checkpoints.
Engine sẽ tự warm-up lại từ đầu (1500 candles) khi restart.

Usage (WSL):
  docker cp reset_all_live.py aureus-signal:/app/reset_all_live.py
  docker exec aureus-signal python /app/reset_all_live.py
"""
import asyncio
import os
import json
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    print(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

    # 1. Clear ALL aureus:state:* keys
    state_keys = list(r.scan_iter("aureus:state:*"))
    if state_keys:
        r.delete(*state_keys)
        print(f"🗑️  Deleted {len(state_keys)} state keys: {state_keys}")
    else:
        print("ℹ️  No state keys found")

    # 2. Clear ALL aureus:checkpoint:* keys
    cp_keys = list(r.scan_iter("aureus:checkpoint:*"))
    if cp_keys:
        r.delete(*cp_keys)
        print(f"🗑️  Deleted {len(cp_keys)} checkpoint keys: {cp_keys}")
    else:
        print("ℹ️  No checkpoint keys found")

    # 3. Clear feature flags (reset to defaults)
    flag_keys = list(r.scan_iter("aureus:config:*"))
    if flag_keys:
        r.delete(*flag_keys)
        print(f"🗑️  Deleted {len(flag_keys)} config/flag keys: {flag_keys}")
    else:
        print("ℹ️  No config keys found")

    # 4. Clear precompute status keys
    precompute_keys = list(r.scan_iter("aureus:precompute:*"))
    if precompute_keys:
        r.delete(*precompute_keys)
        print(f"🗑️  Deleted {len(precompute_keys)} precompute keys")
    else:
        print("ℹ️  No precompute keys found")

    print("\n" + "=" * 50)
    print("✅ Redis cleared. Engine sẽ warm-up lại từ đầu khi restart.")
    print("💡 Chạy: docker restart aureus-signal")

if __name__ == "__main__":
    main()
