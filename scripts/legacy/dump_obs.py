import redis
import json

r = redis.Redis(host='127.0.0.1', port=6379, db=0)

# Keys are like aureus:state:XAUUSD
keys = r.keys("aureus:state:*")

for key in keys:
    data = r.get(key)
    if data:
        state = json.loads(data)
        print(f"--- SYMBOL: {state.get('symbol')} ---")
        obs = state.get('obs', [])
        print(f"Found {len(obs)} Order Blocks")
        for i, ob in enumerate(obs[-5:]): # Just last 5
            print(f"OB {i}: Type={ob['type']}, Start={ob['t_start']}, Break={ob.get('breakout_t')}, Top={ob['top']}, Bottom={ob['bottom']}")
