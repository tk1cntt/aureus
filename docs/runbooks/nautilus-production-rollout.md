# Nautilus Production Rollout (Shadow -> Canary -> Full)

## Preconditions
- `docker-compose.prod.yml` is deployed and healthy.
- Prometheus is scraping `aureus-bridge-metrics`.
- Batch 1-4 unit tests are green.

## Step 1: Shadow Rehearsal Checklist
1. Deploy stack:
   - `docker compose -f docker-compose.prod.yml up -d --build`
2. Run shadow-only for at least 30 minutes.
3. Replay validation streams:
   - `python scripts/replay_data.py --scenario normal --clear-stream`
   - `python scripts/replay_data.py --scenario duplicate`
   - `python scripts/replay_data.py --scenario stale`
4. Capture evidence snapshots:
   - `increase(aureus_bridge_orders_missing_sl_total[5m])`
   - `increase(aureus_bridge_orders_missing_tp_total[5m])`
   - `changes(process_start_time_seconds{job="aureus_bridge_metrics"}[10m])`
   - `increase(aureus_bridge_duplicate_trace_id_total[10m])`

## Step 2: Automated Canary Promotion Gate
Promote to canary only if all checks pass:
- missing SL violations = `0`
- missing TP violations = `0`
- restart events = `0`
- duplicate trace IDs = `0`
- load rejected ratio `<= 0.05`
- shadow mismatches = `0`

### Gate Collection Example
```python
from rollout_gates import RolloutGateMetrics, evaluate_rollout_gate

metrics = RolloutGateMetrics(
    missing_sl_total=0,
    missing_tp_total=0,
    restart_per_hour=0.0,
    duplicate_trace_id_total=0,
    load_rejected_ratio=0.0,
    shadow_mismatch_total=0,
)
decision = evaluate_rollout_gate(metrics)
print(decision.allow_promotion, decision.reasons, decision.evidence)
```

### Validation Commands
- `docker compose -f docker-compose.prod.yml ps`
- `cmd /c curl -s http://localhost:19158/metrics | findstr /I "missing_sl missing_tp duplicate_trace realized_pnl process_start_time_seconds"`

## Step 3: Full Promotion Gate
After at least 60 minutes of stable canary:
1. Re-check all gate thresholds and evidence payload.
2. Confirm no DLQ spikes from sync worker.
3. Promote all symbols and redeploy.

## Evidence Capture Template
- Shadow window start/end:
- Canary window start/end:
- Metrics snapshot command output:
- Gate decision output (`allow_promotion`, `reasons`, `evidence`):
- Residual risks / mitigations:

## Post-Promotion Checks
- Node health endpoint returns healthy state:
  - `curl -s http://localhost:18080/healthz`
- Restart count remains flat:
  - `docker inspect -f "{{.RestartCount}}" aureus-nautilus-node`
- Metrics endpoint remains fresh:
  - `curl -s http://localhost:19158/metrics`
