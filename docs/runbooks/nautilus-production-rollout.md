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
   - `missing_sl_total`
   - `missing_tp_total`
   - `restart_per_hour`
   - `duplicate_trace_id_total`

## Step 2: Canary Promotion Gate
Promote to canary only if all conditions hold:
- `missing_sl_total == 0`
- `missing_tp_total == 0`
- `restart_per_hour == 0`
- `duplicate_trace_id_total == 0`

Validation commands:
- `docker compose -f docker-compose.prod.yml ps`
- `curl -s http://localhost:19158/metrics | findstr /I "missing_sl missing_tp duplicate_trace pnl"`

## Step 3: Full Promotion Gate
After at least 60 minutes of stable canary:
1. Re-check all gate thresholds.
2. Confirm no DLQ spikes from sync worker.
3. Promote all symbols by updating deployment env and reloading stack.

## Post-Promotion Checks
- Node health endpoint returns healthy state:
  - `curl -s http://localhost:18080/healthz`
- Restart count remains flat:
  - `docker inspect -f "{{.RestartCount}}" aureus-nautilus-node`
- Metrics endpoint remains fresh:
  - `curl -s http://localhost:19158/metrics`
