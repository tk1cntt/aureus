import sys
import os
import time
import pandas as pd
import tracemalloc

# Ensure the engine module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.common import OutsideBarAnalyzer, OrderFormation

def test_cache_thrashing_integration():
    print("🧪 Starting Cache Thrashing Integration Test...")
    tracemalloc.start()
    
    # Simulate an analyzer with a typical small max size
    analyzer = OutsideBarAnalyzer(cache_max_size=500)
    
    # Generate 2000 mock candles (far exceeding the 500 limit)
    print("Generating 2000 mock candles...")
    candles = []
    base_time = 1600000000
    for i in range(2000):
        candle = pd.Series({
            't': base_time + (i * 300), 
            'o': 1.0, 
            'h': 2.0, 
            'l': 0.5, 
            'c': 1.5
        })
        candles.append(candle)
        
    dummy_sub_candles = {"M1": pd.DataFrame()}
    
    # Measure execution time and memory delta
    start_mem, _ = tracemalloc.get_traced_memory()
    start_time = time.time()
    
    for c in candles:
        # Pass use_sub_tf=False to bypass small_tf_logic requirements for simple integration speed test
        # In a real thrashing scenario, small_tf_logic is executed, but here we just test memory cache behavior
        analyzer.get_order_formation(c, timeframe="M5", use_sub_tf=False)
        
    end_time = time.time()
    end_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    duration = end_time - start_time
    mem_used_kb = (peak_mem - start_mem) / 1024
    
    print(f"Processed 2000 items in {duration:.4f} seconds")
    print(f"Peak memory increase: {mem_used_kb:.2f} KB")
    
    # Validation 1: Size is still bounded
    assert len(analyzer._cache) == 500, f"Cache size should be bounded at exactly 500, got {len(analyzer._cache)}"
    print("✅ Cache size successfully bounded at 500 despite 2000 insertions.")
    
    # Validation 2: Memory is not exploding
    # An OrderedDict with 500 small tuples/enums should be under a few hundred KB,
    # but creating 2000 Pandas Series takes ~1.5MB in python.
    # We verify the memory doesn't continuously leak past the expected object overhead.
    assert mem_used_kb < 2500, f"Memory footprint too high: {mem_used_kb:.2f} KB (Possible leak)"
    print("✅ Memory footprint verified under Python overhead limit.")
    
    # Validation 3: Basic Performance is still O(1)
    # 2000 simple logic gets should be extremely fast (under 0.1s in pure python)
    assert duration < 0.5, f"Performance degraded: {duration:.4f}s (thrashing penalty too high)"
    print("✅ O(1) insertion/eviction performance verified.")
    
    print("\n🎉 Cache Thrashing Integration Test Passed!")

if __name__ == "__main__":
    test_cache_thrashing_integration()
