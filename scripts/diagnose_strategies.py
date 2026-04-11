"""
Diagnostic script to investigate strategy rejection.
Run this from the services/aureus-signal directory to test
why all 6 seed strategies are being rejected.
"""
import asyncio
import json
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Load seed strategies and test with mock data."""
    from engine.strategies.seed_strategies import seed_system_strategies
    from engine.strategies.template import TemplateStrategy
    from engine.state import SymbolState
    from engine.strategies.registry import StrategyRegistry
    import pandas as pd
    
    print("=" * 80)
    print("STRATEGY DIAGNOSTIC TOOL")
    print("=" * 80)
    
    # Create a mock DB pool object
    class MockDB:
        async def fetch(self, query, *args):
            # Return 6 seed strategy IDs
            return [{"id": i+1, "name": f"Strategy_{i+1}", "config": "{}", "min_score": 10, "magic_number": (i+1)*1000} for i in range(6)]
    
    mock_db = MockDB()
    
    # Now test with seed_system_strategies directly
    # Let's manually inspect the 6 seed strategies
    from engine.strategies.seed_strategies import SEED_STRATEGIES
    
    print(f"\nTotal seed strategies defined: {len(SEED_STRATEGIES)}")
    
    for i, config in enumerate(SEED_STRATEGIES):
        print(f"\n--- Strategy {i+1}: {config.get('name', 'UNKNOWN')} ---")
        print(f"  direction: {config.get('trade_execution', {}).get('direction', 'NOT SET')}")
        print(f"  context_filters: {config.get('context_filters', 'NOT SET')}")
        print(f"  min_score_threshold: {config.get('min_score_threshold', 'NOT SET')}")
        sequence = config.get('sequence', [])
        print(f"  sequence length: {len(sequence)}")
        for step in sequence:
            print(f"    - tag: {step.get('tag', 'MISSING')}, weight: {step.get('weight', 0)}, required: {step.get('required', False)}")
    
    print("\n\n" + "=" * 80)
    print("TESTING STRATEGY EVALUATION WITH MOCK DATA")
    print("=" * 80)
    
    # Create a proper mock state with log_signal_normalize that mimics real data
    symbol = "XAUUSD"
    state = SymbolState(symbol)
    
    # Mock log_signal_normalize with typical signal events
    # Format: [{signals: {events: [{tag: "choch_up", ...}]}}]
    state.log_signal_normalize = [
        {
            "signals": {
                "events": [{"tag": "choch_up", "t": 1000}]
            },
            "t": 1000
        }
    ]
    
    # Create mock DataFrame
    ts_unix = 1775720460
    mini_df = pd.DataFrame([{"t": ts_unix, "c": 3000.0}])
    
    # Test each strategy
    for i, config in enumerate(SEED_STRATEGIES):
        print(f"\n--- Testing {config.get('name', 'UNKNOWN')} ---")
        try:
            strat = TemplateStrategy(config)
            print(f"  ✓ Loaded successfully")
            print(f"  spec_compatibility: {getattr(strat, 'spec_compatibility', 'NOT SET')}")
            print(f"  direction: {strat.direction}")
            
            context = {"df": mini_df, "signals": {}, "state": state, "bar_ts": ts_unix, "symbol": symbol}
            intent = strat.on_bar_close(context)
            
            if intent is None:
                print(f"  ✗ No intent (returned None)")
                continue
                
            if intent.get("is_actionable"):
                print(f"  ✓ ACTIONABLE - WOULD TRIGGER!")
                print(f"    reason_code: {intent.get('reason_code')}")
            else:
                print(f"  ✗ NOT actionable")
                print(f"    reason_code: {intent.get('reason_code', 'UNKNOWN')}")
                print(f"    intent_id: {intent.get('intent_id')}")
                
                # Show sequence diagnostics if available
                if "sequence_diagnostics" in intent:
                    diag = intent["sequence_diagnostics"]
                    print(f"    matched_steps: {diag.get('matched_steps', 0)}/{diag.get('total_steps', 0)}")
                    print(f"    current_step: {diag.get('current_step_index', 0)}")
                    print(f"    mismatch_reason: {diag.get('mismatch_reason', 'N/A')}")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
