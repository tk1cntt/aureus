# Execute-Plan Batch 2 (Week 1 Day 4–6)

Implement the next batch from `docs/plans/2026-03-19-aureus-next-2week-task-breakdown.md` using the existing no-worktree constraint in `d:\AIFramework\aureus`.

## User Review Required

> [!IMPORTANT]
> `mypy` is not installed in the current environment (`python -m mypy ...` returns `No module named mypy`).
> For Batch 2 quality gates, I will wire `mypy` into CI and local commands, but local verification in this environment may still fail until dependencies are installed.

> [!WARNING]
> The `executing-plans` skill recommends isolated worktrees, but per your instruction I will continue execution directly in `d:\AIFramework\aureus`.

## Proposed Changes

### 1) CI Quality Gate Pipeline
Create/adjust a reproducible quality gate for `aureus-nautilus-node` covering `pytest`, lint, and type-check.

#### [NEW] [aureus-nautilus-node-quality.yml](file:///d:/AIFramework/aureus/.github/workflows/aureus-nautilus-node-quality.yml)
- Add CI job(s) to run in `services/aureus-nautilus-node`:
  - dependency install
  - `pytest -q`
  - lint command (targeted Python lint scope)
  - type-check command (`mypy`) for targeted modules
- Ensure CI fails on any non-zero command exit.

#### [MODIFY] [requirements.txt](file:///d:/AIFramework/aureus/services/aureus-nautilus-node/requirements.txt)
- Add missing quality dependencies required by Batch 2 gates (at minimum `mypy`; lint dependency depending on selected tool).

#### [NEW] [QUALITY_GATES.md](file:///d:/AIFramework/aureus/docs/runbooks/QUALITY_GATES.md)
- Document exact local/CI commands and expected pass/fail behavior.
- Include quick troubleshooting notes for missing tooling.

---

### 2) SLO v1 and Metric Mapping
Define and document SLO v1 aligned to currently available bridge/node metrics.

#### [NEW] [nautilus-slo-v1.md](file:///d:/AIFramework/aureus/docs/signals/nautilus-slo-v1.md)
- Define SLOs and thresholds for:
  - restart rate
  - missing SL/TP
  - duplicate trace IDs
  - stream freshness
- Map each SLO to concrete metric names already in use (Prometheus/bridge metrics).
- Include alert severity and operator response hints.

#### [MODIFY] [task.md](file:///d:/AIFramework/aureus/docs/plans/task.md)
- Add/advance Batch 2 tracker rows (`B2-*`) with status and notes while execution proceeds.

---

### 3) Dashboard + Alert Baseline Tuning
Align dashboards and alert rules with SLO v1 and wire dry-run validation evidence.

#### [MODIFY] [nautilus-alerts.yml](file:///d:/AIFramework/aureus/monitoring/prometheus/rules/nautilus-alerts.yml)
- Tune alert conditions/labels/annotations based on agreed SLO v1 thresholds.
- Keep alerts mapped to rollout-gate metrics.

#### [MODIFY] [aureus_nautilus_flow.json](file:///d:/AIFramework/aureus/monitoring/grafana/dashboards/aureus_nautilus_flow.json)
- Ensure panels cover SLO v1 metrics and clear operator visibility.

#### [MODIFY] [nautilus-production-rollout.md](file:///d:/AIFramework/aureus/docs/runbooks/nautilus-production-rollout.md)
- Add a short dry-run alert validation section and expected evidence capture checklist.

## Verification Plan

### Automated Tests
Run from `d:/AIFramework/aureus/services/aureus-nautilus-node` unless noted.

1. `python -m pytest -q`
2. `python -m mypy execution_client.py data_client.py`
3. (from repo root) CI-equivalent command(s) documented in `docs/runbooks/QUALITY_GATES.md`

### Manual Verification
1. Confirm Prometheus rule syntax and load path consistency after edits.
2. Verify Grafana dashboard provisioning still references `monitoring/grafana/dashboards/aureus_nautilus_flow.json`.
3. Run metrics sampling check used in rollout docs:
   - `curl -s http://localhost:19158/metrics | findstr /I "missing_sl missing_tp duplicate_trace pnl"`
4. Review `docs/plans/task.md` to ensure Batch 2 items and notes are updated with evidence.
