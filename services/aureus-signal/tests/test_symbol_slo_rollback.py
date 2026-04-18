import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.strategy_executor import resolve_strategy_processing_mode, run_strategy_executor
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


def test_run_strategy_executor_wires_health_manager_runtime_path():
    source = inspect.getsource(run_strategy_executor)
    assert "SymbolRuntimeHealthManager(" in source
    assert "resolve_strategy_processing_mode(" in source
    assert "update_symbol_metrics(" in source


def test_strategy_rollout_resolution_is_scoped_per_symbol():
    manager = SymbolRuntimeHealthManager()
    manager.set_symbol_mode("XAUUSD", "full")
    manager.set_symbol_mode("EURUSD", "full")

    for _ in range(3):
        manager.update_symbol_metrics("XAUUSD", lag_p95_ms=3000.0, queue_depth=260, error_rate=0.1)

    assert resolve_strategy_processing_mode("XAUUSD", manager) == "fallback_serial"
    assert resolve_strategy_processing_mode("EURUSD", manager) == "full"

    xau_status = manager.get_symbol_status("XAUUSD")
    eur_status = manager.get_symbol_status("EURUSD")
    assert xau_status["allow_parallel"] is False
    assert eur_status["allow_parallel"] is True
