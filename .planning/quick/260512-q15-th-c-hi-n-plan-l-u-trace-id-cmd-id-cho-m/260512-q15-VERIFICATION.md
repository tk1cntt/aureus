---
phase: 260512-q15-trace-cmd-pending-fill
verified: 2026-05-12T12:15:26Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "MT5 provider compile/runtime smoke"
    expected: "AureusProvider_v2.mq5 compiles in MetaEditor and pending limit fill emits ORDER_FILLED with mapped trace_id/cmd_id when deal history comment is empty"
    why_human: "No MQ5 compiler/runtime available in verifier shell; MQL5 syntax and wiring verified by code inspection only"
---

# Quick 260512-q15: trace/cmd pending fill Verification Report

**Task Goal:** Thực hiện plan lưu trace_id/cmd_id cho MT5 pending limit order, persist mapping pending_order_id -> trace_id/cmd_id, gửi ORDER_FILLED có mapping, và backend journal fallback update bằng pending_order_id/cmd_id khi thiếu trace_id
**Verified:** 2026-05-12T12:15:26Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Khi MT5 nhận pending limit order, provider lưu mapping pending_order_id -> trace_id/cmd_id trong memory. | VERIFIED | `mql5/AureusProvider_v2.mq5` defines `g_pendingOrderIds`, `g_pendingTraceIds`, `g_pendingCmdIds`; `StorePendingOrderMapping((long)result.order, traceId, cmdId, comment, strategyName)` runs before pending `PushOrderOpened`. Mapping bounded by `InpMaxCmdIdHistory`. |
| 2 | Khi pending order khớp, ORDER_FILLED có trace_id/cmd_id lấy từ mapping nếu MT5 comment/history không đủ dữ liệu. | VERIFIED | `OnTradeTransaction` detects pending `DEAL_ENTRY_IN`, calls `PopPendingOrderMapping(orderTicket, ...)`, fills missing `traceId`/comment/strategy, then calls `PushOrderFilled(..., traceId, dealComment, fillTime, mappedCmdId)`. `PushOrderFilled` JSON includes `trace_id` and `cmd_id`. |
| 3 | Journal update được row TRIGGERED thành EXECUTED bằng trace_id, hoặc fallback pending_order_id/cmd_id khi trace_id thiếu. | VERIFIED | `TradeJournalManager.on_order_opened` only rejects when all correlation keys missing, then SQL `WHERE status = 'TRIGGERED'` matches `trace_id`, or when trace missing matches `pending_order_id = $9`, or `cmd_id = $11`; `SET status = 'EXECUTED'`. |
| 4 | DB E2E chứng minh lifecycle pending placed -> filled -> closed và case filled thiếu trace_id vẫn update đúng row. | VERIFIED | `python -m pytest services/aureus-trader/tests/test_journal.py -k "pending or filled or trace_id" -q` passed 8 tests. DB E2E with `AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus python services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py` printed PASS and asserted fallback row `EXECUTED`, `ticket`, `position_id`, `entry_deal_ticket`, `pending_order_id`, `cmd_id`. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `mql5/AureusProvider_v2.mq5` | Provider-side pending order mapping and ORDER_FILLED enrichment | VERIFIED | Exists, substantive. Mapping globals/functions present. Stored on pending order acceptance. Popped on pending fill and passed into ORDER_FILLED payload. Wired through existing command/order flow. |
| `services/aureus-trader/journal.py` | Journal fallback update by pending_order_id/cmd_id when trace_id missing | VERIFIED | Exists, substantive. `on_order_filled` normalizes `position_ticket`; `on_order_opened` accepts pending/cmd fallback keys and SQL updates journal row by fallback predicates. |
| `services/aureus-trader/tests/test_journal.py` | Unit coverage for fallback filled event without trace_id | VERIFIED | Exists, substantive. Tests cover fallback success and no-correlation-key failure. Pytest spot-check passed. |
| `services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py` | Database E2E proof for pending_order_id/cmd_id fallback | VERIFIED | Exists, substantive. Uses asyncpg against PostgreSQL, creates normal and fallback lifecycle, asserts real DB state. E2E spot-check passed with system python. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `mql5/AureusProvider_v2.mq5` | `ORDER_FILLED` payload | `PushOrderFilled` includes mapped `trace_id`/`cmd_id` for `trans.order` | VERIFIED | Manual verification: `PopPendingOrderMapping(orderTicket, ...)` runs before `PushOrderFilled`; `traceId` set from mapped value when empty; `mappedCmdId` passed as final argument; JSON includes both fields. gsd regex missed multiline call. |
| `services/aureus-trader/journal.py` | `aureus_trade_journal` | `on_order_opened` UPDATE WHERE trace_id OR pending_order_id OR cmd_id | VERIFIED | Manual verification: SQL lines include `($8::text IS NOT NULL AND trace_id = $8)`, `pending_order_id = $9`, `cmd_id = $11`, and `status = 'TRIGGERED'`. gsd regex escaped `$` mismatch. |
| `services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py` | PostgreSQL `aureus_trade_journal` | real asyncpg insert/update assertions | VERIFIED | gsd key-link verified; script imports asyncpg, creates pool, asserts DB rows for normal and fallback fill. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `mql5/AureusProvider_v2.mq5` | `traceId`, `cmdId`, `pendingOrderId` | Command JSON -> trade `result.order` -> `StorePendingOrderMapping` arrays -> `OnTradeTransaction` `orderTicket` -> `PopPendingOrderMapping` -> `PushOrderFilled` JSON | Yes | FLOWING |
| `services/aureus-trader/journal.py` | `trace_id`, `pending_order_id`, `cmd_id`, `position_ticket`, `deal_ticket` | Redis/event dict -> `on_order_filled` normalization -> `on_order_opened` parameterized SQL -> `aureus_trade_journal` row | Yes | FLOWING |
| `services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py` | fallback DB row state | asyncpg pool -> real INSERT/UPDATE through `TradeJournalManager` -> SELECT assertions | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Journal unit fallback coverage passes | `cd "D:/Aureus" && python -m pytest services/aureus-trader/tests/test_journal.py -k "pending or filled or trace_id" -q` | `8 passed, 75 deselected in 0.18s` | PASS |
| DB E2E proves normal and fallback lifecycle | `cd "D:/Aureus" && AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus python services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py` | Printed `PASS limit lifecycle DB E2E ...`; fallback row assertions passed. Initial provided command using `./.venv/bin/python` failed because `.venv/bin/python` absent in shell. | PASS |
| MQ5 compile/runtime | MetaEditor/manual MT5 smoke | Not runnable from verifier shell. | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| `QUICK-260512-Q15` | `260512-q15-PLAN.md` | Trace/cmd pending limit order mapping and journal fallback update | SATISFIED | All four must-have truths verified; unit and DB E2E passed. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `services/aureus-trader/journal.py` | 47-188 | `return None` helper returns | Info | Not stub; helper parsing defaults. No goal impact. |
| `mql5/AureusProvider_v2.mq5` | 1274 | `return StringToDouble(...)` matched broad `return` scan | Info | False positive from anti-pattern regex; not stub. |

### Human Verification Required

#### 1. MT5 provider compile/runtime smoke

**Test:** Compile `mql5/AureusProvider_v2.mq5` in MetaEditor and place/fill pending limit order where deal history comment lacks trace metadata.
**Expected:** Provider compiles; accepted pending order stores mapping; filled pending order emits `ORDER_FILLED` with `pending_order_id`, mapped `trace_id`, mapped `cmd_id`, and backend journal row becomes `EXECUTED`.
**Why human:** Verifier shell has no MQ5 compiler/MT5 runtime; code wiring is verified, but platform compile/runtime behavior needs human/tooling outside shell.

### Gaps Summary

No automated goal gaps found. Phase goal achieved by code inspection plus unit and DB E2E checks. Overall status remains `human_needed` because MQ5 compile/runtime cannot be verified in this environment.

---

_Verified: 2026-05-12T12:15:26Z_
_Verifier: Claude (gsd-verifier)_
