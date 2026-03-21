---
phase: 10
slug: phan-tich-toi-uu-sweep-targets
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-22
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/test_sweep_integration_execute_signals_for_candle.py tests/test_structure_integration_execute_signals_for_candle.py` |
| **Full suite command** | `pytest tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_sweep_integration_execute_signals_for_candle.py tests/test_structure_integration_execute_signals_for_candle.py`
- **After every plan wave:** Run `pytest tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | REQ-10-01 | unit | `pytest tests/test_structure_o1.py` | ✅ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | REQ-10-02 | unit | `pytest tests/test_structure_integration_execute_signals_for_candle.py` | ✅ W0 | ⬜ pending |
| 10-01-03 | 01 | 2 | REQ-10-03 | unit | `pytest tests/test_sweep_o1.py` | ✅ W0 | ⬜ pending |
| 10-01-04 | 01 | 2 | REQ-10-04 | unit | `pytest tests/test_sweep_integration_execute_signals_for_candle.py` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Golden Master Test suites exist for Structure and Sweep.
- [x] pytest infrastructure is operational.

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-03-22
