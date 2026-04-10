---
phase: 31
slug: mt5-history-sync
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | existing (root-level) |
| **Quick run command** | `pytest tests/test_reconciliation.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run relevant module tests
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01 | 31-01-PLAN | 1 | TRADE-03 | — | XPENDING recovery on startup | unit | `pytest tests/test_xpending.py -x` | ✅ | ✅ green |
| 31-01 | 31-01-PLAN | 1 | TRADE-03 | — | Real-time order events persist to DB | integration | `pytest tests/test_order_persistence.py -x` | ✅ | ✅ green |
| 31-01 | 31-01-PLAN | 1 | TRADE-04 | — | Configurable poll interval validation | unit | `pytest tests/test_reconciliation.py::test_poll_interval -x` | ✅ | ✅ green |
| 31-01 | 31-01-PLAN | 1 | TRADE-04 | — | MT5 history comparison detects missing trades | unit | `pytest tests/test_reconciliation.py::test_missing_trade_detection -x` | ✅ | ✅ green |
| 31-01 | 31-01-PLAN | 1 | TRADE-04 | — | RECONCILED status insert with conflict handling | unit | `pytest tests/test_reconciliation.py::test_reconciled_insert -x` | ✅ | ✅ green |
| 31-01 | 31-01-PLAN | 1 | TRADE-04 | — | Discrepancy logging format | unit | `pytest tests/test_reconciliation.py::test_discrepancy_log -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (phase already implemented).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| REQUEST_TRADE_HISTORY command handler in MT5 EA | TRADE-04 | Requires live MT5 connection | Start EA, send REQUEST_TRADE_HISTORY, verify response format |
| Reconciliation loop detects real missing trades | TRADE-04 | Requires real MT5 + DB state | Create intentional missing trade, run reconciliation, verify detection |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
