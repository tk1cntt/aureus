import pytest
import time
from unittest.mock import patch
from common.circuit_breaker import CircuitBreaker, CircuitBreakerState
from engine.symbol_runtime import SymbolRuntimeHealthManager

def test_circuit_breaker_initial_state():
    cb = CircuitBreaker(error_threshold=2, timeout_seconds=10)
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute() is True

def test_circuit_breaker_trips_to_open():
    cb = CircuitBreaker(error_threshold=2, timeout_seconds=10)
    
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute() is True
    
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.can_execute() is False

@patch("common.circuit_breaker.time.monotonic")
def test_circuit_breaker_half_open_recovery(mock_time):
    mock_time.return_value = 100.0
    
    cb = CircuitBreaker(error_threshold=2, timeout_seconds=10)
    cb.record_failure() 
    cb.record_failure()
    
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.can_execute() is False
    
    mock_time.return_value = 109.9
    assert cb.can_execute() is False
    
    mock_time.return_value = 110.1
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN
    
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0

@patch("common.circuit_breaker.time.monotonic")
def test_circuit_breaker_half_open_failure(mock_time):
    mock_time.return_value = 100.0
    cb = CircuitBreaker(error_threshold=1, timeout_seconds=10)
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN

    mock_time.return_value = 111.0
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.can_execute() is False


def test_per_symbol_breaker_isolation_does_not_trip_other_symbols():
    manager = SymbolRuntimeHealthManager()
    manager.record_symbol_failure("XAUUSD")
    manager.record_symbol_failure("XAUUSD")
    manager.record_symbol_failure("XAUUSD")
    manager.record_symbol_failure("XAUUSD")
    manager.record_symbol_failure("XAUUSD")

    xau = manager.get_symbol_status("XAUUSD")
    eur = manager.get_symbol_status("EURUSD")

    assert xau["breaker_open"] is True
    assert xau["allow_parallel"] is False
    assert eur["breaker_open"] is False
    assert eur["allow_parallel"] is True


def test_per_symbol_backlog_threshold_alerts_only_when_crossing_limit():
    manager = SymbolRuntimeHealthManager(queue_depth_threshold=200)
    assert manager.update_symbol_metrics("XAUUSD", lag_p95_ms=100.0, queue_depth=199, error_rate=0.0) is None

    reason = manager.update_symbol_metrics("XAUUSD", lag_p95_ms=100.0, queue_depth=201, error_rate=0.0)
    assert reason == "BACKLOG_THRESHOLD_BREACH"

    status = manager.get_symbol_status("XAUUSD")
    assert status["queue_depth"] == 201
    assert status["allow_parallel"] is True


def test_symbol_enters_fallback_after_three_consecutive_slo_breaches():
    manager = SymbolRuntimeHealthManager()
    for _ in range(3):
        reason = manager.update_symbol_metrics("XAUUSD", lag_p95_ms=2500.0, queue_depth=10, error_rate=0.01)

    assert reason == "SLO_BREACH_FALLBACK_SERIAL"
    status = manager.get_symbol_status("XAUUSD")
    assert status["mode"] == "fallback_serial"
    assert status["allow_parallel"] is False


def test_symbol_exits_fallback_after_five_consecutive_healthy_minutes():
    manager = SymbolRuntimeHealthManager()
    for _ in range(3):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=2500.0, queue_depth=250, error_rate=0.10)

    status = manager.get_symbol_status("XAUUSD")
    assert status["mode"] == "fallback_serial"

    reason = None
    for _ in range(5):
        reason = manager.update_symbol_metrics("XAUUSD", lag_p95_ms=900.0, queue_depth=90, error_rate=0.02)

    assert reason == "SLO_RECOVERED_PARALLEL"
    status = manager.get_symbol_status("XAUUSD")
    assert status["mode"] == "full"
    assert status["allow_parallel"] is True
