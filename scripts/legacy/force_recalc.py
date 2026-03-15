import redis
import json

r = redis.Redis(host='redis', port=6379, decode_responses=True)

symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY', 'ETHUSD', 'BTCUSD', 'USTEC']

for symbol in symbols:
    cmd = {
        "type": "REQUEST_BACKFILL_COUNT",
        "symbol": symbol,
        "count": 10000
    }
    # Publish and get subscriber count
    subs = r.publish("aureus:mt5:commands", json.dumps(cmd))
    print(f"Sent RECALCULATE command for {symbol}. Subscribers: {subs}")
