---
phase: 30
slug: trade-state-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | existing (root-level) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
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
| 30-01 | 30-01-PLAN | 1 | TRADE-01 | — | Valid state transitions allowed | unit | `pytest tests/test_trade_state_machine.py -x` | ✅ | ✅ green |
| 30-01 | 30-01-PLAN | 1 | TRADE-01 | — | Invalid state transitions rejected | unit | `pytest tests/test_trade_state_machine.py::test_invalid_transitions -x` | ✅ | ✅ green |
| 30-01 | 30-01-PLAN | 1 | TRADE-02 | — | Order events upserted to aureus_trades | integration | `pytest tests/test_db_writer_orders.py -x` | ✅ | ✅ green |
| 30-01 | 30-01-PLAN | 1 | TRADE-02 | — | JSONB payload merge on conflict | integration | `pytest tests/test_db_writer_orders.py::test_payload_merge -x` | ✅ | ✅ green |
| 30-01 | 30-01-PLAN | 1 | TRADE-02 | — | Idempotent writes (duplicate trace_id) | integration | `pytest tests/test_db_writer_orders.py::test_idempotent_upsert -x` | ✅ | ✅ green |
| 30-01 | 30-01-PLAN | 1 | TRADE-05 | — | Bot trade filter query works | unit | `pytest tests/test_magic_number_filter.py -x` | ✅ | ✅ green |
| 30-01 | 30-01-PLAN | 1 | TRADE-05 | — | Manual trade filter query works | unit | `pytest tests/test_magic_number_filter.py::test_manual_filter -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (phase already implemented).

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
