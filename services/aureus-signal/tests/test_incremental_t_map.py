import pytest
import pandas as pd
import sys
import os

# Ensure we can import from engine
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from engine.state import SymbolState
from engine.signals.structure import StructureSignal

def test_t_map_persistence_and_incremental_update():
    """
    Test Case: StructureSignal.calculate should populate and incrementally update state_obj.t_map.
    Story 3.2 / Task 1
    """
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # Initial data
    data1 = [
        {'t': 1000, 'o': 100, 'h': 110, 'l': 90, 'c': 100},
        {'t': 1001, 'o': 100, 'h': 105, 'l': 85, 'c': 90},
        {'t': 1002, 'o': 90,  'h': 95,  'l': 70, 'c': 80},
    ]
    df1 = pd.DataFrame(data1)
    
    # First call: should populate t_map
    signal.calculate(df1, state)
    
    assert hasattr(state, 't_map'), "state should have t_map"
    assert len(state.t_map) == 3
    assert state.t_map[1000] == 0
    assert state.t_map[1002] == 2
    
    # Second call: add one new candle
    data2 = data1 + [{'t': 1003, 'o': 80, 'h': 115, 'l': 105, 'c': 110}]
    df2 = pd.DataFrame(data2)
    
    # We can mock/check if it was truly incremental if we really wanted to, 
    # but for now we verify correctness.
    signal.calculate(df2, state)
    
    assert len(state.t_map) == 4
    assert state.t_map[1003] == 3
    assert state.t_map[1000] == 0

def test_t_map_sliding_window_rebuild():
    """
    Test Case: StructureSignal.calculate should rebuild t_map if the window slides.
    Story 3.2 / Task 2
    """
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # Initial window [0, 1, 2]
    data1 = [
        {'t': 1000, 'o': 100, 'h': 110, 'l': 90, 'c': 100},
        {'t': 1001, 'o': 101, 'h': 111, 'l': 91, 'c': 101},
        {'t': 1002, 'o': 102, 'h': 112, 'l': 92, 'c': 102},
    ]
    df1 = pd.DataFrame(data1)
    signal.calculate(df1, state)
    assert state.t_map[1000] == 0
    
    # Sliding window: remove first candle, add new one [1, 2, 3]
    data2 = [
        {'t': 1001, 'o': 101, 'h': 111, 'l': 91, 'c': 101},
        {'t': 1002, 'o': 102, 'h': 112, 'l': 92, 'c': 102},
        {'t': 1003, 'o': 103, 'h': 113, 'l': 93, 'c': 103},
    ]
    df2 = pd.DataFrame(data2)
    signal.calculate(df2, state)
    
    assert len(state.t_map) == 3
    assert 1000 not in state.t_map
    assert state.t_map[1001] == 0
    assert state.t_map[1002] == 1
    assert state.t_map[1003] == 2

def test_t_map_performance_benchmark():
    """
    Performance Benchmark: Compare full rebuild vs incremental update.
    Story 3.2 / Task 3
    """
    import time
    state = SymbolState("BTCUSD")
    signal = StructureSignal()
    
    # Large dataset (2000 candles)
    n_candles = 2000
    data = [{'t': i, 'o': 100, 'h': 110, 'l': 90, 'c': 100} for i in range(n_candles)]
    df_large = pd.DataFrame(data)
    
    # 1. Measure Full Rebuild (First call)
    start_time = time.perf_counter()
    signal.calculate(df_large, state)
    full_rebuild_time = time.perf_counter() - start_time
    
    # 2. Measure Incremental Update (One new candle)
    data_inc = data + [{'t': n_candles, 'o': 100, 'h': 110, 'l': 90, 'c': 100}]
    df_inc = pd.DataFrame(data_inc)
    
    start_time = time.perf_counter()
    signal.calculate(df_inc, state)
    incremental_time = time.perf_counter() - start_time
    
    print(f"\n[Performance Benchmark]")
    print(f"Full Rebuild ({n_candles} candles): {full_rebuild_time*1000:.4f}ms")
    print(f"Incremental Update (1 new candle): {incremental_time*1000:.4f}ms")
    
    # Target: Incremental should be significantly faster than full rebuild for large N
    # We don't assert a specific ratio to avoid flaky tests in CI, but we log it.
    assert incremental_time < full_rebuild_time or full_rebuild_time < 0.001 # Small N edge case
