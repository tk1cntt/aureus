---
phase: 39
slug: fix-strategy-service-crash-from-unhandled-exceptions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | None detected — uses pytest defaults |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ --cov=engine` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_<specific_file>.py -x`
- **After every plan wave:** `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** All new test files pass, grep confirms no bare `except:` remains
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01 | 01-PLAN | 1 | REQ-39-1 | — | Strategy executor main loop recovers from unhandled exceptions | unit | `pytest tests/test_strategy_executor_crash.py -x` | ❌ W0 | ⬜ pending |
| 39-02 | 02-PLAN | 1 | REQ-39-2 | — | Background tasks (news, reload, integrity) don't crash silently | unit | `pytest tests/test_background_task_supervision.py -x` | ❌ W0 | ⬜ pending |
| 39-03 | 03-PLAN | 1 | REQ-39-3 | — | `recalculate_all_signals()` errors don't kill parent task | unit | `pytest tests/test_recalculate_resilience.py -x` | ❌ W0 | ⬜ pending |
| 39-04 | TBA | 2 | REQ-39-4 | — | Pubsub listeners reconnect after Redis disconnect | unit | `pytest tests/test_pubsub_resilience.py -x` | ❌ W0 | ⬜ pending |
| 39-lint | TBA | 1 | REQ-39-5 | — | No bare `except:` clauses remain | lint | `grep -rn "except:" engine/ --include="*.py"` | Manual | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_strategy_executor_crash.py` — covers REQ-39-1: main loop exception recovery
- [ ] `tests/test_background_task_supervision.py` — covers REQ-39-2: supervised background tasks
- [ ] `tests/test_recalculate_resilience.py` — covers REQ-39-3: recalculate error isolation
- [ ] `tests/test_pubsub_resilience.py` — covers REQ-39-4: pubsub reconnection
- [ ] `tests/conftest.py` — shared fixtures (mock Redis, mock DB pool)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Service survives prolonged run with injected errors | REQ-39-1 | Long-duration stability test | Run service for 10+ minutes with error injection, verify no crash |
| All background tasks recover from Redis disconnect | REQ-39-2/REQ-39-4 | Requires live Redis | Kill Redis, restart, verify all tasks reconnect |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
