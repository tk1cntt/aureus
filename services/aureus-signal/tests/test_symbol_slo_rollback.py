import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.symbol_runtime import SymbolRuntimeHealthManager


def test_slo_rollback_is_scoped_to_violating_symbol_only():
    manager = SymbolRuntimeHealthManager()

    for _ in range(3):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=2100.0, queue_depth=210, error_rate=0.01)
        manager.update_symbol_metrics("EURUSD", lag_p95_ms=500.0, queue_depth=30, error_rate=0.0)

    xau = manager.get_symbol_status("XAUUSD")
    eur = manager.get_symbol_status("EURUSD")

    assert xau["mode"] == "fallback_serial"
    assert xau["allow_parallel"] is False
    assert eur["mode"] == "full"
    assert eur["allow_parallel"] is True


def test_slo_fallback_reason_reports_breach_dimension_and_duration():
    manager = SymbolRuntimeHealthManager()

    reason = None
    for _ in range(3):
        reason = manager.update_symbol_metrics("XAUUSD", lag_p95_ms=500.0, queue_depth=50, error_rate=0.08)

    assert reason == "SLO_BREACH_FALLBACK_SERIAL"

    status = manager.get_symbol_status("XAUUSD")
    assert status["last_transition_reason"] == "error_rate"
    assert status["consecutive_breach_minutes"] == 3


def test_slo_hysteresis_requires_consecutive_healthy_minutes_for_recovery():
    manager = SymbolRuntimeHealthManager()

    for _ in range(3):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=2500.0, queue_depth=250, error_rate=0.10)

    for _ in range(4):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=500.0, queue_depth=50, error_rate=0.0)

    status = manager.get_symbol_status("XAUUSD")
    assert status["mode"] == "fallback_serial"

    reason = manager.update_symbol_metrics("XAUUSD", lag_p95_ms=500.0, queue_depth=50, error_rate=0.0)
    assert reason == "SLO_RECOVERED_PARALLEL"

    status = manager.get_symbol_status("XAUUSD")
    assert status["mode"] == "full"
    assert status["consecutive_healthy_minutes"] == 5
