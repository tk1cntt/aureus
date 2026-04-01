import json
import os
import sys
import unittest
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.state import SymbolState
from engine.strategies.template import TemplateStrategy
from engine.logging_common import get_logger

logger = get_logger(__name__)

# Control benchmark config (no context filters, low score threshold)
TREND_CONT_BEAR_CONFIG = {
    "name": "TREND_CONT_BEAR",
    "id": 1,
    "min_score_threshold": 0,
    "context_filters": [],
    "sequence": [
        {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30}
    ],
    "trade_execution": {
        "size": 1.0,
        "sl": {"type": "FIXED_PIPS", "value": 500},
        "tp": {"type": "RR_RATIO", "value": 2.0},
        "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
        "capital_risk_pct": 1.0,
        "early_exits": ["choch_up"]
    }
}


class TestChochTriggerMismatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data_path = "d:/Aureus/data-test.json"
        with open(data_path, "r", encoding="utf-8") as f:
            cls.raw_data = json.load(f)
        
        # Create a mock dataframe for the strategy evaluation
        df_records = []
        for d in cls.raw_data:
            df_records.append({"t": d["t"], "c": d["price"], "o": d["price"], "h": d["price"], "l": d["price"], "v": 1.0})
        cls.df = pd.DataFrame(df_records)

    def test_choch_down_triggers_strategy(self):
        """
        Replay the data-test.json sequentially through TemplateStrategy to verify
        that CHOCH events are captured and translated into intents.
        """
        state = SymbolState("USTEC")
        
        # Manually clear to simulate fresh engine:
        state.log_signal_normalize = []
        
        strategy = TemplateStrategy(TREND_CONT_BEAR_CONFIG)
        
        triggers = 0
        accepted_intents = []
        
        # Iterate over records as if they are arriving one by one
        for i in range(len(self.raw_data)):
            # Append new candle's event record
            state.log_signal_normalize.append(self.raw_data[i])
            
            # Evaluate the strategy
            # `df` passed to evaluate just needs to be up to current index
            current_df = self.df.iloc[:i+1]
            
            intent = strategy.evaluate(current_df, {}, state)
            
            if intent:
                triggers += 1
                accepted_intents.append(intent)

        # Print diagnostics
        print(f"\n--- DIAGNOSTICS ---")
        print(f"Total rows examined: {len(self.raw_data)}")
        choch_count = 0
        for d in self.raw_data:
            signals = d.get("signals", {})
            events = signals.get("events", [])
            for ev in events:
                if ev.get("tag") == "choch" or ev.get("value") == "choch_down" or ev.get("tag") == "choch_down":
                    choch_count += 1
        
        print(f"Total CHOCH raw events embedded in data-test.json: {choch_count}")
        print(f"Total strategy triggers (Intents): {triggers}")
        
        # If there are CHOCH events in the raw data, we EXPECT at least 1 trigger!
        self.assertGreater(choch_count, 0, "No CHOCH events found in data. Test is invalid.")
        self.assertGreater(triggers, 0, f"Mismatch bug! Found {choch_count} CHOCH events but 0 strategy triggers.")

if __name__ == "__main__":
    unittest.main()
