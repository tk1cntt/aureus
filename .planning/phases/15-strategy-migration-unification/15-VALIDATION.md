---
phase: 15
slug: strategy-migration-unification
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-22
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick run command** | `pytest tests/test_strategy_registry.py -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_strategy_registry.py` and `pytest tests/test_template_strategy.py`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | SEQ-03 | unit | `pytest tests/test_template_strategy_context.py` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 1 | SEQ-03 | unit | `pytest tests/test_strategy_registry.py` | ✅ | ⬜ pending |
| 15-01-03 | 01 | 2 | SEQ-04 | unit | `pytest tests/test_seed_strategies.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_template_strategy_context.py` — unit tests for ContextEvaluator inside TemplateStrategy

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Output Log Verification | SEQ-04 | Visual Log check | Run live_engine locally with seeded data, print out order plans to view if trailing/SL stops appear properly generated. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
