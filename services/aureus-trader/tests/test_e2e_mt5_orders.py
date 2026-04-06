"""Full E2E test — non-blocking listener collects all events."""
import redis
import json
import time
import threading

REDIS_HOST = "localhost"
REDIS_PORT = 6380

events = []
lock = threading.Lock()

def listen_events():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    ps = r.pubsub()
    ps.subscribe("aureus:mt5:events")
    start = time.time()
    for msg in ps.listen():
        if time.time() - start > 20:
            break
        if msg['type'] != 'message':
            continue
        data = json.loads(msg['data'])
        with lock:
            events.append(data)
        print(f"  [EVENT #{len(events)}] {data['type']:16s} {json.dumps(data)}")
        if data['type'] in ('ORDER_OPENED', 'ORDER_FAILED', 'ORDER_CLOSED'):
            print(f"  [RECEIVED TERMINAL STATE] -> {data['type']}")

    ps.unsubscribe()
    r.close()

listener = threading.Thread(target=listen_events, daemon=True)
listener.start()
time.sleep(1)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
ts = int(time.time())

# Get latest tick
tick = r.hgetall("aureus:latest:XAUUSD:tick")
if not tick or 'ask' not in tick:
    print("❌ Failed to get XAUUSD tick. Is EA running?")
    exit(1)
    
ask = float(tick['ask'])
print(f"\n[XAUUSD] Current Ask: {ask}")

sl = round(ask - 3.0, 2)
tp = round(ask + 3.0, 2)

print(f"\n=== TEST 1: OPEN_ORDER MARKET BUY with SL={sl} & TP={tp} ===")
cmd1 = {"type":"OPEN_ORDER","symbol":"XAUUSD","cmd_id":f"e2e-{ts}-buy",
        "direction":"BUY","order_type":"MARKET","volume":0.01,
        "price":0.0,"sl":sl,"tp":tp,"magic":99998,"comment":"E2E_SLTP"}
r.publish("aureus:mt5:commands", json.dumps(cmd1))

print("\n=== TEST 2: SENDING DUPLICATE ===")
time.sleep(1)
r.publish("aureus:mt5:commands", json.dumps(cmd1))

listener.join(timeout=30)
r.close()
print(f"\n{'='*60}")
print(f"TOTAL EVENTS: {len(events)}\n")
for i, ev in enumerate(events, 1):
    t = ev.get('type','?')
    cid = ev.get('cmd_id','N/A')
    reason = ev.get('reason','')
    ticket = ev.get('ticket','')
    price = ev.get('open_price','')
    info = f"reason={reason}" if reason else f"ticket={ticket} price={price}" if ticket else ""
    print(f"  {i}. {t:16s} cmd_id={cid:30s} {info}")

types = [e['type'] for e in events]
print(f"\nACK:          {types.count('ACK')}")
print(f"NACK:         {types.count('NACK')}")
print(f"ORDER_OPENED: {types.count('ORDER_OPENED')}")
print(f"ORDER_FAILED: {types.count('ORDER_FAILED')}")

checks = []
checks.append(("ACK received", types.count('ACK') >= 1))
checks.append(("ORDER result received", types.count('ORDER_OPENED') + types.count('ORDER_FAILED') >= 1))
checks.append(("NACK for duplicate", any(e.get('reason')=='DUPLICATE' for e in events)))

print(f"\n{'='*60}")
for name, ok in checks:
    print(f"  {'✅' if ok else '❌'} {name}")
print(f"\nOVERALL: {'PASS ✅' if all(c[1] for c in checks) else 'FAIL ❌'}")
