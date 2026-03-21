---
phase: 05
slug: signal-session-optimization
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-21
updated: 2026-03-21
---

# Phase 05 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Quick run command** | `python -m pytest services/aureus-signal/tests/test_session_o1.py services/aureus-signal/tests/test_session_integration_execute_signals_for_candle.py -q` |
| **Runtime-path command** | `python -m pytest services/aureus-signal/tests/test_session_integration_live_engine.py -q` |
| **Coverage command (executed from `services/aureus-signal`)** | `python -m pytest tests/test_session_o1.py tests/test_session_integration_execute_signals_for_candle.py tests/test_session_integration_live_engine.py --cov=engine.signals.session --cov-report=term-missing -q` |

## Per-Task Verification Map

| Task ID | Plan | Requirement | Test Type | Automated Command | Status |
|---------|------|-------------|-----------|-------------------|--------|
| 05-01-01 | 01 | SIG-05 | unit | `python -m pytest services/aureus-signal/tests/test_session_o1.py -q` | ✅ pass |
| 05-01-02 | 01 | TST-02 | integration | `python -m pytest services/aureus-signal/tests/test_session_integration_execute_signals_for_candle.py -q` | ✅ pass |
| 05-01-03 | 01 | TST-01,TST-02 | runtime integration | `python -m pytest services/aureus-signal/tests/test_session_integration_live_engine.py -q` | ✅ pass |
| 05-01-04 | 01 | TST-03,TST-04 | coverage + gate | `python -m pytest tests/test_session_o1.py tests/test_session_integration_execute_signals_for_candle.py tests/test_session_integration_live_engine.py --cov=engine.signals.session --cov-report=term-missing -q` | ✅ pass (91%) |

## Validation Sign-Off

- [x] Dedicated session unit test file exists and passes.
- [x] Dedicated session integration test file exists and passes.
- [x] Runtime-path integration test validates non-masked factory wiring.
- [x] Coverage gate for changed session scope passes (`91%`).
- [x] Phase closure only after all gates are green.
