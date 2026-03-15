import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState
from engine.signals.pivots import PivotSignal
from engine.signals.structure import StructureSignal

def generate_synthetic_data(num_candles=1000):
    """
    Generate synthetic OHLC data that clearly forms higher highs and higher lows,
    followed by a lower low to force a CHOCH.
    """
    times = pd.date_range("2024-01-01", periods=num_candles, freq="min")
    df = pd.DataFrame({"t": times.astype('int64') // 10**9})
    
    # Base straight line
    df["o"] = 100.0
    df["h"] = 101.0
    df["l"] = 99.0
    df["c"] = 100.0
    df["volume"] = 100
    
    # Create clear swings
    # Swing 1 (Low)
    df.loc[100, "l"] = 50.0
    df.loc[100, "h"] = 55.0
    
    # Swing 2 (High)
    df.loc[200, "h"] = 150.0
    df.loc[200, "l"] = 145.0
    
    # Swing 3 (Higher Low)
    df.loc[300, "l"] = 100.0
    df.loc[300, "h"] = 105.0
    
    # Swing 4 (Higher High)
    df.loc[400, "h"] = 200.0
    df.loc[400, "l"] = 195.0
    
    # Swing 5: Huge drop causing CHOCH (Lower Low)
    df.loc[500, "l"] = 40.0
    df.loc[500, "h"] = 45.0
    
    return df

def run_test():
    print("--- Running Integration Test: Historical Wipeout & State Hydration ---")
    
    df_full = generate_synthetic_data(1000)
    
    # Setup Signals
    # Use amplitude 40 so it catches the 50-point moves
    pivot_signal = PivotSignal(ext_period=5, min_amplitude=40)
    structure_signal = StructureSignal()
    
    # ---------------------------------------------------------
    # PART 1: Run normal continuous engine (Candles 0 to 600)
    # ---------------------------------------------------------
    print("\nPhase 1: Continuous Run (Simulating Pre-Crash Server)")
    state_v1 = SymbolState("XAUUSD")
    df_part1 = df_full.iloc[:600].copy()
    
    pivot_signal.calculate(df_part1, state_v1)
    structure_signal.calculate(df_part1, state_v1)
    
    original_pivots = state_v1.swing_points
    choch_pivots = [p for p in original_pivots if p.get('is_choch')]
    
    print(f"Total Pivots found in V1: {len(original_pivots)}")
    print(f"CHOCHs found in V1: {len(choch_pivots)}")
    
    if not choch_pivots:
        print("[ERROR] Test Data failed to generate a CHOCH!")
        return
        
    choch_timestamp = choch_pivots[0]['t']
    print(f"CHOCH detected at: {choch_timestamp}")
    
    # ---------------------------------------------------------
    # PART 2: Simulate Crash & Hydration (Candles 400 to 800)
    # ---------------------------------------------------------
    print("\nPhase 2: Hydration Run (Simulating Server Restart & Warmup)")
    # The Live Engine fetches the serialized swing_points from DB
    restored_swing_points = [dict(p) for p in original_pivots] 
    
    # But zigzag_engine buffer is destroyed (None)
    state_v2 = SymbolState("XAUUSD")
    state_v2.swing_points = restored_swing_points
    # state_v2.zigzag_engine is implicitly None
    
    # Feed it overlapping data (e.g., last 200 candles before crash + new candles)
    # This simulates the LIMIT 1500 warmup query fetching history
    df_part2 = df_full.iloc[400:800].copy()
    
    # Run the Pivot calculation. This SHOULD trigger the new Merge & Append logic
    pivot_signal.calculate(df_part2, state_v2)
    
    # ---------------------------------------------------------
    # PART 3: Assertions (Did the wipeout happen?)
    # ---------------------------------------------------------
    print("\nPhase 3: Verification")
    hydrated_pivots = state_v2.swing_points
    hydrated_chochs = [p for p in hydrated_pivots if p.get('is_choch')]
    
    print(f"Total Pivots found after Hydration: {len(hydrated_pivots)}")
    print(f"CHOCHs preserved after Hydration: {len(hydrated_chochs)}")
    
    if len(hydrated_pivots) < len(original_pivots):
        print("[FAIL] Wipeout detected! Total pivots decreased.")
        return
        
    if not hydrated_chochs:
        print("[FAIL] CHOCH metadata was wiped out during Pivot Merge!")
        return
        
    if hydrated_chochs[0]['t'] == choch_timestamp:
        print(f"[PASS] CHOCH metadata successfully mapped to correct historical timestamp {choch_timestamp}!")
    else:
        print("[FAIL] CHOCH timestamp mismatch!")
        return
        
    print("\n[SUCCESS] Integration Test Passed! Merge & Append architecture is solid.")

if __name__ == "__main__":
    run_test()
