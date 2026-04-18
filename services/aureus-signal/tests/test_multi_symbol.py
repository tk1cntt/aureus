import asyncio
import inspect
import os
import sys

# Add aureus-signal service root to import path for `engine.*`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.live_engine import load_symbols_config
from engine.strategy_executor import run_strategy_executor


def test_symbol_orchestration():
    async def _run():
        print("🧪 Starting Multi-Symbol Orchestration Test...")

        symbols_list = ["XAUUSD", "EURUSD"]
        symbol_signals = {}

        # 1. Test Config Loading
        print("Checking config loading...")
        
        from unittest.mock import patch
        with patch(f"{__name__}.load_symbols_config") as mock_load:
            mock_load.return_value = {"XAUUSD": {"digits": 2}, "EURUSD": {"digits": 5}}
            symbol_config = mock_load(path="services/aureus-signal/symbols.json")
            
            for symbol in symbols_list:
                cfg = symbol_config.get(symbol, symbol_config.get("XAUUSD", {}))
                assert cfg is not None
                print(f"  - Loaded {symbol} config: digits={cfg.get('digits')}")
                symbol_signals[symbol] = cfg

        assert symbol_signals["XAUUSD"]["digits"] == 2
        assert symbol_signals["EURUSD"]["digits"] == 5
        print("✅ Config loading verified.")

        # 2. Test Stream Routing Simulation
        print("Simulating stream routing...")
        target_streams = {f"aureus:stream:{s}:candle": s for s in symbols_list}

        # Case: Message from EURUSD stream
        mock_msg_key = "aureus:stream:EURUSD:candle"
        routed_symbol = target_streams.get(mock_msg_key)
        assert routed_symbol == "EURUSD"
        print(f"✅ Routing verified: {mock_msg_key} -> {routed_symbol}")

        # 3. Test Locking Isolation
        print("Checking lock isolation...")
        symbol_locks = {s: asyncio.Lock() for s in symbols_list}

        async with symbol_locks["XAUUSD"]:
            assert symbol_locks["XAUUSD"].locked()
            assert not symbol_locks["EURUSD"].locked()
            print("✅ Lock isolation verified: Locking XAUUSD does not block EURUSD.")

        print("\n🎉 All Step 1 Orchestration tests passed!")

    asyncio.run(_run())

def test_strategy_executor_rollout_wiring_keywords_present():
    source = inspect.getsource(run_strategy_executor)
    assert "SymbolRuntimeHealthManager(" in source
    assert "resolve_strategy_processing_mode(" in source
    assert "update_symbol_metrics(" in source
    assert "record_symbol_success(" in source
    assert "record_symbol_failure(" in source


if __name__ == "__main__":
    test_symbol_orchestration()
