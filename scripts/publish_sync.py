import redis
import json
import time

r = redis.Redis(host='localhost', port=6388, db=0)

print("Publishing REQUEST_BACKFILL_COUNT for XAUUSD (force_full=True)...")
r.publish("aureus:mt5:commands", json.dumps({
    "type": "REQUEST_BACKFILL_COUNT",
    "symbol": "XAUUSD",
    "count": 5000,
    "force_full": True
}))
print("Publish sent!")
time.sleep(1)

