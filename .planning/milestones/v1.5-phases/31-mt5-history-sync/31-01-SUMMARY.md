---
phase: 31
plan: "01"
subsystem: mt5-history-sync
tags: [mt5, reconciliation, xpending, trade-history]
dependency:
  requires: ["30-01"]
  provides: ["TRADE-03", "TRADE-04"]
  affects: ["db-writer", "mt5-ea"]
tech-stack:
  added: []
  patterns: [redis-streams, consumer-groups, pub-sub, reconciliation-loop]
key-files:
  created: []
  modified:
    - mql5/AureusProvider.mq5
    - services/aureus-db-writer/main.py
    - services/aureus-db-writer/schema.sql
decisions:
  - "Used asyncio.create_task() for reconciliation loop to run concurrently with main stream consumer"
  - "Configurable interval via HISTORY_SYNC_INTERVAL_SEC env var with 10-300s bounds"
  - "Reconciled trades get status='RECONCILED' and trace_id prefixed with 'reconciled-'"
  - "XPENDING recovery scans all order streams and re-adds unacked messages to buffer"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-07"
---

# Phase 31 Plan 01: MT5 History Sync Summary

**One-liner:** Hybrid MT5 history sync with XPENDING recovery on startup, REQUEST_TRADE_HISTORY EA command handler, and configurable reconciliation loop that auto-fixes missing trades with RECONCILED status and audit logging.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T1 | Add reconciliation log table to schema | `484e1c0` | `services/aureus-db-writer/schema.sql` |
| T2 | Add REQUEST_TRADE_HISTORY handler to MT5 EA | `000a66d` | `mql5/AureusProvider.mq5` |
| T3 | Add XPENDING recovery + reconciliation loop to DB writer | `98bd363` | `services/aureus-db-writer/main.py` |

## Implementation Details

### New EA Command: REQUEST_TRADE_HISTORY

Added to `mql5/AureusProvider.mq5`:

- **`BuildTradeHistoryJSON(fromTime, toTime, filterMagic, filterSymbol)`** — Queries MT5 history via `HistorySelect()` + `HistoryDealGetTicket()`, filters by DEAL_ENTRY_OUT (closed positions), magic number, and symbol. Returns JSON array of trade records with ticket, symbol, direction, prices, volume, profit, timestamps (milliseconds).

- **`ExecuteTradeHistoryRequest(raw)`** — Parses JSON command with from_time, to_time, magic_number, symbol fields. Validates time range, calls BuildTradeHistoryJSON, sends response via TCP socket.

- **Wired into `ProcessIncomingCommands()`** — Detects `"REQUEST_TRADE_HISTORY"` in incoming TCP data before existing REQUEST_BACKFILL checks.

### XPENDING Recovery

Added `check_xpending()` method to DBWriter class:

- Scans Redis for all `aureus:stream:*:orders` streams
- For each stream, ensures consumer group exists, then calls `XPENDING` to find unacknowledged messages
- Fetches each unacked message content, re-adds to `order_buffer`, then ACKs it
- Processes recovered messages immediately via `process_batch()`
- Called on startup in `run()` before main loop

### Reconciliation Loop

Added as background asyncio task via `asyncio.create_task(self.reconciliation_loop())`:

- **Interval:** Configurable via `HISTORY_SYNC_INTERVAL_SEC` env var (10-300s range, default 30s)
- **Cycle:**
  1. Query DB for trades closed in last 5 minutes
  2. Publish `REQUEST_TRADE_HISTORY` command to `aureus:mt5:commands` Redis channel
  3. Subscribe to `aureus:mt5:responses:db-writer` and wait up to 10s for EA response
  4. Compare DB tickets vs MT5 tickets to find missing
  5. Insert missing trades with `status='RECONCILED'`, `entry_type='MARKET'`, trace_id `reconciled-{ticket}-{uuid}`
  6. Log every discrepancy to `aureus_reconciliation_log` with action, source, details JSON

### Schema Changes

New table `aureus_reconciliation_log`:
- Columns: `id`, `run_at`, `action`, `ticket`, `symbol`, `source`, `status`, `details` (JSONB), `created_at`
- Indexes on `run_at DESC`, `action`, `ticket` for efficient audit queries

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:spoofing | mql5/AureusProvider.mq5 | EA sends TRADE_HISTORY JSON over TCP socket — gateway must validate response schema before forwarding to Redis |
| threat_flag:tampering | services/aureus-db-writer/main.py | TRADE_HISTORY responses received via Redis pub/sub `aureus:mt5:responses:db-writer` — validated by checking `type` field equals `TRADE_HISTORY` and parsing JSON schema |

## Known Stubs

None. All functionality is fully wired:
- EA command handler connects to existing TCP socket infrastructure
- Reconciliation loop connects to existing Redis + Postgres connections
- Schema table is created on DB writer startup via existing schema.sql loading

## Verification Results

### Automated Checks
- [x] **Python syntax:** `main.py` parses as valid Python 3.10+ (`ast.parse` passed)
- [x] **Tests:** 66 tests passed, 2 warnings (pre-existing, unrelated to Phase 31 changes)
- [x] **MQ5 function presence:** `BuildTradeHistoryJSON` (2 refs), `ExecuteTradeHistoryRequest` (2 refs), `REQUEST_TRADE_HISTORY` (5 refs)
- [x] **Schema:** `aureus_reconciliation_log` table DDL with all required columns and indexes

### Manual Integration Tests (Not yet run — requires live MT5 + Redis + Postgres)
- [ ] XPENDING Recovery: Stop DB writer while messages pending → restart → verify "Recovered N unacked messages"
- [ ] EA Command Response: Send REQUEST_TRADE_HISTORY → verify EA returns valid JSON trade array
- [ ] Reconciliation Cycle: Delete trade from DB → wait → verify re-inserted with `status='RECONCILED'`
- [ ] Configurable Interval: Set `HISTORY_SYNC_INTERVAL_SEC=15` → verify 15s reconciliation
- [ ] Discrepancy Audit: Query `aureus_reconciliation_log` → verify entries match reconciliation actions

## Self-Check: PASSED

- [x] `mql5/AureusProvider.mq5` exists and modified
- [x] `services/aureus-db-writer/main.py` exists and modified
- [x] `services/aureus-db-writer/schema.sql` exists and modified
- [x] Commits `484e1c0`, `000a66d`, `98bd363` exist in git log
