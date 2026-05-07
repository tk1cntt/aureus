---
quick_id: 260507-qqh
mode: quick-full
status: planned
must_haves:
  truths:
    - aureus_trade_signal_snapshots persists D1 open, high, low, close values at entry time when source snapshot contains D1 OHLC.
    - Database schema supports persisted D1 OHLC fields.
    - Database/e2e verification creates or reads a real aureus_trade_signal_snapshots row with non-null D1 OHLC values.
  artifacts:
    - Migration/schema change if D1 OHLC columns do not already exist.
    - Source mapping/persistence change for D1 OHLC.
    - Regression test for D1 OHLC persistence.
    - Executor summary.
    - Verification report.
  key_links:
    - source D1 OHLC payload -> snapshot persistence insert/upsert via mapped open/high/low/close fields
    - snapshot persistence -> aureus_trade_signal_snapshots via D1 OHLC columns
    - DB/e2e verification -> real snapshot row with non-null D1 OHLC query
---

# Quick Task 260507-qqh Plan

## Goal

Persist D1 OHLC values at entry time into `aureus_trade_signal_snapshots`, with schema support and DB/e2e proof that created snapshot rows store non-null `d1_open`, `d1_high`, `d1_low`, and `d1_close`.

## Tasks

### Task 1 — Inspect existing D1 OHLC source and snapshot schema

- **files**: `services/**`, DB migration/schema files, tests near trade signal snapshot persistence.
- **action**: Find existing `aureus_trade_signal_snapshots` write path and current source payload keys for D1 OHLC. Confirm whether destination columns exist. Use GitNexus query/context; before editing any symbol, run `gitnexus_impact({target: "<symbol>", direction: "upstream"})` and record blast radius.
- **verify**: Summary documents exact source field names and destination column names.
- **done**: Mapping contract exists: source D1 OHLC -> `aureus_trade_signal_snapshots` columns.

### Task 2 — Add schema and persistence mapping

- **files**: Migration/schema file if needed; snapshot persistence source file(s); focused tests.
- **action**: Add minimal D1 OHLC columns if absent, following existing `d1_poc/d1_vah/d1_val` convention. Wire D1 open/high/low/close from existing indicator/signal snapshot data into insert/upsert payload. Add regression test asserting values reach insert payload or persistence layer.
- **verify**: Run focused pytest for the discovered snapshot persistence test path, expected form: `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest <snapshot_persistence_test_path> -q"`; executor must replace `<snapshot_persistence_test_path>` with actual test file/function.
- **done**: Source and schema persist D1 OHLC without changing unrelated snapshot fields.

### Task 3 — Run DB/e2e verification and pre-commit gate

- **files**: Changed source, migration/schema, test files.
- **action**: Run DB/e2e verification through WSL per `RUN_SERVICES.md`, creating or selecting a real `aureus_trade_signal_snapshots` row with non-null D1 OHLC. Run mandatory `gitnexus_detect_changes()` before any code commit. If GitNexus detect changes is unavailable or fails, stop before commit and document blocker in `.planning/quick/260507-qqh-persist-d1-ohlc-snapshot/260507-qqh-SUMMARY.md`.
- **verify**: DB query output shows non-null D1 OHLC; GitNexus detect changes passes before commit, or summary documents blocker and no code commit is made.
- **done**: DB proof captured, GitNexus pre-commit gate satisfied or blocker documented before commit.
