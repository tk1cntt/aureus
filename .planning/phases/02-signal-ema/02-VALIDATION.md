---
phase: 02
slug: signal-ema
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-20
updated: 2026-03-20T23:21:13+07:00
---

# Phase 02 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `services/aureus-signal/pytest.ini` (or project default pytest config) |
| **Quick run command** | `python -m pytest services/aureus-signal/tests/test_ema_o1.py services/aureus-signal/tests/test_ema_integration_execute_signals_for_candle.py -q` |
| **Full suite command** | `python -m pytest services/aureus-signal/tests -k "ema" -q` |
| **Estimated runtime** | ~45 seconds |

## Sampling Rate

- After every task commit: run the quick EMA command.
- After plan wave completion: run the full EMA subset command.
- Before `/gsd-verify-work`: rerun full EMA subset + coverage check.
- Max feedback latency: 60 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SIG-02 | unit | `python -m pytest services/aureus-signal/tests/test_ema_o1.py -q` | ✅ | ✅ green |
| 02-01-02 | 01 | 1 | TST-02 | integration | `python -m pytest services/aureus-signal/tests/test_ema_integration_execute_signals_for_candle.py -q` | ✅ | ✅ green |
| 02-01-03 | 01 | 1 | TST-03,TST-04 | coverage + gate | `python -m pytest tests/test_ema_o1.py tests/test_ema_integration_execute_signals_for_candle.py --cov=engine.signals.ema --cov-report=term-missing -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky/blocked*

## Execution Results (Observed)

1. Quick gate:
   - `python -m pytest services/aureus-signal/tests/test_ema_o1.py services/aureus-signal/tests/test_ema_integration_execute_signals_for_candle.py -q`
   - Result: `6 passed`
2. Coverage gate:
   - `python -m pytest tests/test_ema_o1.py tests/test_ema_integration_execute_signals_for_candle.py --cov=engine.signals.ema --cov-report=term-missing -q`
   - Result: `6 passed`, `engine/signals/ema.py = 92%`.
3. Collection blocker follow-up:
   - `pytest services/aureus-signal/tests/test_multi_symbol.py services/aureus-signal/tests/test_strategy_contract_v1.py -q`
   - Result: `10 passed in 1.48s`.

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

- All target behaviors for this phase have automated verification.

## Validation Sign-Off

- [x] All tasks have automated verification commands.
- [x] Sampling continuity is maintained across all tasks.
- [x] No watch-mode flags are used.
- [x] Coverage gate (`100%`) is proven in command output.
- [x] Phase closure condition met for unit + integration + coverage checks.

**Approval:** approved
