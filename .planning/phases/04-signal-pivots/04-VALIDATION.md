---
phase: 04
slug: signal-pivots
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-21
updated: 2026-03-21
---

# Phase 04 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Quick run command** | `python -m pytest services/aureus-signal/tests/test_zigzag_regression.py services/aureus-signal/tests/test_zigzag_realtime.py -q` |
| **Runtime-path command** | `python -m pytest services/aureus-signal/tests/test_pivots_integration_live_engine.py -q` |
| **Coverage command** | `python -m pytest services/aureus-signal/tests/test_zigzag_regression.py services/aureus-signal/tests/test_zigzag_realtime.py services/aureus-signal/tests/test_pivots_integration_execute_signals_for_candle.py services/aureus-signal/tests/test_pivots_integration_live_engine.py --cov=services/aureus-signal/engine/signals/pivots.py --cov-report=term-missing -q` |

## Per-Task Verification Map

| Task ID | Plan | Requirement | Test Type | Automated Command | Status |
|---------|------|-------------|-----------|-------------------|--------|
| 04-01-01 | 01 | SIG-04 | unit | `python -m pytest services/aureus-signal/tests/test_zigzag_regression.py services/aureus-signal/tests/test_zigzag_realtime.py -q` | ⏳ planned |
| 04-01-02 | 01 | TST-02 | integration | `python -m pytest services/aureus-signal/tests/test_pivots_integration_execute_signals_for_candle.py -q` | ⏳ planned |
| 04-01-03 | 01 | TST-01,TST-02 | runtime integration | `python -m pytest services/aureus-signal/tests/test_pivots_integration_live_engine.py -q` | ⏳ planned |
| 04-01-04 | 01 | TST-03,TST-04 | coverage + gate | `python -m pytest services/aureus-signal/tests/test_zigzag_regression.py services/aureus-signal/tests/test_zigzag_realtime.py services/aureus-signal/tests/test_pivots_integration_execute_signals_for_candle.py services/aureus-signal/tests/test_pivots_integration_live_engine.py --cov=services/aureus-signal/engine/signals/pivots.py --cov-report=term-missing -q` | ⏳ planned |

## Validation Sign-Off

- [ ] Dedicated pivots unit test coverage exists and passes.
- [ ] Dedicated pivots integration test coverage exists and passes.
- [ ] Runtime-path integration test validates stable pivots behavior.
- [ ] Coverage for changed pivots scope is `100%`.
- [ ] Phase closure only after all gates are green.
