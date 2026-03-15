"""
Unit tests for Checkpoint Marker logic — Story 9.4

Tests:
  - AC1: Writes aureus:checkpoint:{symbol} with last_processed_time
  - AC2: Lightweight: Payload <= 100 bytes
  - AC4: No Crash: Redis write failure caught and ignored
"""
import asyncio
import json
import time

# --- Helper functions that replicate the inline logic from live_engine.py ---

async def simulate_checkpoint_write(r, symbol: str, ts_unix: float):
    """Simulates the checkpoint write block in live_engine.py:452"""
    try:
        checkpoint_payload = json.dumps({
            "last_processed_time": int(ts_unix),
            "updated_at": int(time.time())
        })
        await r.set(f"aureus:checkpoint:{symbol}", checkpoint_payload)
        return checkpoint_payload
    except Exception as e:
        return None

# --- Mock Objects ---

class FakeRedis:
    def __init__(self):
        self.data = {}
        self.should_fail = False

    async def set(self, key, value):
        if self.should_fail:
            raise ConnectionError("Redis is down")
        self.data[key] = value


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# --- Tests ---

def test_checkpoint_payload_format():
    """AC1: Format is correct with last_processed_time and updated_at."""
    r = FakeRedis()
    ts_unix = 1709300000.0
    symbol = "XAUUSD"
    
    payload = run(simulate_checkpoint_write(r, symbol, ts_unix))
    
    assert payload is not None
    assert f"aureus:checkpoint:{symbol}" in r.data
    
    data = json.loads(r.data[f"aureus:checkpoint:{symbol}"])
    assert "last_processed_time" in data
    assert "updated_at" in data
    assert data["last_processed_time"] == int(ts_unix)


def test_checkpoint_payload_size():
    """AC2: Payload is lightweight (<= 100 bytes)."""
    r = FakeRedis()
    ts_unix = 1709300000.0
    
    payload = run(simulate_checkpoint_write(r, "XAUUSD", ts_unix))
    
    size_bytes = len(payload.encode('utf-8'))
    assert size_bytes <= 100, f"Payload too large: {size_bytes} bytes. Content: {payload}"
    print(f"Payload size is {size_bytes} bytes — very lightweight.")


def test_checkpoint_no_crash_on_error():
    """AC4: Redis error is caught and doesn't crash."""
    r = FakeRedis()
    r.should_fail = True
    ts_unix = 1709300000.0
    
    # This should not raise an exception
    payload = run(simulate_checkpoint_write(r, "XAUUSD", ts_unix))
    
    assert payload is None, "Expected None because exception was caught"
    assert len(r.data) == 0


if __name__ == "__main__":
    tests = [
        test_checkpoint_payload_format,
        test_checkpoint_payload_size,
        test_checkpoint_no_crash_on_error
    ]
    
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
            
    print(f"\n--- Results: {passed} PASSED, {failed} FAILED ---")
