import asyncpg
import asyncio
from datetime import datetime, timedelta
import os

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "aureus")
POSTGRES_USER = os.getenv("POSTGRES_USER", "aureus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "aureus_secure_pass")

async def seed():
    print(f"Connecting to database at {POSTGRES_HOST}:{POSTGRES_PORT}...")
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        
        # Create table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS aureus_candles (
                time TIMESTAMPTZ NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                PRIMARY KEY (time, symbol, timeframe)
            );
            SELECT create_hypertable('aureus_candles', 'time', if_not_exists => TRUE);
        """)
        
        # Seed 100 dummy candles for XAUUSD M1
        now = datetime.now()
        data = []
        base_price = 2000.0
        for i in range(100):
            t = now - timedelta(minutes=100-i)
            o = base_price + (i * 0.5)
            h = o + 2.0
            l = o - 2.0
            c = o + 1.0
            data.append((t, "XAUUSD", "M1", o, h, l, c, 1000.0))
        
        await conn.executemany("""
            INSERT INTO aureus_candles (time, symbol, timeframe, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (time, symbol, timeframe) DO NOTHING
        """, data)
        
        print(f"Successfully seeded {len(data)} candles.")
        await conn.close()
    except Exception as e:
        print(f"Seeding error: {e}")

if __name__ == "__main__":
    asyncio.run(seed())
