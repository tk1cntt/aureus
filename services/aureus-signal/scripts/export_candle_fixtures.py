"""Export candle data from TimescaleDB as frozen CSV test fixtures.

Usage:
    cd services/aureus-signal
    python scripts/export_candle_fixtures.py
"""
import asyncio
import os
import csv
import asyncpg
from dotenv import load_dotenv

load_dotenv()

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
BARS_PER_SYMBOL = 2000


async def export_all():
    db_dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://aureus:aureus_password@localhost:5433/aureus",
    )
    pool = await asyncpg.create_pool(db_dsn)

    # Discover all symbols with M1 data
    symbols = await pool.fetch(
        "SELECT DISTINCT symbol FROM aureus_candles WHERE timeframe = 'M1' ORDER BY symbol"
    )

    os.makedirs(EXPORT_DIR, exist_ok=True)

    for row in symbols:
        symbol = row["symbol"]
        candles = await pool.fetch(
            """
            SELECT
                EXTRACT(EPOCH FROM time)::BIGINT AS t,
                open AS o, high AS h, low AS l, close AS c, volume AS v
            FROM aureus_candles
            WHERE symbol = $1 AND timeframe = 'M1'
            ORDER BY time DESC
            LIMIT $2
            """,
            symbol,
            BARS_PER_SYMBOL,
        )

        # Reverse to chronological order (oldest first)
        candles = list(reversed(candles))

        filepath = os.path.join(EXPORT_DIR, f"candles_{symbol}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["t", "o", "h", "l", "c", "v"])
            for c in candles:
                writer.writerow([c["t"], c["o"], c["h"], c["l"], c["c"], c["v"]])

        print(f"Exported {len(candles)} bars for {symbol} -> {filepath}")

    await pool.close()
    print("\nExport complete.")


if __name__ == "__main__":
    asyncio.run(export_all())
