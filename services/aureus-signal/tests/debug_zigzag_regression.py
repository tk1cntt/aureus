import pandas as pd
import json
import os
import sys

# Add service path to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.common.zigzag_pro2 import ZigZagPro

def debug_regression():
    truth_path = "services/aureus-signal/tests/zigzag_ground_truth.json"
    with open(truth_path, "r") as f:
        truth = json.load(f)
        
    df = pd.DataFrame(truth['candles'])
    params = truth['params']
    expected = truth['expected']
    
    engine = ZigZagPro(**params)
    ext_period = int(params['ext_period'])
    
    # Initialize
    current_df = df.iloc[:ext_period+1]
    engine.update(current_df, incremental=True)
    
    print(f"--- Warmup done (index 0 to {ext_period}) ---")
    
    # Feed one by one and check
    for i in range(ext_period+1, 20):  # Check first 20 candles
        current_df = df.iloc[:i+1]
        buffers = engine.update(current_df, incremental=True)
        
        print(f"\n[Index {i}] Candle Time: {df.iloc[i]['t']}")
        for key in ['up', 'dn', 'type']:
            actual_val = buffers[key][i]
            expected_val = expected[key][i]
            if actual_val != expected_val:
                print(f"  !!! ERROR in {key}: Actual={actual_val}, Expected={expected_val}")
                # Also check historical buffer state
                if len(engine.up) > 10:
                    print(f"  Buffer state at index 10: up={engine.up[10]}, dn={engine.dn[10]}, type={engine.type_buffer[10]}")
                print(f"  Pointers: last_up_idx={engine.last_up_idx}, last_dn_idx={engine.last_dn_idx}")

if __name__ == '__main__':
    debug_regression()
