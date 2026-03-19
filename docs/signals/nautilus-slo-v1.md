# Nautilus SLO v1 (Bridge + Node)

This document defines SLO v1 for rollout gates and maps each objective to available telemetry.

## SLO Objectives

| SLO | Target | Prometheus Signal | Severity | Operator Response |
|---|---|---|---|---|
| Restart rate | `0` restarts during canary window | `changes(process_start_time_seconds{job="aureus_bridge_metrics"}[10m])` | critical | Freeze promotion, inspect container restarts, review exporter/node logs |
| Missing SL | `0` missing SL events | `increase(aureus_bridge_orders_missing_sl_total[5m])` | critical | Block promotion, inspect order payload validation and upstream signal generation |
| Missing TP | `0` missing TP events | `increase(aureus_bridge_orders_missing_tp_total[5m])` | critical | Block promotion, inspect risk policy and strategy payload completeness |
| Duplicate trace IDs | `0` duplicate traces during canary | `increase(aureus_bridge_duplicate_trace_id_total[10m])` (instrumentation gap - currently not emitted by bridge exporter) | warning | Treat as release blocker signal from node-side logs/tests until exporter metric is added |
| Stream freshness | PnL stream age `<= 120s` | `time() - max(timestamp(aureus_bridge_realized_pnl))` | warning | Validate bridge exporter loop health and Redis stream ingestion |

## Notes

- SLO v1 intentionally uses currently scrapeable bridge metrics for go-live readiness.
- Duplicate-trace SLO is defined now for operational policy consistency, but exporter instrumentation is still pending.
- Rollout gates in `services/aureus-nautilus-node/rollout_gates.py` remain the source-of-truth policy checks for canary promotion decisions.
