---
phase: 25
slug: rollout-gates-safe-fallback
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-05
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` / `pyproject.toml` |
| **Quick run command** | `pytest tests/ -m "circuit_breaker or fallback"` |
| **Full suite command** | `pytest tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | ROUT-04 | unit | `pytest tests/test_circuit_breaker.py` | ❌ W0 | ⬜ pending |
| 25-01-02 | 01 | 1 | ROUT-04 | unit | `pytest tests/providers/test_tradingagents_circuit.py` | ❌ W0 | ⬜ pending |
| 25-01-03 | 01 | 1 | ROUT-03 | unit | `pytest tests/test_ta_drift_telemetry.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_circuit_breaker.py` — stubs for ROUT-04
- [ ] `tests/providers/test_tradingagents_circuit.py` — stubs for ROUT-04
- [ ] `tests/test_ta_drift_telemetry.py` — stubs for ROUT-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Timescale telemetry | ROUT-03 | Database visibility | Ensure Grafana or TimescaleDB query shows rows inserted for drift logs |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
