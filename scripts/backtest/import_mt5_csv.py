import asyncio
import argparse
import csv
import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mt5-csv-importer")

async def import_csv(file_path: str, symbol: str, timeframe: str = 'M1', chunk_size: int = 5000):
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@127.0.0.1:5433/aureus")
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    symbol = symbol.upper()
    logger.info(f"📂 Starting import: {file_path} (Symbol: {symbol}, TF: {timeframe})")

    # Connect to database
    try:
        pool = await asyncpg.create_pool(db_dsn)
        async with pool.acquire() as conn:
            # [Review Note] Using executemany instead of copy_records_to_table because we need
            # UPSERT (ON CONFLICT DO UPDATE) for idempotent re-imports. copy_from does not
            # support ON CONFLICT. The trade-off is slower bulk insert (~3-5x) but safe re-runs.
            query = """
                INSERT INTO aureus_backtest_candles (time, symbol, timeframe, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (time, symbol, timeframe) 
                DO UPDATE SET 
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """
            
            total_imported = 0
            rows = []
            start_time = asyncio.get_event_loop().time()
            
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for i, line in enumerate(reader):
                    if not line or len(line) < 7:
                        continue
                    
                    # [Review Fix] Skip header rows: if first column doesn't match
                    # date pattern YYYY.MM.DD, treat as header and skip
                    if i == 0 and not line[0][:4].isdigit():
                        logger.info(f"Skipping header row: {line}")
                        continue
                    
                    try:
                        # Format: YYYY.MM.DD,HH:MM,O,H,L,C,V
                        dt_str = f"{line[0]} {line[1]}"
                        # [Review Note] Timezone Convention: We store as UTC but this actually
                        # represents Broker Time (typically GMT+2/+3 for MT5). All components
                        # in the pipeline treat these timestamps consistently as "Broker Time
                        # stored in UTC container". No real timezone conversion occurs.
                        dt = datetime.strptime(dt_str, "%Y.%m.%d %H:%M").replace(tzinfo=timezone.utc)
                        
                        rows.append((
                            dt, symbol, timeframe,
                            float(line[2]), float(line[3]), float(line[4]), float(line[5]), float(line[6])
                        ))
                        
                        # Process in chunks
                        if len(rows) >= chunk_size:
                            await conn.executemany(query, rows)
                            total_imported += len(rows)
                            logger.info(f"📦 Imported {total_imported} candles...")
                            rows = []
                            
                    except (ValueError, IndexError) as ve:
                        logger.warning(f"Line {i+1}: Data error, skipping: {ve}")

                # Final chunk
                if rows:
                    await conn.executemany(query, rows)
                    total_imported += len(rows)
            
            end_time = asyncio.get_event_loop().time()
            logger.info(f"✅ Successfully imported/updated {total_imported} candles in {end_time - start_time:.2f}s")
            
        await pool.close()
    except Exception as e:
        logger.error(f"Database error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import MT5 CSV data into Backtest Database")
    parser.add_argument("--file", required=True, help="Path to MT5 CSV file")
    parser.add_argument("--symbol", required=True, help="Trading symbol (e.g., XAUUSD)")
    parser.add_argument("--timeframe", default="M1", help="Timeframe (default: M1)")
    parser.add_argument("--chunk", type=int, default=5000, help="Chunk size for batch insert (default: 5000)")
    
    args = parser.parse_args()
    asyncio.run(import_csv(args.file, args.symbol, args.timeframe, args.chunk))
