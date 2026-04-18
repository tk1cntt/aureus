---
phase: 45
slug: h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-18
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | none — dùng discovery mặc định |
| **Quick run command** | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q` |
| **Full suite command** | `python3 -m pytest /d/Aureus/services/aureus-signal/tests -q` |
| **Estimated runtime** | ~180 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q`
- **After every plan wave:** Run `python3 -m pytest /d/Aureus/services/aureus-signal/tests -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 300 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | PH45-01 | T-45-01 | Worker per-symbol không chặn symbol khác | integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_multi_symbol.py -q` | ✅ | ⬜ pending |
| 45-01-02 | 01 | 1 | PH45-02/03 | T-45-02 | FIFO strict + drop out-of-order candle | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_live_engine_gates.py -q` | ✅ | ⬜ pending |
| 45-02-01 | 02 | 2 | PH45-04/05 | T-45-03 | Snapshot đúng candle + trace_id dedupe strict | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_strategy_trigger_lifecycle.py -q` | ✅ | ⬜ pending |
| 45-03-01 | 03 | 3 | PH45-06/07 | T-45-04 | Circuit-breaker/backlog/SLO rollback per-symbol | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-signal/tests/test_circuit_breaker.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/aureus-signal/tests/test_per_symbol_worker_runtime.py` — lifecycle worker queue + backlog + breaker
- [ ] `services/aureus-signal/tests/test_out_of_order_drop_policy.py` — verify drop+ack+metric
- [ ] `services/aureus-signal/tests/test_symbol_slo_rollback.py` — SLO breach liên tiếp -> fallback tuần tự symbol đó

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Shadow->Canary->Full rollout per-symbol | PH45-07 | Cần môi trường runtime có stream live đa symbol | Bật cờ shadow cho 1 symbol, so sánh output shadow và live; tăng canary; xác nhận auto rollback chỉ tác động symbol vi phạm SLO |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 300s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending