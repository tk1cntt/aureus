import redis
import json
import time

r = redis.Redis(host='localhost', port=6380, decode_responses=True)

ts = int(time.time())
signal_event = {
    "type": "STRATEGY_MATCH",
    "symbol": "XAUUSD",
    "t": ts * 1000,
    "data": {
        "strategy_id": "test_e2e_strategy",
        "direction": "BUY",
        "entry_type": "MARKET",
        "size_value": 0.01,
        "magic_number": 99912,
        "sl_absolute": 2500.0,
        "tp_absolute": 2800.0
    }
}

print('Publishing STRATEGY_MATCH to aureus:signal:match')
r.publish('aureus:signal:match', json.dumps(signal_event))
print('Message published. Check aureus-trader logs for dispatch info and EA logs for execution.')
