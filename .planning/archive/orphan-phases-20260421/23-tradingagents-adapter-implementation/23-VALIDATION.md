---
phase: 23
slug: tradingagents-adapter-implementation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-04
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / tox.ini |
| **Quick run command** | `pytest services/aureus-signal/tests/test_tradingagents_adapter.py` |
| **Full suite command** | `pytest services/aureus-signal/tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest services/aureus-signal/tests/test_tradingagents_adapter.py`
- **After every plan wave:** Run `pytest services/aureus-signal/tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | ADPT-01 | unit | `pytest services/aureus-signal/tests/test_tradingagents_adapter.py::test_decision_provider_interface` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | ADPT-02 | unit | `pytest services/aureus-signal/tests/test_tradingagents_adapter.py::test_symbol_mapping` | ❌ W0 | ⬜ pending |
| 23-01-03 | 01 | 1 | ADPT-03 | unit | `pytest services/aureus-signal/tests/test_tradingagents_adapter.py::test_cache_and_backoff` | ❌ W0 | ⬜ pending |
| 23-01-04 | 01 | 1 | ADPT-04 | unit | `pytest services/aureus-signal/tests/test_tradingagents_adapter.py::test_error_fallback` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/aureus-signal/tests/test_tradingagents_adapter.py` — test scaffolds for ADPT-01,02,03,04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| External 429 response | ADPT-04 | Requires hitting rate limit practically | Run adapter script loop against live testnet |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
