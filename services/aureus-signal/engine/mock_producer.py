import logging
import json
import asyncio
import asyncpg
import redis.asyncio as redis
from datetime import datetime, timedelta

logger = logging.getLogger("mock-producer")

class CSVMockProducer:
    """
    Mock Producer that reads candles from DB (aureus_backtest_candles)
    and pushes them into a Redis Stream to simulate live trading.
    """
    def __init__(self, db_pool: asyncpg.Pool, redis_conn: redis.Redis, run_id: str, symbol: str, stream_key: str):
        self.db_pool = db_pool
        self.r = redis_conn
        self.run_id = run_id
        self.symbol = symbol.upper()
        self.stream_key = stream_key

    async def produce(self, start_dt: datetime, end_dt: datetime, timeframe: str = 'M1', batch_size: int = 500):
        """
        Queries candles from DB and pushes to Redis Stream using a cursor and pipeline.
        Features a 1440-candle EXACT pre-fetch warmup period to immune against weekend gaps.
        """
        logger.info(f"[MockProducer] Querying candles for {self.symbol} ({timeframe}) from {start_dt} to {end_dt} (Pre-fetching 1440 warmup candles)")
        
        # [Review Fix] Pre-validate data availability before creating cursor/pipeline
        # This avoids creating unnecessary Redis pipeline when no data exists.
        pre_check_query = """
            SELECT COUNT(*) FROM aureus_backtest_candles
            WHERE symbol = $1 AND timeframe = $2 AND time >= $3 AND time <= $4
        """
        try:
            async with self.db_pool.acquire() as check_conn:
                main_count = await check_conn.fetchval(pre_check_query, self.symbol, timeframe, start_dt, end_dt)
                if main_count == 0:
                    logger.warning(f"⚠️ No data found in database for {self.symbol} from {start_dt} to {end_dt}. Please run Story 3.1 Importer first.")
                    return False
                logger.info(f"[MockProducer] Found {main_count} main candles in DB")
        except Exception as e:
            logger.error(f"[MockProducer] Pre-check failed: {e}")
            return False
        
        # [Review Note] Stream Bounded Design:
        # Producer pushes in batches of `batch_size` (default 500) via Redis pipeline.
        # Consumer processes and XDEL messages after each candle, keeping stream size
        # bounded by consumer lag (typically < batch_size). This prevents OOM for long
        # backtests. See Story 3.3 Dev Notes for asyncio.gather concurrent design.
        #
        # Exact-row fetch using CTEs prevents Weekend/Holiday gap issues
        query = """
            WITH Warmup AS (
                SELECT time, symbol, timeframe, open, high, low, close, volume
                FROM aureus_backtest_candles
                WHERE symbol = $1 AND timeframe = $2 AND time < $3
                ORDER BY time DESC
                LIMIT 1440
            ), Main AS (
                SELECT time, symbol, timeframe, open, high, low, close, volume
                FROM aureus_backtest_candles
                WHERE symbol = $1 AND timeframe = $2 AND time >= $3 AND time <= $4
            )
            SELECT * FROM Warmup
            UNION ALL
            SELECT * FROM Main
            ORDER BY time ASC
        """
        
        count = 0
        try:
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    cursor = conn.cursor(query, self.symbol, timeframe, start_dt, end_dt)
                    
                    # Use Redis pipeline for high-performance writes
                    pipe = self.r.pipeline()
                    
                    async for record in cursor:
                        payload = {
                            "type": "CANDLE",
                            "symbol": record['symbol'],
                            "timeframe": record['timeframe'],
                            "t": record['time'].isoformat(),
                            "o": float(record['open']),
                            "h": float(record['high']),
                            "l": float(record['low']),
                            "c": float(record['close']),
                            "v": float(record['volume'])
                        }
                        
                        pipe.xadd(self.stream_key, {"payload": json.dumps(payload)})
                        count += 1
                        
                        # Execute in batches
                        if count % batch_size == 0:
                            await pipe.execute()
                            logger.info(f"[MockProducer] Pushed {count} candles to stream {self.stream_key}")

                    # Final execution
                    if count % batch_size != 0:
                        await pipe.execute()

            if count == 0:
                # [Note] Shouldn't reach here due to pre-check, but kept as safety net
                logger.warning(f"⚠️ No data found in database for {self.symbol} from {start_dt} to {end_dt}. Please run Story 3.1 Importer first.")
                return False

            logger.info(f"✅ Successfully pushed {count} candles to {self.stream_key}")
            return True
        except Exception as e:
            logger.error(f"[MockProducer] Error during production: {e}")
            return False
