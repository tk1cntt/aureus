---
phase: 55-evaluation-data-model-pipeline
plan: 01
subsystem: evaluation-data-model-pipeline
tags: [evaluation, schema, migration, guardrails]
requires: []
provides: [EVAL-01, EVAL-04, SIGNAL-SNAPSHOT-01]
affects:
  - services/aureus-db-writer/migrations/add_trade_evaluations.sql
  - services/aureus-db-writer/tests/test_evaluation_migration.py
  - services/aureus-trader/tests/test_signal_snapshot_migration.py
  - services/aureus-trader/tests/test_evaluation_pipeline.py
tech_stack:
  added: [PostgreSQL, pytest]
  patterns: [append-only versioned rows, composite uniqueness, jsonb guardrails]
key_files:
  created:
    - services/aureus-db-writer/migrations/add_trade_evaluations.sql
    - services/aureus-db-writer/tests/test_evaluation_migration.py
    - services/aureus-trader/tests/test_signal_snapshot_migration.py
    - services/aureus-trader/tests/test_evaluation_pipeline.py
  modified: []
decisions:
  - Dùng unique(trade_journal_id, score_version) làm idempotency/lineage guard chính.
  - Tách bảng signal snapshot để lưu payload đầy đủ + typed columns phục vụ analytics.
metrics:
  started_at: "2026-04-21T00:00:00Z"
  completed_at: "2026-04-21T00:00:00Z"
  duration_seconds: 0
---

# Phase 55 Plan 01: Evaluation Schema + Signal Snapshot Guardrails Summary

Hoàn thành migration evaluation journal-linked với ràng buộc chống duplicate/sai shape ở DB-level, kèm test contracts TDD cho evaluation và signal snapshot.

## Tasks Completed

1. RED: tạo failing tests cho evaluation migration, signal snapshot migration, pipeline contract.
2. GREEN: implement `add_trade_evaluations.sql` với bảng `aureus_trade_evaluations` + `aureus_trade_signal_snapshots` và đầy đủ constraints/indexes theo plan.
3. Verification: chạy lại subset gồm migration tests và regression `test_journal.py` đều pass.

## Deviations from Plan

### Auto-fixed Issues

1. [Rule 3 - Blocking] Thiếu dependency `pytest_asyncio` trong môi trường test.
- Found during: Task 1 RED run
- Fix: cài `pytest-asyncio` để unblock chạy pytest.
- Files modified: none (environment-level)

## Known Stubs

None.

## Self-Check: PASSED
- FOUND: D:/Aureus/services/aureus-db-writer/migrations/add_trade_evaluations.sql
- FOUND: D:/Aureus/services/aureus-db-writer/tests/test_evaluation_migration.py
- FOUND: D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_migration.py
- FOUND: D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py
