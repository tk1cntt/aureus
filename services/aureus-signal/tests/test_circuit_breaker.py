import pytest
import time
from unittest.mock import patch
from common.circuit_breaker import CircuitBreaker, CircuitBreakerState

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
