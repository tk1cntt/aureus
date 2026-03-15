"""
Unit test for recalculate_all_signals with Checkpoint logic — Story 9.8
"""
import sys
import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Directly import the function we are testing
from engine.live_engine import recalculate_all_signals

class MockDBPool:
    def __init__(self, max_snapshot_time, query_results=None):
        self.max_snapshot_time = max_snapshot_time
        self.query_results = query_results or {}
        self.executed_queries = []
        
    async def fetchval(self, query, *args):
        self.executed_queries.append({"query": query, "args": args})
        if "MAX(time)" in query:
            return self.max_snapshot_time
        return None
        
    async def fetch(self, query, *args):
        self.executed_queries.append({"query": query, "args": args})
        if "LIMIT 200" in query:
            return self.query_results.get("warmup", [])
        if "time >" in query:
            return self.query_results.get("new", [])
        return []

class MockRedis:
    def __init__(self, checkpoint_ts=None):
        self.checkpoint_ts = checkpoint_ts
        self.set_calls = {}
        
    async def get(self, key):
        if key == "aureus:checkpoint:XAUUSD" and self.checkpoint_ts:
            return json.dumps({"last_processed_time": self.checkpoint_ts, "updated_at": 123456789})
        return None
        
    async def set(self, key, value):
        self.set_calls[key] = value

class MockWindowManager:
    def __init__(self):
        self.states = {"XAUUSD": MagicMock()}
        self.states["XAUUSD"].to_dict.return_value = {"state": "dummy"}
    def reset(self, symbol):
        pass
    def update(self, symbol, data):
        return (MagicMock(empty=False), self.states[symbol])
    def get_df(self, symbol):
        df_mock = MagicMock()
        return df_mock

class MockStrategyRegistry:
    def evaluate_all(self, df, signals, state):
        pass

class MockLock:
    async def __aenter__(self):
        pass
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

# Need a robust mock for Row to simulate asyncpg Record
class MockRow:
    def __init__(self, dt):
        # Force the datetime to be UTC aware, so .timestamp() behaves identically on Windows and Linux
        self.dt = dt.replace(tzinfo=timezone.utc)
    def __getitem__(self, item):
        if item == 'time':
            return self.dt
        return 0

async def main():
    print("--- Running Story 9.8 Unit Tests ---")
    
    symbol = "XAUUSD"
    base_time_utc = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    base_time_naive = base_time_utc.replace(tzinfo=None)
    newer_ts = int(base_time_utc.timestamp()) + 3600 # 1 hour later
    
    wm = MockWindowManager()
    reg = MockStrategyRegistry()
    lock = MockLock()
    signals = {}
    
    # Generate some fake database rows
    row1 = MockRow(base_time_naive)
    row2 = MockRow(datetime.fromtimestamp(newer_ts, tz=timezone.utc).replace(tzinfo=None))
    row3_ts = newer_ts + 60
    row3 = MockRow(datetime.fromtimestamp(row3_ts, tz=timezone.utc).replace(tzinfo=None))
    
    # ---------------------------------------------------------
    # Scenario 1: Checkpoint exists and is NEWER than snapshot
    # Expectation: new_rows query uses checkpoint time. Checkpoint is updated at the end to row3_ts.
    # ---------------------------------------------------------
    db = MockDBPool(base_time_naive, {"new": [row2, row3]})
    r = MockRedis(newer_ts)
    
    await recalculate_all_signals(symbol, db, r, wm, signals, reg, lock)
    
    # Verify the delta query arg was the new_ts
    delta_query_args = [q["args"] for q in db.executed_queries if "time > $2" in q["query"]][0]
    expected_delta_time = datetime.fromtimestamp(newer_ts, tz=timezone.utc).replace(tzinfo=None)
    assert delta_query_args[1] == expected_delta_time, f"Expected {expected_delta_time}, got {delta_query_args[1]}"
    
    # Verify checkpoint was updated to row3's timestamp at the end
    cp_key = f"aureus:checkpoint:{symbol}"
    assert cp_key in r.set_calls
    cp_data = json.loads(r.set_calls[cp_key])
    actual_ts = cp_data["last_processed_time"]
    print(f"DEBUG: expected_ts={row3_ts}, actual_ts={actual_ts}")
    assert actual_ts == row3_ts
    
    print("[PASS] Scenario 1: Recalculate correctly used Checkpoint for delta and updated it afterwards.")
    
    # ---------------------------------------------------------
    # Scenario 2: Checkpoint is missing (None)
    # Expectation: Fallback to max snapshot time.
    # ---------------------------------------------------------
    db2 = MockDBPool(base_time_naive, {"new": [row2, row3]})
    r2 = MockRedis(None)
    
    await recalculate_all_signals(symbol, db2, r2, wm, signals, reg, lock)
    
    delta_query_args2 = [q["args"] for q in db2.executed_queries if "time > $2" in q["query"]][0]
    assert delta_query_args2[1] == base_time_naive
    
    print("[PASS] Scenario 2: Checkpoint missing -> Recalculation fell back to Snapshot time.")

    print("\n[SUCCESS] All ACs passed for recalculate_all_signals Checkpoint Update!")

if __name__ == "__main__":
    asyncio.run(main())
