import sys
import os
import asyncio
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState
from engine.signals.pivots import PivotSignal

def generate_ohlc(num_candles, start_price=100.0, seed=42):
    """Generates simple OHLC data with a clear swing pattern."""
    times = pd.date_range("2024-01-01", periods=num_candles, freq="min")
    df = pd.DataFrame({
        "t": times.astype('int64') // 10**9,
        "o": [start_price] * num_candles,
        "h": [start_price + 1] * num_candles,
        "l": [start_price - 1] * num_candles,
        "c": [start_price] * num_candles
    })
    
    # Create a Low at 100
    df.loc[100, "l"] = 50.0
    df.loc[100, "h"] = 55.0
    
    # Create a High at 200
    df.loc[200, "h"] = 150.0
    df.loc[200, "l"] = 145.0
    
    # Create a Low at 300 (Higher Low)
    df.loc[300, "l"] = 80.0
    df.loc[300, "h"] = 85.0
    
    return df

async def test_combined_logic():
    print("--- Running Combined Integration Test (Story 11.1 + 9.8) ---")
    
    # 1. Initialize State and Signal
    symbol = "XAUUSD"
    state = SymbolState(symbol)
    pivot_signal = PivotSignal(ext_period=5, min_amplitude=30)
    
    # 2. Simulate PHASE 1: Normal Live Processing
    print("\nPhase 1: Initial Processing (Creating History)")
    df_initial = generate_ohlc(400)
    pivot_signal.calculate(df_initial, state)
    
    initial_pivots = state.swing_points
    print(f"Initial Pivots Count: {len(initial_pivots)}")
    for p in initial_pivots:
        print(f"  - {p['type']} at {p['t']} (Price: {p['price']})")
    
    # 3. Simulate PHASE 2: Gap occurs, and Recalculate is triggered from Checkpoint
    # In Story 9.8, the engine reads a Checkpoint (e.g. at t=350)
    checkpoint_time = df_initial.iloc[350]['t']
    print(f"\nPhase 2: Simulating Recalculate from Checkpoint {checkpoint_time}")
    
    # Wipe the zigzag_engine to simulate a "stateless" recalculate call (common in Integrity Task)
    state.zigzag_engine = None 
    # But keep the swing_points (as if restored from Snapshot/DB)
    
    # The recalculate logic (Story 11.1 fix) should fetch 1500 warmup + delta
    # Here we simulate the fetch of 400 candles (warmup) + 200 new candles (delta)
    df_warmup = df_initial.iloc[:400].copy() # Existing candles used as warmup
    df_delta = generate_ohlc(200, start_price=105.0) # New candles (Delta)
    df_delta['t'] = df_delta['t'] + (df_initial.iloc[-1]['t'] - df_initial.iloc[0]['t']) + 60
    
    # Add a new swing in Delta
    df_delta.loc[100, "h"] = 250.0 # New High
    df_delta.loc[100, "l"] = 245.0
    
    df_combined = pd.concat([df_warmup, df_delta]).reset_index(drop=True)
    
    print(f"Executing recalculate loop on {len(df_combined)} total candles (Warmup + Delta)")
    # In real live_engine.py, this would be the loop in `recalculate_all_signals`
    pivot_signal.calculate(df_combined, state)
    
    # 4. Verification
    print("\nPhase 3: Verification")
    final_pivots = state.swing_points
    print(f"Final Pivots Count: {len(final_pivots)}")
    
    # Assertions
    # 1. Old pivots (t < 350) must still exist
    historical_count = len([p for p in final_pivots if p['t'] < checkpoint_time])
    if historical_count >= 2:
        print(f"[PASS] Historical pivots before checkpoint preserved: {historical_count}")
    else:
        print(f"[FAIL] Historical pivots lost! Found only {historical_count}")
        return

    # 2. New high should be detected
    new_highs = [p for p in final_pivots if p['price'] >= 250]
    if new_highs:
        print(f"[PASS] New High from Recalculate batch detected at price {new_highs[0]['price']}")
    else:
        print("[FAIL] New High from Delta not detected!")
        return

    # 3. Check for duplicates (Idempotency)
    timestamps = [p['t'] for p in final_pivots]
    if len(timestamps) == len(set(timestamps)):
         print("[PASS] No duplicate pivots found in the merged list. Idempotency guaranteed.")
    else:
         print("[FAIL] Duplicate/Overlapping pivots detected in merge!")
         return

    print("\n[SUCCESS] Story 11.1 + 9.8 Interaction Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_combined_logic())
