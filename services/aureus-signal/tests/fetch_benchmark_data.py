import pandas as pd
import asyncpg
import json
import asyncio
import os
from datetime import datetime, timedelta

# Try both dev and prod ports
DB_PORTS = [5433, 5432]
DB_USER = "aureus"
DB_NAME = "aureus"
DB_PASS = "aureus_password"
HOST = "localhost"

TARGET_SYMBOLS = ["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD"]
CANDLE_COUNT = 2000

async def fetch_data_for_port(port):
    dsn = f"postgresql://{DB_USER}:{DB_PASS}@{HOST}:{port}/{DB_NAME}"
    conn = None
    try:
        print(f"Attempting to connect to {HOST}:{port}...")
        conn = await asyncpg.connect(dsn, timeout=5)
        print(f"Connected to PostgreSQL on port {port}")
        
        benchmark_data = {}
        
        for symbol in TARGET_SYMBOLS:
            print(f"Fetching data for {symbol}...")
            query = """
                SELECT time, open, high, low, close, volume
                FROM aureus_candles
                WHERE symbol = $1
                ORDER BY time DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, symbol, CANDLE_COUNT)
            
            if not rows:
                print(f"No data found for {symbol} on port {port}")
                continue
            
            candles = []
            for row in reversed(rows):
                candles.append({
                    "t": int(row['time'].timestamp()),
                    "o": float(row['open']),
                    "h": float(row['high']),
                    "l": float(row['low']),
                    "c": float(row['close']),
                    "v": float(row['volume'])
                })
            
            if candles:
                benchmark_data[symbol] = candles
                print(f"Successfully fetched {len(candles)} candles for {symbol}")
        
        if benchmark_data:
            output_path = "/mnt/d/Aureus/services/aureus-signal/tests/benchmark_data_golden.json"
            # Ensure directory exists in WSL context if needed, but here it's /mnt/d
            with open(output_path, "w") as f:
                json.dump(benchmark_data, f, indent=4)
            print(f"Golden dataset saved to {output_path}")
            return True
        return False
    except Exception as e:
        print(f"Failed on port {port}: {e}")
        return False
    finally:
        if conn:
            await conn.close()

async def main():
    for port in DB_PORTS:
        if await fetch_data_for_port(port):
            print("Extraction successful.")
            break
    else:
        print("Failed to extract data from all ports.")

if __name__ == "__main__":
    asyncio.run(main())
