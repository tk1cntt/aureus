import json
import pandas as pd
import os
import sys

# Add service path to sys.path
signal_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if signal_root not in sys.path:
    sys.path.append(signal_root)
from engine.common.zigzag_pro2 import ZigZagPro

def generate():
    input_file = 'services/aureus-signal/tests/zigzag_ground_truth.json'
    output_file = 'services/aureus-signal/tests/zigzag_ground_truth_filtered.json'
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    candles = data['candles']
    df = pd.DataFrame(candles)
    
    # Use default params from test suite
    params = {
        "ext_period": 3,
        "min_amplitude": 10,
        "min_motion": 0,
        "point": 1.0,
        "digits": 0
    }
    
    engine = ZigZagPro(**params)
    results = engine.update(df, incremental=False)
    
    # Prepare ground truth format
    # The original file has "results" which is a list of objects per index
    # We will recreate that with the new values
    new_results = []
    for i in range(len(candles)):
        new_results.append({
            "up": results["up"][i],
            "dn": results["dn"][i],
            "type": int(results["type"][i])
        })
        
    output_data = {
        "params": params,
        "candles": candles,
        "results": new_results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
        
    print(f"Generated {output_file}")

if __name__ == '__main__':
    generate()
