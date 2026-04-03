---
phase: "15.5"
plan: "01"
title: "Data Export & Test Fixtures"
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/scripts/export_candle_fixtures.py
  - services/aureus-signal/tests/fixtures/.gitkeep
autonomous: true
requirements_addressed: [STRATQA-02, STRATQA-03, STRATQA-04, STRATQA-05]
---

<objective>
Export historical candle data from TimescaleDB (`aureus_candles`) as frozen CSV fixtures committed to the repo. These CSV files serve as deterministic test data for scenario tests, determinism tests, and the replay tool — ensuring all downstream tests use identical data regardless of when they run.
</objective>

<must_haves>
- Python script that connects to TimescaleDB and exports 2000 M1 bars per symbol as CSV
- CSV files committed to `services/aureus-signal/tests/fixtures/candles_{SYMBOL}.csv`
- Export all symbols currently in the database
- CSV format: `t,o,h,l,c,v` with `t` as unix timestamp integer
- Script is rerunnable (overwrites existing CSVs)
</must_haves>

---

<task id="15.5-01-T1" title="Create export script">
<read_first>
- services/aureus-signal/engine/live_engine.py (lines 269-275 for DB query pattern)
- services/aureus-signal/symbols.json (available symbols and config)
</read_first>

<action>
Create `services/aureus-signal/scripts/export_candle_fixtures.py`:

```python
"""Export candle data from TimescaleDB as frozen CSV test fixtures."""
import asyncio
import os
import csv
import asyncpg
from dotenv import load_dotenv

load_dotenv()

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
BARS_PER_SYMBOL = 2000

async def export_all():
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    pool = await asyncpg.create_pool(db_dsn)

    # Discover all symbols in the database
    symbols = await pool.fetch(
        "SELECT DISTINCT symbol FROM aureus_candles WHERE timeframe = 'M1' ORDER BY symbol"
    )

    os.makedirs(EXPORT_DIR, exist_ok=True)

    for row in symbols:
        symbol = row["symbol"]
        candles = await pool.fetch("""
            SELECT
                EXTRACT(EPOCH FROM time)::BIGINT AS t,
                open AS o, high AS h, low AS l, close AS c, volume AS v
            FROM aureus_candles
            WHERE symbol = $1 AND timeframe = 'M1'
            ORDER BY time DESC
            LIMIT $2
        """, symbol, BARS_PER_SYMBOL)

        # Reverse to chronological order
        candles = list(reversed(candles))

        filepath = os.path.join(EXPORT_DIR, f"candles_{symbol}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["t", "o", "h", "l", "c", "v"])
            for c in candles:
                writer.writerow([c["t"], c["o"], c["h"], c["l"], c["c"], c["v"]])

        print(f"Exported {len(candles)} bars for {symbol} → {filepath}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(export_all())
```

Create `services/aureus-signal/tests/fixtures/.gitkeep` (empty file to track directory).
</action>

<acceptance_criteria>
- `services/aureus-signal/scripts/export_candle_fixtures.py` exists and contains `async def export_all()`
- File contains `BARS_PER_SYMBOL = 2000`
- CSV header line is `t,o,h,l,c,v`
- Running `python scripts/export_candle_fixtures.py` from `services/aureus-signal/` produces CSV files in `tests/fixtures/`
- Each CSV file has ≤2001 lines (1 header + up to 2000 data rows)
- `tests/fixtures/.gitkeep` exists
</acceptance_criteria>
</task>

<task id="15.5-01-T2" title="Run export and commit fixtures">
<read_first>
- services/aureus-signal/scripts/export_candle_fixtures.py
</read_first>

<action>
Run the export script from `services/aureus-signal/`:
```bash
cd services/aureus-signal
python scripts/export_candle_fixtures.py
```

Verify the exported files:
```bash
wc -l tests/fixtures/candles_*.csv
head -2 tests/fixtures/candles_XAUUSD.csv
```

Expected output format:
```
t,o,h,l,c,v
1710000000,2050.50,2055.00,2048.00,2053.00,1500
```

Commit the fixture files to the repository.
</action>

<acceptance_criteria>
- At least one CSV file exists: `tests/fixtures/candles_XAUUSD.csv`
- First line of each CSV is `t,o,h,l,c,v`
- Each file has between 100 and 2001 lines
- Files are committed to git
</acceptance_criteria>
</task>

---

<verification>
1. Script file exists at expected path
2. Script runs without errors when TimescaleDB is accessible
3. CSV files are valid (header + numeric data rows)
4. Data is chronologically ordered (t values ascending)
</verification>
