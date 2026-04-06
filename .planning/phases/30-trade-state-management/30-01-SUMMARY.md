---
phase: 30
plan: 01
type: execute
wave: 1
subsystem: aureus-db-writer
tags:
  - trade-state-management
  - state-machine
  - timescaledb
  - redis-stream
requires:
  - Phase 26: Magic number per strategy (aureus_strategy_templates.magic_number column)
provides:
  - Trade state machine with 6 states and validated transitions
  - order_buffer in DB writer with Redis stream consumption
  - Magic number filter SQL queries for bot vs manual trade classification
affects:
  - services/aureus-db-writer/schema.sql
  - services/aureus-db-writer/main.py
  - services/aureus-db-writer/state_machine.py
tech-stack:
  added:
    - Python state machine module (state_machine.py)
    - SQL filter queries (queries/magic_number_filters.sql)
  patterns:
    - State transition validation before DB write
    - ON CONFLICT (trace_id) DO UPDATE with JSONB payload merge
    - Redis stream consumer with batch ACK after successful insert
key-files:
  created:
    - services/aureus-db-writer/state_machine.py
    - services/aureus-db-writer/tests/test_state_machine.py
    - services/aureus-db-writer/tests/test_order_buffer.py
    - services/aureus-db-writer/tests/test_magic_number_filter.py
    - services/aureus-db-writer/queries/magic_number_filters.sql
  modified:
    - services/aureus-db-writer/main.py
    - services/aureus-db-writer/schema.sql (already had aureus_trades from prior work)
decisions:
  - "New trade records must start as PENDING status — other initial statuses rejected"
  - "Invalid state transitions are ACKed (not requeued) to prevent poison pill loops"
  - "State transition validated via DB lookup of existing status before insert"
metrics:
  duration_minutes: 15
  completed_date: "2026-04-06T22:55:00Z"
  tests_added: 64
  tests_total: 66
  files_created: 5
  files_modified: 1
---

# Phase 30 Plan 01: Trade State Management Summary

**One-liner:** Trade state machine with 6-state lifecycle (PENDING→SENT→FILLED→CLOSED/FAILED/CANCELLED), TimescaleDB persistence via order_buffer in DB writer, and magic_number SQL filters for bot vs manual trade classification.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T1 | Create aureus_trades hypertable and state machine module | `2b6b0f6` | state_machine.py, tests/test_state_machine.py |
| T2 | Implement order_buffer in DB writer with Redis stream consumption | `428bc20` | main.py, tests/test_order_buffer.py |
| T3 | Create magic number filter queries and integration verification | `f21447d` | queries/magic_number_filters.sql, tests/test_magic_number_filter.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing validation] New records required initial status validation**
- **Found during:** Task 2 (test_order_buffer.py — invalid PENDING→FILLED test)
- **Issue:** Code only validated transitions for existing records. New records with non-PENDING initial status (e.g., FILLED) were accepted without validation.
- **Fix:** Added check: if no existing record found, new_status must be 'PENDING'. Otherwise rejected with warning log.
- **Files modified:** services/aureus-db-writer/main.py
- **Commit:** `428bc20`

**2. [Rule 2 - Security] Invalid direction/entry_type values defaulted instead of rejected**
- **Found during:** Task 2 (threat model T-30-01 mitigation)
- **Issue:** direction and entry_type from untrusted Redis payloads could contain arbitrary values.
- **Fix:** Added validation: direction must be BUY/SELL, entry_type must be MARKET/LIMIT/STOP. Invalid values default to 'UNKNOWN' with warning log.
- **Files modified:** services/aureus-db-writer/main.py
- **Commit:** `428bc20`

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:T-30-01 | main.py | direction/entry_type validated against allowed sets before DB write |
| threat_flag:T-30-02 | main.py | validate_transition() called before every insert, invalid transitions logged with trace_id |
| threat_flag:T-30-05 | main.py | All parameters passed as positional args ($1..$20) to asyncpg.executemany |

## Known Stubs

None. All functionality is fully wired.

## Test Results

```
66 passed, 2 warnings in 0.99s
- test_state_machine.py: 46 tests (valid/invalid transitions, terminal states, edge cases)
- test_order_buffer.py: 5 tests (valid transition, invalid transition, conflict update, missing trace_id, magic_number)
- test_magic_number_filter.py: 13 tests (query structure, mocked results, edge cases)
- test_position_account_ingest.py: 2 tests (pre-existing, still passing)
```

## Self-Check: PASSED

- [x] state_machine.py exists and exports all required symbols
- [x] tests/test_state_machine.py — 46 tests pass
- [x] main.py contains order_buffer, stream discovery, routing, process_batch block
- [x] tests/test_order_buffer.py — 5 tests pass
- [x] queries/magic_number_filters.sql — 4 queries present
- [x] tests/test_magic_number_filter.py — 13 tests pass
- [x] schema.sql contains aureus_trades with hypertable and 5 indexes
- [x] All 3 commits verified: 2b6b0f6, 428bc20, f21447d
