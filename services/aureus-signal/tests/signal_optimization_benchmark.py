import pandas as pd
import json
import os
import sys
import time
import hashlib
import numpy as np
import cProfile
import pstats
from io import StringIO
from datetime import datetime

# Ensure service path is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.manager import WindowManager
from engine.signals.structure import StructureSignal
from engine.signals.pivots import PivotSignal

GOLDEN_DATA_PATH = os.path.join(os.path.dirname(__file__), "benchmark_data_golden.json")
OUTPUT_REPORT_PATH = os.path.join(os.path.dirname(__file__), "benchmark_report.json")

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

def generate_golden_hash(results):
    """Generates a stable SHA256 hash from the results dictionary."""
    result_str = json.dumps(results, sort_keys=True, cls=NumpyEncoder)
    return hashlib.sha256(result_str.encode()).hexdigest()

def run_benchmark():
    if not os.path.exists(GOLDEN_DATA_PATH):
        print(f"Error: {GOLDEN_DATA_PATH} not found. Run fetch_benchmark_data.py first.")
        return

    with open(GOLDEN_DATA_PATH, "r") as f:
        all_data = json.load(f)

    print(f"Loaded data for {len(all_data)} symbols.")
    
    wm = WindowManager()
    # Configuration for StructureSignal - mimicking local production setup
    # Note: Using default params for StructureSignal
    structure_signal = StructureSignal()
    pivot_signal = PivotSignal(zigzag_engine="pro2")
    
    full_results = {}
    performance_metrics = {}
    
    global_start_t = time.time()
    total_candles_processed = 0

    for symbol, candles in all_data.items():
        candles = candles[:2000]
        print(f"\nBenchmarking {symbol} ({len(candles)} candles)...")
        symbol_start_t = time.time()
        
        # We collect hashes of swing points and OBs at each step or at the end
        # To keep it efficient, we only hash the FINAL state after all candles
        for i, candle in enumerate(candles):
            # Convert tick dict to the format expected by WindowManager
            # WindowManager.update expects a dict with 't', 'o', 'h', 'l', 'c', 'v' as strings
            candle_str = {k: str(v) for k, v in candle.items()}
            
            df, state = wm.update(symbol, candle_str)
            
            if df is not None and len(df) >= 5:
                pivot_signal.calculate(df, state, redis_client=None, symbol=symbol)
                structure_signal.calculate(df, state, redis_client=None, symbol=symbol)
            
            total_candles_processed += 1

        symbol_end_t = time.time()
        duration = symbol_end_t - symbol_start_t
        
        # Capture critical state for hashing
        state = wm.states.get(symbol)
        if not state:
            continue
        
        # Hashing:
        # 1. Swing points (HH/LL indices and times)
        # 2. Active OBs (Price, Time, Type)
        # 3. CHoCHs/BOSs 
        
        # Note: state.swing_points and state.obs are already lists of dicts
        swing_points = [
            {"t": p.get("t"), "type": p.get("type"), "idx": p.get("idx")} 
            for p in state.swing_points
        ]
        
        active_obs = [
            {"t_start": ob.get("t_start"), "ob_type": ob.get("ob_type"), "top": ob.get("top"), "bottom": ob.get("bottom")}
            for ob in state.obs if not ob.get("mitigated")
        ]
        
        full_results[symbol] = {
            "swing_points": swing_points,
            "active_obs": active_obs
        }
        
        performance_metrics[symbol] = {
            "duration_s": duration,
            "candles": len(candles),
            "latency_ms_per_candle": (duration * 1000) / len(candles) if len(candles) > 0 else 0
        }
        
        print(f"[{symbol}] Summary: {len(swing_points)} swing points, {len(active_obs)} active OBs.")

    global_end_t = time.time()
    total_duration = global_end_t - global_start_t
    
    golden_hash = generate_golden_hash(full_results)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "golden_hash": golden_hash,
        "total_duration_s": total_duration,
        "total_candles": total_candles_processed,
        "avg_latency_ms": (total_duration * 1000) / total_candles_processed if total_candles_processed > 0 else 0,
        "symbol_metrics": performance_metrics
    }
    
    with open(OUTPUT_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=4)
        
    print("\n" + "="*40)
    print(f"BENCHMARK COMPLETE")
    print(f"Golden Hash: {golden_hash}")
    print(f"Avg Latency: {report['avg_latency_ms']:.4f} ms/candle")
    print(f"Total Time:  {total_duration:.2f} s")
    print("="*40)

if __name__ == "__main__":
    # Use cProfile to find bottlenecks
    # pr = cProfile.Profile()
    # pr.enable()
    
    run_benchmark()
    
    # pr.disable()
    # s = StringIO()
    # ps = pstats.Stats(pr, stream=s).sort_stats('tottime')
    # ps.print_stats(30) 
    # print(s.getvalue())
    
    # bottleneck_content = s.getvalue()
    # bottleneck_path = os.path.join(os.path.dirname(__file__), "bottlenecks.txt")
    # with open(bottleneck_path, "w") as f:
    #     f.write(bottleneck_content)
    
    # print(f"\nTop 50 Bottlenecks saved to {bottleneck_path}")
