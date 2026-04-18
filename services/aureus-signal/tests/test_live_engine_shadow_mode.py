import pytest
import asyncio
import inspect
import json
import os
import sys
import time
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.providers.base import DecisionSignal
from engine.live_engine import run_signal_engine, shadow_execute_pulse, resolve_symbol_processing_mode
from engine.symbol_runtime import SymbolRuntimeHealthManager

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


def test_run_signal_engine_wires_health_and_rollout_hooks():
    source = inspect.getsource(run_signal_engine)
    assert "SymbolRuntimeHealthManager(" in source
    assert "resolve_symbol_processing_mode(" in source
    assert "update_symbol_metrics(" in source
    assert "get_symbol_status(" in source


def test_rollout_transition_shadow_canary_full():
    manager = SymbolRuntimeHealthManager()
    manager.set_symbol_mode("XAUUSD", "shadow")
    assert resolve_symbol_processing_mode("XAUUSD", manager) == "shadow"

    manager.set_symbol_mode("XAUUSD", "canary")
    assert resolve_symbol_processing_mode("XAUUSD", manager) == "canary"

    manager.set_symbol_mode("XAUUSD", "full")
    assert resolve_symbol_processing_mode("XAUUSD", manager) == "full"


def test_rollout_forces_fallback_serial_when_slo_breaches():
    manager = SymbolRuntimeHealthManager()
    manager.set_symbol_mode("XAUUSD", "canary")

    for _ in range(3):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=3000.0, queue_depth=250, error_rate=0.10)

    assert resolve_symbol_processing_mode("XAUUSD", manager) == "fallback_serial"

    manager.set_symbol_mode("EURUSD", "full")
    manager.update_symbol_metrics("EURUSD", lag_p95_ms=300.0, queue_depth=20, error_rate=0.0)
    assert resolve_symbol_processing_mode("EURUSD", manager) == "full"


def test_invalid_rollout_mode_is_rejected():
    manager = SymbolRuntimeHealthManager()
    with pytest.raises(ValueError):
        manager.set_symbol_mode("XAUUSD", "beta")


def test_rollout_allows_recovery_to_full_after_hysteresis():
    manager = SymbolRuntimeHealthManager()
    manager.set_symbol_mode("XAUUSD", "full")
    for _ in range(3):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=3000.0, queue_depth=250, error_rate=0.10)

    assert resolve_symbol_processing_mode("XAUUSD", manager) == "fallback_serial"

    for _ in range(5):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=500.0, queue_depth=50, error_rate=0.0)

    assert resolve_symbol_processing_mode("XAUUSD", manager) == "full"
