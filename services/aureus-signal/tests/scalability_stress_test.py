import time
import pandas as pd
import numpy as np
import sys
import os

# Ensure we can import from engine
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState
from engine.signals.structure import StructureSignal

def run_scalability_test(num_obs=50, num_candles=1000):
    print(f"--- Scalability Stress Test: {num_obs} OBs, {num_candles} Candles ---")
    
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # 1. Create many active Bullish OBs spread across different price ranges
    # Most will NOT be touched by the current price
    for i in range(num_obs):
        ob = {
            "ob_type": "BULLISH",
            "top": 1000.0 + (i * 10),
            "bottom": 990.0 + (i * 10),
            "t_start": 100,
            "t_breakout": 150,
            "mitigated": False,
            "last_check_t": 200
        }
        state.add_ob(ob)
    
    # 2. Generate dummy data where price is far above the highest OB (no touches)
    # This tests the 'Fast-Path' and 'Vectorized Skip' efficiency
    data = []
    for i in range(num_candles):
        data.append({
            't': 1000 + i,
            'o': 50000, 'h': 50100, 'l': 49900, 'c': 50000
        })
    df = pd.DataFrame(data)
    
    # 3. Benchmark _verify_mitigations
    start_time = time.perf_counter()
    # Simulate calling it candle-by-candle (Real-time scenario)
    for i in range(1, num_candles + 1):
        # In real-time, df usually grows or is a rolling window
        current_df = df.iloc[:i]
        signal._verify_mitigations(current_df, state)
        
    end_time = time.perf_counter()
    duration = end_time - start_time
    avg_per_call = (duration / num_candles) * 1000 # ms
    
    print(f"Total Duration: {duration:.4f}s")
    print(f"Avg Latency per call: {avg_per_call:.4f}ms")
    
    return avg_per_call

if __name__ == "__main__":
    # Test with 1 OB (Baseline)
    latency_1 = run_scalability_test(num_obs=1, num_candles=500)
    
    # Test with 50 OBs (Stress)
    latency_50 = run_scalability_test(num_obs=50, num_candles=500)
    
    increase = ((latency_50 - latency_1) / latency_1) * 100
    print(f"\nLatency Increase (1 -> 50 OBs): {increase:.2f}%")
    
    if increase < 50: # Expecting well under 50% increase due to vectorized skip
        print("✅ SCALABILITY TARGET MET: Increase is within acceptable bounds.")
    else:
        print("❌ SCALABILITY ISSUE: Latency increased significantly with OB count.")
