import asyncio
import asyncpg
import redis.asyncio as aioredis
import json
import os
import sys
from datetime import datetime, timezone, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CandleSimulator")

# Prod DB Connect Info
PROD_DB_HOST = os.getenv("PROD_DB_HOST", "localhost")
PROD_DB_PORT = os.getenv("PROD_DB_PORT", "5432")
PROD_DB_USER = os.getenv("PROD_DB_USER", "aureus")
PROD_DB_PASSWORD = os.getenv("PROD_DB_PASSWORD", "aureus_password")
PROD_DB_NAME = os.getenv("PROD_DB_NAME", "aureus")

# Dev Redis Connect Info 
DEV_REDIS_HOST = os.getenv("DEV_REDIS_HOST", "localhost")
DEV_REDIS_PORT = int(os.getenv("DEV_REDIS_PORT", "6380"))

# Config
SYMBOLS = os.getenv("SYMBOLS", "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD").split(",")
TICK_INTERVAL = float(os.getenv("TICK_INTERVAL", "1.0")) # seconds

async def get_db_pool():
    dsn = f"postgresql://{PROD_DB_USER}:{PROD_DB_PASSWORD}@{PROD_DB_HOST}:{PROD_DB_PORT}/{PROD_DB_NAME}"
    return await asyncpg.create_pool(dsn)

async def simulate_symbol(symbol: str, pool, r):
    logger.info(f"[{symbol}] Starting simulation...")
    
    checkpoint_key = f"simulator:checkpoint:{symbol}"
    
    async with pool.acquire() as conn:
        # Check Dev Redis for existing checkpoint
        saved_cp = await r.get(checkpoint_key)
        
        if saved_cp:
            last_processed_time = datetime.fromtimestamp(int(saved_cp), tz=timezone.utc)
            logger.info(f"[{symbol}] Resuming simulation from Dev Checkpoint: {last_processed_time}")
        else:
            # Get the max time in the DB to find a good starting point if no checkpoint
            max_time_row = await conn.fetchrow('SELECT MAX(time) as max_time FROM aureus_candles WHERE symbol = $1', symbol)
            
            # Retry loop if Prod DB is empty
            while not max_time_row or not max_time_row['max_time']:
                logger.warning(f"[{symbol}] No candles found in Prod DB. Retrying in 10s...")
                await asyncio.sleep(10)
                max_time_row = await conn.fetchrow('SELECT MAX(time) as max_time FROM aureus_candles WHERE symbol = $1', symbol)
                
            max_time = max_time_row['max_time']
            if max_time.tzinfo is None:
                max_time = max_time.replace(tzinfo=timezone.utc)
                
            last_processed_time = max_time - timedelta(minutes=1500)
            logger.info(f"[{symbol}] No checkpoint. Starting from 1500 mins ago: {last_processed_time}")
        
        while True:
            # Fetch candles chronological order
            query = """
                SELECT * FROM aureus_candles 
                WHERE symbol = $1 AND time > $2 
                ORDER BY time ASC LIMIT 500
            """
            rows = await conn.fetch(query, symbol, last_processed_time)
            
            if not rows:
                # Reached the current tip. Wait for new candles from Prod DB MT5
                await asyncio.sleep(5)
                continue
                
            for row in rows:
                candle_time = row['time']
                if candle_time.tzinfo is None:
                    candle_time = candle_time.replace(tzinfo=timezone.utc)
                
                # Format to stream event compatible with aureus-db-writer/aureus-signal
                event_data = {
                    "symbol": symbol,
                    "time": str(int(candle_time.timestamp())),
                    "open": str(row['open']),
                    "high": str(row['high']),
                    "low": str(row['low']),
                    "close": str(row['close']),
                    "tick_volume": str(row['tick_volume'])
                }
                
                stream_name = f"aureus:stream:{symbol}:candle"
                await r.xadd(stream_name, event_data)
                
                # Simulate realistic ticketing speed
                # Fast forward for old data, wait tick interval for near-real-time
                now_utc = datetime.now(timezone.utc)
                if (now_utc - candle_time).total_seconds() > 300: # Catching up historic
                    await asyncio.sleep(0.01)
                else:
                    await asyncio.sleep(TICK_INTERVAL)
                
                last_processed_time = candle_time
                await r.set(checkpoint_key, int(last_processed_time.timestamp()))

async def main():
    logger.info("==================================================")
    logger.info("🚀 Starting Aureus Dev Candle Simulator")
    logger.info("Reading from PROD DB -> Pushing to DEV Redis")
    logger.info("==================================================")
    
    pool = await get_db_pool()
    r = aioredis.Redis(host=DEV_REDIS_HOST, port=DEV_REDIS_PORT, decode_responses=True)
    
    try:
        await r.ping()
        logger.info(f"✅ Connected to Dev Redis at {DEV_REDIS_HOST}:{DEV_REDIS_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Dev Redis: {e}")
        sys.exit(1)
        
    tasks = []
    for symbol in SYMBOLS:
        tasks.append(simulate_symbol(symbol.strip(), pool, r))
        
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
