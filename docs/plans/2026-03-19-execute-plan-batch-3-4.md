# Execute-Plan Batch 3–4 (Day 8–14)

Implement Day 8–14 from `docs/plans/2026-03-19-aureus-next-2week-task-breakdown.md` in the current workspace (`d:\AIFramework\aureus`), following the existing no-worktree constraint previously accepted.

## User Review Required

> [!IMPORTANT]
> `aureus_bridge_duplicate_trace_id_total` is referenced by current SLO/alerts but is not emitted by the bridge exporter yet. For Batch 3 we will keep node-side fallback evidence (`test_execution_risk_controls.py`) while adding an exporter metric to close this gap.

> [!WARNING]
> Docker runtime commands may not be fully executable in this tool environment. Where runtime drills cannot be fully executed here, I will provide reproducible scripts/runbook steps and collect all available local evidence.

## Proposed Changes

### 1) Batch 3 — Alert Tuning + Golden Signals (Day 8)

#### [MODIFY] [nautilus-alerts.yml](file:///d:/AIFramework/aureus/monitoring/prometheus/rules/nautilus-alerts.yml)
- Tune noisy conditions/`for` windows and severity labels for production canary behavior.
- Keep strict `missing_sl`/`missing_tp` as promotion blockers.
- Align duplicate-trace behavior with exporter-backed signal once added.

#### [MODIFY] [main.py](file:///d:/AIFramework/aureus/services/aureus-bridge-metrics-exporter/main.py)
- Add missing golden signal metric export for duplicate traces (and any related labels/counters needed by rules/dashboard).
- Preserve backward compatibility with existing metrics scraping.

#### [MODIFY] [aureus_nautilus_flow.json](file:///d:/AIFramework/aureus/monitoring/grafana/dashboards/aureus_nautilus_flow.json)
- Add/adjust panels to surface tuned alerts and golden signals clearly for on-call decisions.

---

### 2) Batch 3 — Chaos Test + Replay Test (Day 10–11)

#### [NEW] [test_chaos_redis_disconnect.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/tests/test_chaos_redis_disconnect.py)
- Add deterministic chaos test coverage for Redis disconnect/reconnect and recovery expectations.
- Assert no crash-loop behavior and expected error/retry metrics/logging behavior.

#### [NEW] [test_replay_duplicate_stale_stream.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/tests/test_replay_duplicate_stale_stream.py)
- Add replay-oriented tests for duplicate stream IDs and stale stream behavior.
- Validate duplicate/staleness detection paths align with rollout gating assumptions.

#### [MODIFY] [test_data_client.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/tests/test_data_client.py)
- Extend current client tests with explicit duplicate/stale edge cases and metrics assertions.

#### [MODIFY] [replay_data.py](file:///d:/AIFramework/aureus/scripts/replay_data.py)
- Make replay script path/configuration portable for current workspace.
- Add flags/modes to support duplicate and stale replay scenarios for runbook drills.

---

### 3) Batch 4 — Load + Shadow/Canary Automation + Final Report (Day 12–14)

#### [NEW] [test_load_idempotency_oco.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/tests/test_load_idempotency_oco.py)
- Simulate higher-volume order intents to validate idempotency and OCO safety invariants under stress.
- Verify rejection/acceptance metrics and stable decision behavior.

#### [MODIFY] [rollout_gates.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/rollout_gates.py)
- Extend gate evaluation helpers for structured canary evidence aggregation (load + shadow signals).

#### [MODIFY] [test_shadow_canary_flow.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/tests/test_shadow_canary_flow.py)
- Add tests for extended canary gate logic and failure-reason transparency.

#### [MODIFY] [nautilus-production-rollout.md](file:///d:/AIFramework/aureus/docs/runbooks/nautilus-production-rollout.md)
- Add shadow rehearsal checklist and automated canary-gate execution steps.
- Include clear evidence capture template for Go/No-Go.

#### [NEW] [2026-03-19-go-no-go-report.md](file:///d:/AIFramework/aureus/docs/plans/2026-03-19-go-no-go-report.md)
- Produce final release decision report structure with:
  - SLO results
  - alert/chaos/replay/load evidence summary
  - residual risks
  - explicit Go/No-Go recommendation.

#### [MODIFY] [task.md](file:///d:/AIFramework/aureus/docs/plans/task.md)
- Add Batch 3/4 tracker rows (`B3-*`, `B4-*`) and update statuses/evidence as tasks complete.

## Verification Plan

### Automated Tests
Run from `d:/AIFramework/aureus/services/aureus-nautilus-node` unless noted.

1. `python -m pytest -q`
2. `python -m ruff check .`
3. `python -m mypy --explicit-package-bases --ignore-missing-imports --disable-error-code no-redef execution_client.py data_client.py rollout_gates.py`
4. Targeted new suites:
   - `python -m pytest -q tests/test_chaos_redis_disconnect.py`
   - `python -m pytest -q tests/test_replay_duplicate_stale_stream.py`
   - `python -m pytest -q tests/test_load_idempotency_oco.py`

### Manual Verification
1. Replay duplicate/stale scenarios via updated `scripts/replay_data.py` and confirm expected metrics/log behavior.
2. Capture bridge metrics snapshot:
   - `cmd /c curl -s http://localhost:19158/metrics | findstr /I "missing_sl missing_tp duplicate_trace pnl backlog latency"`
3. Validate rollout runbook dry-run steps and canary gate decision output consistency.
4. Update `docs/plans/task.md` and finalize `docs/plans/2026-03-19-go-no-go-report.md` with evidence links/outputs.
