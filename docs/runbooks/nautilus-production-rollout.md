# Nautilus Production Rollout (Shadow -> Canary -> Full)

## Preconditions
- `docker-compose.prod.yml` is deployed and healthy.
- Prometheus is scraping `aureus-bridge-metrics`.
- Batch 1-2 unit tests are green.

## Step 1: Shadow Mode
1. Deploy production stack:
   - `docker compose -f docker-compose.prod.yml up -d --build`
2. Keep shadow processing only (no promotion) for at least 30 minutes.
3. Capture gate metrics:
   - `increase(aureus_bridge_orders_missing_sl_total[5m])`
   - `increase(aureus_bridge_orders_missing_tp_total[5m])`
   - `changes(process_start_time_seconds{job="aureus_bridge_metrics"}[10m])`
   - `increase(aureus_bridge_duplicate_trace_id_total[10m])`

## Step 2: Canary Promotion Gate
Promote to canary only if all conditions hold:
- missing SL violations = `0`
- missing TP violations = `0`
- restart events = `0`
- duplicate trace IDs = `0`

Validation commands:
- `docker compose -f docker-compose.prod.yml ps`
- `cmd /c curl -s http://localhost:19158/metrics | findstr /I "aureus_bridge_orders_missing_sl_total aureus_bridge_orders_missing_tp_total aureus_bridge_realized_pnl process_start_time_seconds"`

## Step 3: Full Promotion Gate
After at least 60 minutes of stable canary:
1. Re-check all gate thresholds.
2. Confirm no DLQ spikes from sync worker.
3. Promote all symbols by updating deployment env and reloading stack.

## Dry-Run Alert Validation (Batch 2)
Capture and store evidence in rollout notes:
1. `NautilusBridgeRestartSpike` remains inactive during the dry-run window.
2. `NautilusMissingSLViolation` and `NautilusMissingTPViolation` remain inactive.
3. `NautilusPnLStreamStale` remains inactive while `aureus_bridge_realized_pnl` keeps updating.
4. If `aureus_bridge_duplicate_trace_id_total` is not emitted yet, document node-side fallback evidence (log scan + `test_execution_risk_controls.py`).

## Post-Promotion Checks
- Node health endpoint returns healthy state:
  - `curl -s http://localhost:18080/healthz`
- Restart count remains flat:
  - `docker inspect -f "{{.RestartCount}}" aureus-nautilus-node`
- Metrics endpoint remains fresh:
  - `curl -s http://localhost:19158/metrics`
