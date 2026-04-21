---
phase: 54
slug: strategy-scoring-framework
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-21
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `services/aureus-gateway/tests/pytest.ini` |
| **Quick run command** | `python3 -m pytest services/aureus-signal/tests/test_template_strategy.py -q` |
| **Full suite command** | `python3 -m pytest services/aureus-signal/tests -q` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest services/aureus-signal/tests/test_template_strategy.py -q`
- **After every plan wave:** Run `python3 -m pytest services/aureus-signal/tests -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | SCOR-01 | T-54-01 | Scoring formula deterministic | unit | `python3 -m pytest services/aureus-signal/tests -k scoring_formula -q` | ❌ W0 | ⬜ pending |
| 54-01-02 | 01 | 1 | SCOR-02 | T-54-02 | score_version + weights snapshot immutable | unit | `python3 -m pytest services/aureus-signal/tests -k score_version -q` | ❌ W0 | ⬜ pending |
| 54-01-03 | 01 | 1 | SCOR-04 | T-54-03 | breakdown JSON đầy đủ + missing-data policy explicit | unit | `python3 -m pytest services/aureus-signal/tests -k breakdown -q` | ❌ W0 | ⬜ pending |
| 54-02-01 | 02 | 2 | SCOR-03 | T-54-04 | per-trade + aggregate outputs khớp key strategy/symbol/timeframe | integration | `python3 -m pytest services/aureus-signal/tests -k aggregate_score -q` | ❌ W0 | ⬜ pending |
| 54-02-02 | 02 | 2 | ACC-01 | T-54-05 | end-to-end scoring pipeline chạy và persist được dữ liệu audit | integration | `python3 -m pytest services/aureus-signal/tests -k scoring_e2e -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/aureus-signal/tests/test_strategy_scoring_formula.py` — stubs cho SCOR-01
- [ ] `services/aureus-signal/tests/test_strategy_scoring_versioning.py` — stubs cho SCOR-02
- [ ] `services/aureus-signal/tests/test_strategy_scoring_breakdown.py` — stubs cho SCOR-04
- [ ] `services/aureus-signal/tests/test_strategy_scoring_aggregate.py` — stubs cho SCOR-03
- [ ] `services/aureus-signal/tests/test_strategy_scoring_e2e.py` — stubs cho ACC-01

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending