---
phase: 26
slug: signal-event-pipeline-strategy-contract
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | existing (root-level) |
| **Quick run command** | `pytest tests/ -q --tb=short` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -q --tb=short`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01 | 26-PLAN | 1 | NOTIF-01, STRAT-01 | — | Signal events publish to Redis correctly | unit+integration | `pytest tests/test_signal_events.py` | ✅ | ⬜ pending |
| 26-02 | 26-PLAN | 1 | STRAT-02, STRAT-03 | — | Strategy output includes entry_type, SL, TP, lot_size | unit | `pytest tests/test_strategy_contract.py` | ✅ | ⬜ pending |
| 26-03 | 26-PLAN | 2 | STRAT-04 | — | Existing strategies backward compatible | integration | `pytest tests/test_backward_compat.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing test infrastructure covers signal engine and strategy evaluation.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end signal pipeline from engine → Redis → consumer | NOTIF-01 | Requires Docker services running | Start all services, trigger signal, verify Redis pub/sub delivery |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
