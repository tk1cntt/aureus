# Aureus Next Plan (2 Weeks, Balanced)

## Week 1 — Stabilize & Gate
### Goals
- Reach controlled go-live readiness.

### Workstreams
1. **Go-live readiness**
   - Clean lint/type warnings in `data_client.py`, `execution_client.py`
   - Add CI quality gates: `pytest`, lint, type-check
   - Finalize preflight deploy checklist

2. **Observability baseline**
   - Define initial SLOs: restart rate, missing SL/TP, duplicate trace IDs, stream freshness
   - Complete baseline dashboards and alert thresholds
   - Dry-run alert firing path

3. **Trading safety baseline**
   - Confirm kill-switch runbook and trigger criteria
   - Add smoke scenarios for strict-risk violations
   - Run one rollback drill cycle

### End-of-week gate
- CI green
- No critical warnings
- Alert + rollback drill validated

---

## Week 2 — Harden & Drill
### Goals
- Prepare for practical shadow/canary operation.

### Workstreams
1. **Advanced observability**
   - Tune alerts to reduce false positives
   - Add golden signals for bridge/node path
   - Standardize incident timeline template

2. **Safety hardening**
   - Controlled chaos/replay tests (Redis disconnect, duplicate stream, stale feed)
   - Measure rollback MTTR
   - Validate idempotency/OCO under simulated load

3. **Release readiness**
   - Shadow window checklist execution
   - Canary gate automation via `rollout_gates.py`
   - Go/No-go decision package for full promotion

### End-of-week gate
- Stable shadow window
- Canary gates pass at defined thresholds
- Sufficient operational evidence for broader production rollout

---

## Deliverables
- CI quality gates (lint/type/test)
- Production dashboard + tuned alerts
- Chaos/replay test report
- Rollback drill report + MTTR
- Canary decision report (go/no-go)
