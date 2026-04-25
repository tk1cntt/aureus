---
phase: 260425-mfv-tpo-shape-output
plan: 01
subsystem: tpo-shape-display-and-replay-baseline
tags: [quick, tpo, telegram, replay, metadata]
dependency_graph:
  requires: [260425-m1y, REQ-LQO-06, REQ-LQO-07, REQ-LQO-08]
  provides: [display-only-tpo-shape-snapshot, telegram-heuristic-shape-rendering, replay-shape-baseline]
  affects: [services/aureus-signal, services/aureus-notifier]
tech_stack:
  added: []
  patterns: [display-only metadata passthrough, offline replay reporting]
key_files:
  created: []
  modified:
    - services/aureus-signal/engine/indicator_snapshot.py
    - services/aureus-signal/tests/test_indicator_snapshot.py
    - services/aureus-notifier/formatters.py
    - services/aureus-notifier/tests/test_formatters.py
    - services/aureus-signal/engine/signals/tpo_replay.py
    - services/aureus-signal/tests/test_tpo_replay.py
decisions:
  - Shape metadata remains explanatory/display-only and was not wired into scoring, templates, persistence, schema, or migrations.
  - Telegram wording uses heuristic confidence to avoid probability, win-rate, edge, or score implication.
metrics:
  completed_date: 2026-04-25
  duration_seconds: 0
  tasks_completed: 3
---

# Quick Task 260425-mfv: Calibrated TPO Shape Output Summary

Integrated calibrated TPO shape metadata into display-only indicator snapshots and SIGNAL ALERT Telegram, plus offline replay baseline metrics for flip-rate and confidence distribution without scoring or persistence changes.

## Completed Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Preserve calibrated TPO shape metadata in indicator snapshot | 9753667 | services/aureus-signal/engine/indicator_snapshot.py; services/aureus-signal/tests/test_indicator_snapshot.py |
| 2 | Render TPO shape safely in SIGNAL ALERT Telegram | 74556aa | services/aureus-notifier/formatters.py; services/aureus-notifier/tests/test_formatters.py |
| 3 | Add replay/backtest shape baseline metrics without scoring integration | 7c01219 | services/aureus-signal/engine/signals/tpo_replay.py; services/aureus-signal/tests/test_tpo_replay.py |

## What Changed

- `build_indicator_snapshot_for_telegram` now preserves dict-shaped `tpo_d1`, `tpo_h1`, and `tpo_m30` blocks containing `shape`, `shape_confidence_pct`, and `shape_scores_pct`, while safely returning `None` for malformed non-dict TPO blocks.
- SIGNAL ALERT TPO rendering now displays shape confidence as `Shape:D (heuristic 82.5%)` and tests assert no probability/scoring wording appears.
- `replay_tpo_calibration` now adds `shape_baseline` with per-timeframe `valid_shape_count`, `shape_flip_count`, `shape_flip_rate`, and confidence distribution (`count`, `min`, `max`, `avg`, stable buckets).

## Guardrail Confirmation

- No strategy scoring, scoring weights, seed strategy template, DB schema, migration, journal persistence, or database-facing persistence file was modified.
- Shape metadata is explanatory only; it is not passed into `tpo_strategy_tags_from_candidates` and existing threshold sensitivity emitted tag counts remain covered by tests.
- DB E2E was not required because no database-facing code was touched.

## GitNexus Evidence

### Impact Analysis

- `build_indicator_snapshot_for_telegram`: GitNexus CLI impact with `--repo Aureus`; risk `CRITICAL`; direct caller `_process_candle_work_item`; 6 affected processes in Engine. Change was limited to display-only sanitization and covered by focused tests.
- `format_signal_event`: GitNexus CLI impact with `--repo Aureus`; risk `LOW`; direct caller `enqueue`; affected process `Run_notifier -> Send_message`.
- `_fmt_tpo`: GitNexus CLI impact with `--repo Aureus`; risk `LOW`; direct caller `_format_indicator_section`; no affected processes reported directly.
- `replay_tpo_calibration`: GitNexus CLI impact with `--repo Aureus`; risk `LOW`; no upstream callers/processes reported.

### Detect Changes Limitation

- Required `gitnexus_detect_changes()` MCP tool was unavailable in this environment.
- CLI fallback commands `npx gitnexus detect-changes --repo Aureus` and `npx gitnexus detect_changes --repo Aureus` both returned `unknown command`.
- Scoped fallback diff/status was used before commits and showed only the task files for each commit.

## Verification

- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests/test_indicator_snapshot.py -q"` -> `19 passed`.
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-notifier && ../../.venv/bin/python -m pytest tests/test_formatters.py -q"` -> `19 passed`.
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests/test_tpo_replay.py -q"` -> `6 passed`.
- Combined focused regression:
  - Signal service: `tests/test_tpo_replay.py tests/test_indicator_snapshot.py -q` -> `25 passed`.
  - Notifier service: `tests/test_formatters.py -q` -> `19 passed`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected test execution context**
- **Found during:** Task 1 verification
- **Issue:** Running pytest from repo root could not import `engine` in this codebase layout.
- **Fix:** Followed `RUN_SERVICES.md` and executed tests via WSL from each service directory using repo `.venv`.
- **Files modified:** None
- **Commit:** N/A

## Known Stubs

None found in modified files for this plan.

## Threat Flags

None. Changes did not introduce new network endpoints, auth paths, file access patterns, persistence schema, or trust-boundary expansion beyond the plan threat model.

## Self-Check: PASSED

- Created/modified files exist.
- Task commits exist: `9753667`, `74556aa`, `7c01219`.
- Summary created at `D:/Aureus/.planning/quick/260425-mfv-t-ch-h-p-calibrated-tpo-shape-output-v-o/260425-mfv-SUMMARY.md`.
