import redis
import json

r = redis.Redis(host='redis', port=6379, decode_responses=True)
keys = r.keys("aureus:state:*")

for key in sorted(keys):
    symbol = key.split(":")[-1]
    data = r.get(key)
    if not data: continue
    
    state = json.loads(data)
    obs = state.get('obs', [])
    swing_points = state.get('swing_points', [])
    chochs = [sp for sp in swing_points if sp.get('is_choch')]
    bos = [sp for sp in swing_points if sp.get('is_bos')]
    
    print(f"{symbol}:")
    print(f"  Total OBs: {len(obs)}")
    print(f"  CHOCHs in Swing Points: {len(chochs)}")
    print(f"  BOS in Swing Points: {len(bos)}")
