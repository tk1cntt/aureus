import logging
import asyncpg
from typing import List, Dict, Any

logger = logging.getLogger("aureus-signal.gap-detector")

class GapDetector:
    def __init__(self, pg_pool: asyncpg.Pool):
        self.pg_pool = pg_pool

    async def find_gaps(self, symbol: str, timeframe: str = 'M1', lookback_hours: int = 24) -> List[Dict[str, Any]]:
        """Find missing data ranges in the last X hours."""
        query = """
        WITH time_series AS (
            SELECT generate_series(
                date_trunc('minute', now() - ($3::int * interval '1 hour')),
                date_trunc('minute', now() - interval '2 minutes'),
                interval '1 minute'
            ) AS bucket
        ),
        gaps AS (
            SELECT ts.bucket
            FROM time_series ts
            LEFT JOIN aureus_candles c 
              ON c.time = ts.bucket 
             AND c.symbol = $1 
             AND c.timeframe = $2
            WHERE c.time IS NULL
              -- Exclude Weekends (Friday 22:00 - Sunday 22:00 UTC)
              AND NOT (
                (EXTRACT(DOW FROM ts.bucket) = 5 AND EXTRACT(HOUR FROM ts.bucket) >= 22) OR
                (EXTRACT(DOW FROM ts.bucket) = 6) OR
                (EXTRACT(DOW FROM ts.bucket) = 0 AND EXTRACT(HOUR FROM ts.bucket) < 22)
              )
        ),
        gap_groups AS (
            SELECT bucket,
                   bucket - (ROW_NUMBER() OVER (ORDER BY bucket) * interval '1 minute') as grp
            FROM gaps
        )
        SELECT MIN(bucket) as start_time,
               MAX(bucket) as end_time,
               COUNT(*) as missing_count
        FROM gap_groups
        GROUP BY grp
        HAVING COUNT(*) > 1 -- Only care about gaps > 1 min
        ORDER BY start_time;
        """

        try:
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch(query, symbol, timeframe, lookback_hours)
                
                results = []
                for row in rows:
                    results.append({
                        "start": int(row['start_time'].timestamp() * 1000),
                        "end": int(row['end_time'].timestamp() * 1000),
                        "count": row['missing_count']
                    })
                return results
        except Exception as e:
            logger.error(f"Gap detection query failed for {symbol}: {e}")
            return []
