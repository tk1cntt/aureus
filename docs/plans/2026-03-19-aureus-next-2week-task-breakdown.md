# Aureus 2-Week Task Breakdown (Day 1 → Day 14)

## Week 1 — Stabilize & Gate

### Day 1
- Baseline current warnings/errors (`lint`, `type-check`, `pytest`)
- Lock target quality gates and acceptance criteria
- Open cleanup task list for `data_client.py`, `execution_client.py`

### Day 2
- Fix highest-priority type/lint issues in `execution_client.py`
- Add/adjust tests for touched logic
- Re-run `pytest`, lint, type-check

### Day 3
- Fix highest-priority type/lint issues in `data_client.py`
- Add/adjust resilience tests if needed
- Re-run `pytest`, lint, type-check

### Day 4
- Implement CI quality gate pipeline (`pytest` + lint + type-check)
- Ensure failing gates block merge/deploy path
- Document CI commands and expected outputs

### Day 5
- Define SLO v1 (restart, missing SL/TP, duplicate trace ID, stream freshness)
- Map SLOs to concrete metrics and alert thresholds
- Validate metric naming consistency

### Day 6
- Build/update baseline dashboard panels
- Wire alert rules and run dry-fire simulations
- Record alert behavior (trigger + recovery)

### Day 7
- Run rollback drill + kill-switch validation
- Execute strict-risk smoke scenarios
- Week-1 gate review (Go/No-Go for Week 2)

---

## Week 2 — Harden & Drill

### Day 8
- Tune noisy alerts (reduce false positives)
- Add missing “golden signals” for bridge/node path
- Confirm on-call notification routing

### Day 9
- Standardize incident timeline template
- Prepare shadow-window run checklist
- Validate runbook command completeness

### Day 10
- Execute controlled chaos test #1 (Redis disconnect)
- Measure impact and recovery time
- Capture findings + action items

### Day 11
- Execute chaos/replay test #2 (duplicate stream/stale feed)
- Validate duplicate/staleness detection paths
- Capture findings + action items

### Day 12
- Simulate load for idempotency/OCO behavior
- Verify risk checks hold under stress
- Capture performance and correctness notes

### Day 13
- Run shadow-window rehearsal end-to-end
- Run automated canary gate evaluation (`rollout_gates.py`)
- Compile Go/No-Go evidence package draft

### Day 14
- Final gate review (SLOs, alerts, drills, tests)
- Publish release decision report (Go/No-Go)
- Freeze next sprint actions based on findings

---

## Daily Exit Criteria (applies every day)
- Planned tasks completed or explicitly deferred with reason
- Evidence logged (command output, metric snapshot, test result)
- Risks and blockers updated in tracker
