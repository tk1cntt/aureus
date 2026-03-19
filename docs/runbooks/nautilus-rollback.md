# Nautilus Rollback Runbook

## Trigger Conditions
Rollback immediately when any of the following is true:
- `missing_sl_total > 0`
- `missing_tp_total > 0`
- `restart_per_hour > 0`
- `duplicate_trace_id_total > 0`
- Sync DLQ rate spikes unexpectedly

## Immediate Actions
1. Freeze promotion:
   - Stop canary/full expansion.
2. Capture diagnostics:
   - `docker compose -f docker-compose.prod.yml logs --tail=200 aureus-nautilus-node`
   - `docker compose -f docker-compose.prod.yml logs --tail=200 aureus-bridge-metrics`
3. Record current restart counts:
   - `docker inspect -f "{{.RestartCount}}" aureus-nautilus-node`

## Rollback Commands
1. Scale down affected path:
   - `docker compose -f docker-compose.prod.yml stop aureus-nautilus-node aureus-nautilus-bridge`
2. Re-deploy previously known-good image tag/env.
3. Restart services:
   - `docker compose -f docker-compose.prod.yml up -d aureus-nautilus-node aureus-nautilus-bridge`

## Recovery Validation
- `docker compose -f docker-compose.prod.yml ps`
- `curl -s http://localhost:18080/healthz`
- `curl -s http://localhost:19158/metrics | findstr /I "missing_sl missing_tp duplicate_trace"`

Only resume rollout after all gate metrics return to zero and no restart increase is observed for 30 minutes.
