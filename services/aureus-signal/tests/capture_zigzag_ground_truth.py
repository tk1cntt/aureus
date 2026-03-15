import asyncio
import asyncpg
import pandas as pd
import json
import os
import sys
from datetime import datetime

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.common.zigzag_pro2 import ZigZagPro

async def capture():
    # Pivot: Use real CSV data since DB connection is refused
    csv_path = "mql5/XAUUSD/DAT_MT_XAUUSD_M1_202602.csv"
    symbol = "XAUUSD"
    limit = 1000 
    
    print(f"Reading {limit} real candles from {csv_path}...")
    
    try:
        if not os.path.exists(csv_path):
            print(f"❌ CSV file not found: {csv_path}")
            return

        # MT5 CSV Format: Date,Time,Open,High,Low,Close,Vol
        df_raw = pd.read_csv(csv_path, header=None, nrows=limit)
        df_raw.columns = ['date', 'time', 'o', 'h', 'l', 'c', 'v']
        
        # Prepare DataFrame 
        data = []
        for _, row in df_raw.iterrows():
            # Parse '2026.02.01 18:06' -> unix int
            dt_str = f"{row['date']} {row['time']}"
            dt_obj = datetime.strptime(dt_str, "%Y.%m.%d %H:%M")
            ts_unix = int(dt_obj.timestamp())
            
            data.append({
                't': ts_unix,
                'o': float(row['o']),
                'h': float(row['h']),
                'l': float(row['l']),
                'c': float(row['c']),
                'v': int(row['v'])
            })
        df = pd.DataFrame(data)
        
        # Run Legacy ZigZag in BATCH mode
        params = {
            "ext_period": 5,
            "min_amplitude": 100,
            "min_motion": 1,
            "point": 0.01,
            "digits": 2
        }
        engine = ZigZagPro(**params)
        buffers = engine.update(df, incremental=False)
        
        # Save Ground Truth
        output = {
            "symbol": symbol,
            "params": params,
            "candles": data,
            "expected": {
                "up": [float(v) for v in buffers['up']],
                "dn": [float(v) for v in buffers['dn']],
                "type": [int(v) for v in buffers['type']]
            }
        }
        
        with open("services/aureus-signal/tests/zigzag_ground_truth.json", "w") as f:
            json.dump(output, f, indent=2)
            
        print(f"✅ Successfully captured ground truth to services/aureus-signal/tests/zigzag_ground_truth.json")
        print(f"Candles processed: {len(df)}")

    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(capture())
