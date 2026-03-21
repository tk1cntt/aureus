| Task | Description | Status | Notes |
|---|---|---|---|
| PH00 | Signals foundation gate (Tasks 1-6) | in_progress | Executing `docs/plans/2026-03-20-phase-00-signals-foundation-gate-plan.md` |
| P1 | Closed-candle gate in `live_engine.py` + tests | completed | Batch 1 (Core Safety Gates) |
| P2 | Backfill readiness gate (`manager.py` + `live_engine.py`) + tests | completed | Batch 1 (Core Safety Gates) |
| P3 | Window integrity gate (`manager.py` + `live_engine.py`) + tests | completed | Batch 1 (Core Safety Gates) |
| P4 | Signal normalization in `signal_factory.py` + tests | completed | Batch 2 |
| P5 | Decision version metadata in `live_engine.py` + tests | completed | Batch 2 |
| P6 | Strategy base contract split in `strategies/base.py` + tests | completed | Batch 2 |
| P7 | Template strategy phased output + tests | completed | Batch 3 |
| P8 | Registry compatibility + orchestration + tests | not_started | Batch 3 |
| P9 | Trace schema builders in `snapshot_utils.py` + tests | not_started | Batch 3 |
| P10 | Order/state trace persistence (`orders.py`, `state.py`) + tests | not_started | Batch 4 |
| P11 | Execution policy validation in `execution_client.py` + tests | not_started | Batch 4 |
| P12 | Rollout gate thresholds in `rollout_gates.py` + tests | not_started | Batch 4 |
| P13 | Bridge lineage propagation in `main.py` + tests | not_started | Batch 5 |
| P14 | Final regression + coverage gates (100%) | not_started | Batch 5 |
| B1 | Explore project context for signal cleanup scope | completed | Reviewed `engine/signals`, `signal_factory.py`, and related tests |
| B2 | Ask clarifying questions (one at a time) | in_progress | Waiting for first answer before design proposal |
| B3 | Propose 2-3 approaches + recommendation | not_started | Mandatory brainstorming step |
| B4 | Present design sections and get approval | not_started | Must complete before coding |
| B5 | Write design doc in `docs/plans` | not_started | `YYYY-MM-DD-<topic>-design.md` |
| B6 | Transition via writing-plans flow | not_started | Final brainstorming terminal step |
