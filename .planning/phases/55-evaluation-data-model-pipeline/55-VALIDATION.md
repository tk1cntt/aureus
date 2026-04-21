---
phase: 55
slug: evaluation-data-model-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-21
---

# Phase 55 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | services/aureus-gateway/tests/pytest.ini |
| **Quick run command** | `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests/test_strategy_scoring_aggregate.py tests/test_strategy_scoring_e2e.py -q"` |
| **Full suite command** | `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && .venv/bin/python -m pytest services/aureus-trader/tests services/aureus-signal/tests -q"` |
| **Estimated runtime** | ~180 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick scoring/pipeline subset for changed scope
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 55-01-01 | 01 | 1 | EVAL-01,SIGNAL-SNAPSHOT-01 | — | Migration extends journal-linked evaluation + signal snapshot schema | unit/integration | `pytest services/aureus-db-writer/tests/test_evaluation_migration.py services/aureus-trader/tests/test_signal_snapshot_migration.py -q` | ✅ | ⬜ pending |
| 55-01-02 | 01 | 1 | EVAL-01,EVAL-04,SIGNAL-SNAPSHOT-01 | — | Constraints + uniqueness/idempotency reject duplicates on evaluation/signal snapshot | unit | `pytest services/aureus-db-writer/tests/test_evaluation_migration.py services/aureus-trader/tests/test_signal_snapshot_migration.py -q` | ✅ | ⬜ pending |
| 55-02-01 | 02 | 2 | EVAL-02,SIGNAL-SNAPSHOT-01 | — | Persist trigger executes only after ORDER_OPENED success for evaluation/signal snapshot | integration | `pytest services/aureus-trader/tests/test_dispatcher.py services/aureus-trader/tests/test_signal_snapshot_pipeline.py -q` | ✅ | ⬜ pending |
| 55-02-02 | 02 | 2 | EVAL-02,EVAL-04,SIGNAL-SNAPSHOT-01 | — | Persist writes full evaluation + signal snapshot records with lineage fields | integration | `pytest services/aureus-trader/tests/test_evaluation_pipeline.py services/aureus-trader/tests/test_signal_snapshot_pipeline.py -q` | ✅ | ⬜ pending |
| 55-03-01 | 03 | 3 | EVAL-03,SIGNAL-SNAPSHOT-01 | — | Recompute appends new score/signal schema versions without overwriting history | integration | `pytest services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -q` | ✅ | ⬜ pending |
| 55-03-02 | 03 | 3 | EVAL-03,EVAL-04,SIGNAL-SNAPSHOT-01 | — | Recompute remains idempotent across reruns for evaluation/signal snapshots | integration | `pytest services/aureus-trader/tests/test_evaluation_recompute.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/aureus-trader/tests/test_evaluation_persistence.py` — stubs for EVAL-01/02/04
- [ ] `services/aureus-trader/tests/test_signal_snapshot_migration.py` — stubs for SIGNAL-SNAPSHOT-01 index/constraint coverage
- [ ] `services/aureus-trader/tests/test_evaluation_recompute.py` — stubs for EVAL-03
- [ ] `services/aureus-trader/tests/test_signal_snapshot_recompute.py` — stubs for signal snapshot recompute/idempotency
- [ ] `services/aureus-trader/tests/conftest.py` — fixtures for journal-linked evaluation payloads + large-volume snapshot dataset

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ORDER_OPENED real MT5 integration boundary | EVAL-02 | Needs live MT5 bridge acknowledgment path | Run trader in simulated+live bridge env, place order, verify evaluation record appears only after ORDER_OPENED ack |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
