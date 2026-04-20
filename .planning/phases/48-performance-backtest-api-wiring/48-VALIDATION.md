---
phase: 48
slug: performance-backtest-api-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-20
---

# Phase 48 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (API), npm build/typecheck (web) |
| **Config file** | none — Wave 0 creates targeted test scaffolding |
| **Quick run command** | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x` |
| **Full suite command** | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests -q -x && npm --prefix /d/Aureus/services/aureus-dashboard/web run build` |
| **Estimated runtime** | ~90-180 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x` and targeted web contract test when touched.
- **After every plan wave:** Run `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests -q -x && npm --prefix /d/Aureus/services/aureus-dashboard/web run build`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 48-01-01 | 01 | 1 | PERF-01 | T-48-01 | Response contract exposes trade entry/exit fields and pagination meta deterministically | integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "trades_contract"` | ❌ W0 | ⬜ pending |
| 48-01-02 | 01 | 1 | PERF-02 | T-48-02 | win_rate computed from same filtered trade set as table/chart | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "win_rate"` | ❌ W0 | ⬜ pending |
| 48-01-03 | 01 | 1 | PERF-03 | T-48-03 | profit_factor formula handles zero-loss edge case explicitly | unit | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "profit_factor"` | ❌ W0 | ⬜ pending |
| 48-01-04 | 01 | 1 | PERF-04 | T-48-04 | max_drawdown deterministic for ordered equity snapshots | unit | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "max_drawdown"` | ❌ W0 | ⬜ pending |
| 48-01-05 | 01 | 1 | PERF-05 | T-48-05 | avg_rr nullability and numeric typing are explicit in API contract | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "avg_rr"` | ❌ W0 | ⬜ pending |
| 48-01-06 | 01 | 1 | PERF-06 | T-48-06 | equity curve endpoint respects shared filters and ordering | integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "equity_curve"` | ❌ W0 | ⬜ pending |
| 48-01-07 | 01 | 1 | PERF-07 | T-48-07 | invalid filters return structured 4xx error instead of silent fallback | integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py -q -x -k "filter_validation"` | ❌ W0 | ⬜ pending |
| 48-02-01 | 02 | 1 | PERF-08 | T-48-08 | web page renders metrics/table/chart consistently and handles error state | component/integration | `npm --prefix /d/Aureus/services/aureus-dashboard/web run build` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `/d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py` — stubs covering PERF-01..PERF-07
- [ ] `/d/Aureus/services/aureus-dashboard/api/tests/conftest.py` — shared fixtures for deterministic data setup
- [ ] `/d/Aureus/services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx` — PERF-08 contract/error rendering check

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `/performance` browser smoke with live API data | PERF-08 | Needs real runtime wiring + UI rendering with backend availability | Start services per `RUN_SERVICES.md`, open `/performance`, apply same filter set and confirm cards/table/equity reflect same dataset and errors surface correctly for invalid params |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
