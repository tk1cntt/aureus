import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from main import process_message


class MockRedis:
    def __init__(self):
        self.hashes = {}
        self.streams = {}

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def hset(self, key, mapping):
        self.hashes[key] = {**self.hashes.get(key, {}), **mapping}

    async def xadd(self, key, mapping, maxlen=None, approximate=None):
        self.streams.setdefault(key, []).append(mapping)
        return f"{len(self.streams[key])}-0"


@pytest.mark.asyncio
async def test_gateway_rejects_signal_without_contract_fields():
    r = MockRedis()
    data = {"type": "SIGNAL", "symbol": "XAUUSD", "t": 1710000000}

    ok = await process_message(r, data, source="TCP")

    assert ok is False


@pytest.mark.asyncio
async def test_gateway_accepts_valid_signal_contract_payload():
    r = MockRedis()
    data = {
        "type": "SIGNAL",
        "signal_id": "XAUUSD-M1-1710000000-choch_up",
        "decision_id": "XAUUSD-1710000000-decision",
        "run_id": "live",
        "signal_seq": 1,
        "symbol": "XAUUSD",
        "t": 1710000000,
        "tf": "M1",
        "strategy_id": "smc_trend_scalping",
        "signal_type": "choch_up",
        "confidence": 0.82,
        "metadata": {"source": "structure_processor"},
    }

    ok = await process_message(r, data, source="TCP")

    assert ok is True
    assert "aureus:stream:XAUUSD:signal" in r.streams
    assert len(r.streams["aureus:stream:XAUUSD:signal"]) == 1
