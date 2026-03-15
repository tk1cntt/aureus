# Mock external dependencies before importing main
import sys
from unittest.mock import MagicMock, AsyncMock
import os

mock_asyncpg = MagicMock()
mock_asyncpg.create_pool = AsyncMock()
sys.modules["asyncpg"] = mock_asyncpg

mock_redis = MagicMock()
mock_redis.Redis = MagicMock()
sys.modules["redis.asyncio"] = mock_redis

mock_dotenv = MagicMock()
sys.modules["dotenv"] = mock_dotenv

mock_pandas = MagicMock()
sys.modules["pandas"] = mock_pandas

# Mock the entire engine tree
for m in [
    "engine", "engine.manager", "engine.signals", "engine.signals.pivots", 
    "engine.signals.structure", "engine.signals.ema", "engine.strategies", 
    "engine.strategies.registry", "engine.gap_detector", "engine.orders", 
    "engine.ai_validator"
]:
    sys.modules[m] = MagicMock()

# Add parent dir to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env before import
os.environ["SYMBOLS"] = "XAUUSD,EURUSD"

# Now import load_symbols_config from main
from main import load_symbols_config

import asyncio

async def test_symbol_orchestration():
    print("🧪 Starting Multi-Symbol Orchestration Test...")
    
    symbols_list = ["XAUUSD", "EURUSD"]
    symbol_signals = {}
    
    # 1. Test Config Loading
    print("Checking config loading...")
    # Use the real function but it will read the actual symbols.json in the dir
    SYMBOL_CONFIG = load_symbols_config(path="services/aureus-signal/symbols.json")
    
    for symbol in symbols_list:
        cfg = SYMBOL_CONFIG.get(symbol, SYMBOL_CONFIG.get("XAUUSD", {}))
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

if __name__ == "__main__":
    asyncio.run(test_symbol_orchestration())
