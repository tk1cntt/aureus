---
phase: 08
slug: signal-volume-sma
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-21
updated: 2026-03-21
---

# Phase 08 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Quick run command** | `python -m pytest services/aureus-signal/tests/test_volume_sma_o1.py -q` |
| **Runtime-path command** | `python -m pytest services/aureus-signal/tests/test_volume_sma_integration_live_engine.py -q` |
| **Coverage command** | `python -m pytest services/aureus-signal/tests/test_volume_sma_o1.py services/aureus-signal/tests/test_volume_sma_integration_execute_signals_for_candle.py services/aureus-signal/tests/test_volume_sma_integration_live_engine.py --cov=services/aureus-signal/engine/signals/volume_sma.py --cov-report=term-missing -q` |

## Per-Task Verification Map

| Task ID | Plan | Requirement | Test Type | Automated Command | Status |
|---------|------|-------------|-----------|-------------------|--------|
| 08-01-02 | 01 | SIG-08 | unit | `python -m pytest services/aureus-signal/tests/test_volume_sma_o1.py -q` | ⏳ planned |
| 08-01-03 | 01 | TST-02 | integration | `python -m pytest services/aureus-signal/tests/test_volume_sma_integration_execute_signals_for_candle.py -q` | ⏳ planned |
| 08-01-04 | 01 | TST-01,TST-02 | runtime integration | `python -m pytest services/aureus-signal/tests/test_volume_sma_integration_live_engine.py -q` | ⏳ planned |
| 08-01-04 | 01 | TST-03,TST-04 | coverage + gate | `python -m pytest services/aureus-signal/tests/test_volume_sma_o1.py services/aureus-signal/tests/test_volume_sma_integration_execute_signals_for_candle.py services/aureus-signal/tests/test_volume_sma_integration_live_engine.py --cov=services/aureus-signal/engine/signals/volume_sma.py --cov-report=term-missing -q` | ⏳ planned |

## Validation Sign-Off

- [ ] Dedicated Volume SMA unit test coverage exists and passes.
- [ ] Dedicated Volume SMA integration test coverage exists and passes.
- [ ] Runtime-path integration test validates stable threshold behavior.
- [ ] Coverage gate command for changed scope passes.
- [ ] Phase closure only after all gates are green.
