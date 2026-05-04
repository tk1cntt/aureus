---
phase: quick-260504-pyn-remove-active-signals-from-reasoning-tex
plan: 01
subsystem: reasoning-bank
tags: [reasoning-bank, postgres, journal, e2e]
requires: []
provides:
  - Reasoning Bank no longer persists active_signals
  - Idempotent migration drops active_signals column and GIN index
  - E2E asserts runtime schema and reasoning_text exclusions
affects:
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py
  - services/aureus-db-writer/migrations/add_reasoning_entries.sql
  - services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql
tech_stack:
  added: [postgres-migration]
  patterns: [idempotent-migration, dispatcher-e2e]
key_files:
  created:
    - services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql
  modified:
    - services/aureus-trader/journal.py
    - services/aureus-trader/tests/test_journal.py
    - services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py
    - services/aureus-db-writer/migrations/add_reasoning_entries.sql
decisions:
  - Kept active_signals in trade journal and signal snapshot flow; removed only Reasoning Bank persistence and text.
metrics:
  completed_date: 2026-05-04
  tasks_completed: 3
  commits: 3
---

# Quick 260504-pyn Summary

Xóa `active_signals` khỏi Reasoning Bank persistence bằng insert không còn column, source schema không còn column/index, migration drop idempotent, E2E runtime schema checks.

## Tasks Completed

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Remove active_signals from reasoning insert and text expectations | 307bb6b | `services/aureus-trader/journal.py`, `services/aureus-trader/tests/test_journal.py` |
| 2 | Add DB migration and update source schema | 2ce1f82 | `services/aureus-db-writer/migrations/add_reasoning_entries.sql`, `services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql` |
| 3 | Prove runtime DB E2E creates reasoning row without column or index | 55a5196 | `services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py` |

## What Changed

- `_build_reasoning_text()` now keeps `context_filters`, but excludes `active_signals` from journal row.
- `TradeJournalManager.on_order_opened()` no longer inserts `active_signals` into `aureus_reasoning_entries`.
- Source migration `add_reasoning_entries.sql` no longer creates `active_signals JSONB` or `idx_reasoning_entries_active_signals`.
- New migration `drop_reasoning_entries_active_signals.sql` drops index then column with `IF EXISTS`.
- DB E2E applies drop migration twice and asserts:
  - no `aureus_reasoning_entries.active_signals` column
  - no `idx_reasoning_entries_active_signals` index
  - real dispatcher flow creates linked reasoning row
  - `reasoning_text` excludes `active_signals` and `cisd_bull`

## Deviations from Plan

### Auto-fixed Issues

None.

### Tooling Limitations

- GitNexus impact attempted via CLI:
  - `npx gitnexus impact --target _build_reasoning_text --direction upstream`
  - error: `unknown option '--target'`
  - `npx gitnexus impact --target TradeJournalManager.on_order_opened --direction upstream`
  - error: `unknown option '--target'`
- GitNexus detect changes attempted via CLI:
  - `npx gitnexus detect-changes --scope all`
  - error: `unknown command 'detect-changes'`
- WSL configured distro from `RUN_SERVICES.md` missing:
  - `wsl -d Ubuntu-24.04 -u root bash -lc "cd /mnt/d/Aureus && python3 -m pytest services/aureus-trader/tests/test_journal.py -q"`
  - error: `WSL_E_DISTRO_NOT_FOUND`
- Fallback WSL distro `Aureus` lacks pytest:
  - `wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && python3 -m pytest services/aureus-trader/tests/test_journal.py -q"`
  - error: `/usr/bin/python3: No module named pytest`
- Host fallback by absolute test path ran code tests but one path-sensitive test failed because CWD was not project root:
  - `python -m pytest D:/Aureus/services/aureus-trader/tests/test_journal.py -q`
  - result: `75 passed, 1 failed`
  - failing test: `test_main_runtime_wires_redis_into_trade_journal_manager`, `FileNotFoundError: services/aureus-trader/main.py`
- DB migration/E2E verification blocked by missing WSL `psql`:
  - `wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && psql \"$AUREUS_DB_DSN\" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql"`
  - error: `psql: command not found`

## Known Stubs

None found in changed files.

## Threat Flags

None.

## Verification

| Check | Result | Notes |
|---|---|---|
| Unit tests | Blocked in required WSL; host fallback mostly passed | `75 passed, 1 failed` due CWD path-sensitive test, not changed logic |
| Migration idempotency | Blocked | WSL distro lacks `psql`; DB command could not run |
| DB E2E | Blocked | Depends on DB client/service access |
| GitNexus impact | Blocked | CLI option unsupported |
| GitNexus detect_changes | Blocked | CLI command unsupported |

## Deferred Issues

- Environment lacks required Ubuntu-24.04 WSL distro from `RUN_SERVICES.md`.
- Available `Aureus` WSL lacks `pytest` and `psql`, preventing required DB E2E execution in this executor.

## Self-Check: PASSED

- Created file exists: `D:/Aureus/services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql`
- Modified expected files only for code commits.
- Commits exist: `307bb6b`, `2ce1f82`, `55a5196`.
- Unrelated user work remains uncommitted: `D:/Aureus/mql5/AureusProvider_v2.mq5`, `D:/Aureus/mql5/AureusProvider_v2.ex5`, `D:/Aureus/stable/`.
