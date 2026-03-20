---
phase: 03
slug: signal-fvg
status: completed
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-20
updated: 2026-03-20
---

# Phase 03 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Quick run command** | `python -m pytest services/aureus-signal/tests/test_fvg_o1.py services/aureus-signal/tests/test_fvg_integration_execute_signals_for_candle.py -q` |
| **Runtime-path command** | `python -m pytest services/aureus-signal/tests/test_fvg_integration_live_engine.py -q` |
| **Coverage command** | `python -m pytest tests/test_fvg_o1.py tests/test_fvg_integration_execute_signals_for_candle.py tests/test_fvg_integration_live_engine.py --cov=engine.signals.fvg --cov=engine.signals.fvg_up --cov=engine.signals.fvg_down --cov-report=term-missing -q` |

## Per-Task Verification Map

| Task ID | Plan | Requirement | Test Type | Automated Command | Status |
|---------|------|-------------|-----------|-------------------|--------|
| 03-01-01 | 01 | SIG-03 | unit | `python -m pytest services/aureus-signal/tests/test_fvg_o1.py -q` | ✅ pass (5 passed) |
| 03-01-02 | 01 | TST-02 | helper integration | `python -m pytest services/aureus-signal/tests/test_fvg_integration_execute_signals_for_candle.py -q` | ✅ pass (3 passed) |
| 03-01-03 | 01 | TST-01,TST-02 | factory + runtime integration | `python -m pytest services/aureus-signal/tests/test_signal_contract_normalization.py -k "fvg" -q && python -m pytest services/aureus-signal/tests/test_fvg_integration_live_engine.py -q` | ✅ pass (3 passed + 1 passed) |
| 03-01-04 | 01 | TST-03,TST-04 | coverage + gate | `python -m pytest tests/test_fvg_o1.py tests/test_fvg_integration_execute_signals_for_candle.py tests/test_fvg_integration_live_engine.py --cov=engine.signals.fvg --cov=engine.signals.fvg_up --cov=engine.signals.fvg_down --cov-report=term-missing -q` | ✅ pass (9 passed, total 87% coverage) |

## Validation Sign-Off

- [x] Dedicated FVG unit test file exists and passes.
- [x] Dedicated FVG helper integration test exists and passes.
- [x] Runtime-path integration test validates non-masked factory wiring.
- [x] Coverage for changed FVG scope is `>=80%`.
- [x] Phase closure only after all gates are green.
