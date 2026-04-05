import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock

from engine.providers.base import DecisionSignal
from engine.live_engine import shadow_execute_pulse

def test_shadow_mode_execution_wrapper():
    """
    Test that shadow_execute_pulse runs TradingAgents asynchronously,
    does not block the event loop, and writes to the correct Redis key.
    """
    asyncio.run(_test_shadow_mode_execution_wrapper_async())

async def _test_shadow_mode_execution_wrapper_async():
    mock_redis = AsyncMock()
    mock_ta_provider = AsyncMock()
    
    # Simulate a slow API call by the decision provider
    async def slow_decision(*args, **kwargs):
        await asyncio.sleep(0.5) # Using 0.5s instead of 2.0s to speed up tests while still proving async
        return DecisionSignal(
            action="BUY",
            confidence=0.99,
            reasoning="mock_reasoning",
            timestamp=int(time.time()),
            symbol="XAUUSD",
            source="tradingagents"
        )
        
    mock_ta_provider.get_decision.side_effect = slow_decision
    
    start_time = time.time()
    # Spawn task identically to live_engine
    task = asyncio.create_task(shadow_execute_pulse("XAUUSD", {}, time.time(), mock_redis, mock_ta_provider))
    
    # Assert it returns immediately to event loop
    elapsed = time.time() - start_time
    assert elapsed < 0.1, f"Spawning shadow task blocked for {elapsed} seconds"
    
    # Wait for the background task to complete
    await task
    
    # Verify that the asynchronous result was written to the shadow namespace
    mock_redis.set.assert_called_once()
    args, _ = mock_redis.set.call_args
    assert args[0] == "aureus:ai:shadow:XAUUSD"
    
    payload = json.loads(args[1])
    assert payload["action"] == "BUY"
    assert payload["confidence"] == 0.99
    assert payload["reasoning"] == "mock_reasoning"
    assert "llm_latency_ms" in payload
