import sys
import os
import pandas as pd
from unittest.mock import patch, MagicMock

# Ensure the engine module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import OrderedDict
from engine.common import OutsideBarAnalyzer, OrderFormation

def test_outside_bar_cache_public_api():
    print("🧪 Starting OutsideBarAnalyzer Public API Cache Test...")
    analyzer = OutsideBarAnalyzer()
    
    # 1. Initialization Test
    print("Phase 1: Testing Initialization & Max Size...")
    assert isinstance(analyzer._cache, OrderedDict), "Cache must be an OrderedDict"
    assert analyzer._cache_max_size == 500, "Cache max size must be 500"
    print("✅ Initialization verified.")

    # 2. Public API Cache HIT Test
    print("\nPhase 2: Testing Public API Cache HIT (Encapsulation)...")
    # Setup dummy candle
    dummy_candle = pd.Series({'t': 1600000000, 'o': 1.0, 'h': 2.0, 'l': 0.5, 'c': 1.5})
    dummy_sub_candles = {"M1": pd.DataFrame()}
    
    # Mock small_tf_logic so we can count how many times it gets called
    with patch.object(analyzer, 'small_tf_logic', return_value=OrderFormation.OFBHighLow) as mock_small_tf:
        # First call: Should miss cache and call small_tf_logic
        res1 = analyzer.get_order_formation(
            dummy_candle, timeframe="M5", lookback_tf="M1", 
            use_sub_tf=True, sub_candles_by_tf=dummy_sub_candles
        )
        assert res1 == OrderFormation.OFBHighLow
        assert mock_small_tf.call_count == 1, "small_tf_logic should be called on first execution"
        
        # Second call with SAME exactly parameters: Should HIT cache
        res2 = analyzer.get_order_formation(
            dummy_candle, timeframe="M5", lookback_tf="M1", 
            use_sub_tf=True, sub_candles_by_tf=dummy_sub_candles
        )
        assert res2 == OrderFormation.OFBHighLow
        assert mock_small_tf.call_count == 1, "small_tf_logic should NOT be called again (Cache HIT failed)"
        
    print("✅ Public API Cache HIT verified.")

    # 3. Instance Isolation Test
    print("\nPhase 3: Testing Instance Isolation (Multi-Symbol safety)...")
    analyzer1 = OutsideBarAnalyzer()
    analyzer2 = OutsideBarAnalyzer()
    
    # Put item in analyzer1
    analyzer1.get_order_formation(
        dummy_candle, timeframe="M5", lookback_tf="M1", 
        use_sub_tf=True, sub_candles_by_tf=dummy_sub_candles
    )
    
    # Verify analyzer1 has 1 item, analyzer2 has 0
    assert len(analyzer1._cache) == 1, "Analyzer 1 should have 1 cached item"
    assert len(analyzer2._cache) == 0, "Analyzer 2 cache should be empty (Isolation failed)"
    print("✅ Instance Isolation verified.")
    
    # 4. LRU Eviction Test through Public API
    print("\nPhase 4: Testing LRU Eviction & Thrashing Limit...")
    analyzer_lru = OutsideBarAnalyzer()
    analyzer_lru._cache_max_size = 3 # Small size for testing
    
    # Insert 3 different candles
    c1 = pd.Series({'t': 1000, 'o': 1.0, 'h': 2.0, 'l': 0.5, 'c': 1.5})
    c2 = pd.Series({'t': 2000, 'o': 1.0, 'h': 2.0, 'l': 0.5, 'c': 1.5})
    c3 = pd.Series({'t': 3000, 'o': 1.0, 'h': 2.0, 'l': 0.5, 'c': 1.5})
    
    with patch.object(analyzer_lru, 'small_tf_logic', return_value=OrderFormation.OFBHighLow):
        analyzer_lru.get_order_formation(c1, use_sub_tf=True)
        analyzer_lru.get_order_formation(c2, use_sub_tf=True)
        analyzer_lru.get_order_formation(c3, use_sub_tf=True)
        
        assert len(analyzer_lru._cache) == 3, "Cache should be full"
        
        # Access c1 again to make it MOST recently used
        analyzer_lru.get_order_formation(c1, use_sub_tf=True)
        
        # Insert a 4th candle, which should evict the LEAST recently used (c2)
        c4 = pd.Series({'t': 4000, 'o': 1.0, 'h': 2.0, 'l': 0.5, 'c': 1.5})
        analyzer_lru.get_order_formation(c4, use_sub_tf=True)
        
        assert len(analyzer_lru._cache) == 3, "Cache should not exceed max limit"
        
        # Check keys to see what was evicted
        cached_keys = [k[0] for k in analyzer_lru._cache.keys()] # Extract just the timestamp 't'
        assert 1000 in cached_keys, "c1 should still be in cache (LRU updated)"
        assert 3000 in cached_keys, "c3 should still be in cache"
        assert 4000 in cached_keys, "c4 should be in cache"
        assert 2000 not in cached_keys, "c2 should have been evicted (Least Recently Used)"
        
    print("✅ LRU Eviction verified.")

    print("\n🎉 All OutsideBarAnalyzer Cache Code Review fixes validated!")

if __name__ == "__main__":
    test_outside_bar_cache_public_api()
