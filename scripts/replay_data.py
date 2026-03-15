
import redis
import json
import re
from datetime import datetime, timezone

def replay():
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    stream_key = "aureus:stream:XAUUSD:candle"
    
    # 1. Clear existing stream to avoid confusion
    r.delete(stream_key)
    print(f"Cleared {stream_key}")

    # 2. Parse gateway.log
    # Example line: 2026-02-20 02:57:38,848 - aureus-gateway - DEBUG - [TCP] BACKFILL candle 3: 2026-02-19 03:58:00 @ 4984.99
    log_path = "/tmp/gateway.log"
    with open(log_path, 'r') as f:
        lines = f.readlines()

    candles_found = 0
    for line in lines:
        if "BACKFILL candle" in line:
            # Extract timestamp and price
            match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) @ ([\d.]+)", line)
            if match:
                dt_str = match.group(1)
                price = match.group(2)
                
                # Convert to unix ms
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                ts_ms = int(dt.timestamp() * 1000)
                
                candle_data = {
                    "type": "CANDLE",
                    "symbol": "XAUUSD",
                    "t": str(ts_ms),
                    "o": price,
                    "h": price,
                    "l": price,
                    "c": price,
                    "v": "100",
                    "tf": "M1"
                }
                
                r.xadd(stream_key, candle_data, maxlen=5000)
                candles_found += 1
    
    print(f"Replayed {candles_found} candles to {stream_key}")
    r.close()

if __name__ == "__main__":
    replay()
