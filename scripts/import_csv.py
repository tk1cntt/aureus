import asyncio
import pandas as pd
import asyncpg
import redis.asyncio as redis
import json
import os
import sys

# Add signal engine path
sys.path.append(os.path.join(os.getcwd(), '..', '..', 'services', 'aureus-signal'))
try:
    from engine.state import SymbolState
    from engine.signals.pivots import PivotSignal
    from engine.signals.structure import StructureSignal
except ImportError:
    # Fallback if running from different directory
    sys.path.append(os.path.join(os.getcwd(), 'services', 'aureus-signal'))
    from engine.state import SymbolState
    from engine.signals.pivots import PivotSignal
    from engine.signals.structure import StructureSignal

# Configuration
CSV_PATH = "/mnt/e/Openclaw/aureus/workspace/aureus/mql5/XAUUSD/DAT_MT_XAUUSD_M1_202602.csv"
TARGET_DATE = "2026.02.13"
SYMBOL = "XAUUSD"

# DB Config (assuming running from WSL host accessing Docker ports)
DB_DSN = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5433/aureus")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380")

async def import_data():
    print(f"--- Starting Import for {SYMBOL} on {TARGET_DATE} ---")
    
    # 1. Read CSV
    print(f"Reading CSV from {CSV_PATH}...")
    try:
        # Read with pandas, manual parsing for speed/control
        # Assuming format: YYYY.MM.DD,HH:MM,Open,High,Low,Close,Vol
        df = pd.read_csv(CSV_PATH, header=None, names=['date', 'time', 'open', 'high', 'low', 'close', 'vol'])
        
        # Filter by date string directly first
        df = df[df['date'] == TARGET_DATE].copy()
        
        if df.empty:
            print("No data found for target date!")
            return

        print(f"Found {len(df)} rows for {TARGET_DATE}.")
        
        # Combine date and time to datetime and localize to UTC
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%Y.%m.%d %H:%M').dt.tz_localize('UTC')
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 2. Connect to DB and Redis
    print("Connecting to Infrastructure...")
    try:
        conn = await asyncpg.connect(DB_DSN)
        r = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Ensure TimescaleDB and Redis are exposed on localhost (ports 5432, 6379)")
        return

    # 3. Initialize Engine State
    state = SymbolState(SYMBOL)
    pivots_sig = PivotSignal(
        ext_period=5,         # iExtPeriod=5 (window size)
        min_amplitude=2,      # iMinAmplitude=2 (in broker points, NOT absolute price)
        min_motion=0,         # iMinMotion=0 (will default to 1 internally)
        point=0.01,           # _Point for XAUUSD
        digits=2,             # _Digits for XAUUSD
        timeframe="M1"        # Data timeframe
    )
    struct_sig = StructureSignal()
    
    # Prepare Buffer for DB Insert
    candles_to_insert = []
    
    # Keep track of last N candles for signal calculation
    history_window = []
    
    processed_count = 0
    total_rows = len(df)
    
    print(f"Processing {total_rows} candles...")

    for idx, row in df.iterrows():
        dt = row['datetime']
        ts_db = dt 
        ts_unix = int(dt.timestamp())
        
        o = float(row['open'])
        h = float(row['high'])
        l = float(row['low'])
        c = float(row['close'])
        v = int(row['vol'])
        
        candle = {
            "t": ts_unix, "o": o, "h": h, "l": l, "c": c, "v": v
        }
        
        # Prepare for DB insert
        # Table: time (timestamptz), symbol (text), open (double), high (double), low (double), close (double), volume (int)
        candles_to_insert.append((ts_db, SYMBOL, o, h, l, c, v))
        
        # Update Engine State
        # Feed candle to state tracker
        state.update_with_candle(candle)
        
        # Maintain history window for signal logic
        history_window.append(candle)
        if len(history_window) > 200:
            history_window.pop(0)
            
        history_df = pd.DataFrame(history_window)
        
        # Run Signals (every candle to simulate properly)
        # Note: Optimization - usually we run signals only on close, which CSV rows are (1m close).
        
        try:
            p_res = pivots_sig.calculate(history_df, state)
            if p_res:
                state.log_signal(p_res['tag'], candle['t'])
                # print(f"Pivot: {p_res}")
                
            s_res = struct_sig.calculate(history_df, state)
            if s_res:
                state.log_signal(s_res['tag'], candle['t'])
                # print(f"Structure: {s_res}")
        except Exception as e:
            # Catch signal errors to prevent crash
            pass
            
        processed_count += 1
        if processed_count % 100 == 0:
            print(f"Processed {processed_count}/{total_rows}...", end='\r')

    print(f"\nProcessing complete. Final State: {len(state.swing_points)} Swing Points, {len(state.obs)} OBs.")

    # 4. Insert into DB
    print(f"Inserting {len(candles_to_insert)} candles into TimescaleDB...")
    try:
        # Clear ALL data for this symbol to ensure we see the imported historic data
        # (Otherwise, recent "mock" data from seed scripts with newer timestamps will take precedence in "ORDER BY DESC")
        await conn.execute("DELETE FROM aureus_candles WHERE symbol = $1", SYMBOL)
        print(f"Cleared ALL existing data for {SYMBOL}.")

        # Batch Insert
        await conn.executemany("""
            INSERT INTO aureus_candles (time, symbol, open, high, low, close, volume, timeframe)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'M1')
        """, candles_to_insert)
        print("DB Insertion Success.")
    except Exception as e:
        print(f"DB Insertion Failed: {e}")

    # 5. Push State to Redis
    print("Pushing final state to Redis...")
    try:
        state_dict = state.to_dict()
        # Ensure json serializable
        await r.set(f"aureus:state:{SYMBOL}", json.dumps(state_dict))
        print("Redis Update Success.")
    except Exception as e:
        print(f"Redis Update Failed: {e}")

    await conn.close()
    await r.aclose()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(import_data())
