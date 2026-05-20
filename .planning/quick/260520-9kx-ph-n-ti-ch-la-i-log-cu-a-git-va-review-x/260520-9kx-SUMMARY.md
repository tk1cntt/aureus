---
phase: quick-260520-9kx
plan: 01
completed: 2026-05-20
commit: 4fe9793
key_files:
  - mql5/AureusProvider_v2.mq5
  - services/aureus-gateway/main.py
  - services/aureus-gateway/tests/test_order_events.py
---

# Quick 260520-9kx Summary

Fix: ORDER_CLOSED giữ lại exact pending-order correlation theo ticket đã được ORDER_OPENED lưu, phát ra trace_id/cmd_id vào payload close. Không thêm fallback theo symbol/time/strategy guess.

## Culprit

Commit gần nhất liên quan: `add3910 fix(260519-w3p): preserve pending fill mapping when history order type is unavailable`.

Hunk culprit: `OnTradeTransaction` chuyển `PopPendingOrderMapping(orderTicket, ...)` lên đầu nhánh `DEAL_ENTRY_IN`, rồi pop mapping khi pending fill đến. Mapping `pending_order_id -> trace_id/cmd_id` bị xóa ở fill. Khi `DEAL_ENTRY_OUT` sau đó gọi `PushOrderClosed(...)`, close path chỉ parse trace từ `DEAL_COMMENT`; runtime cho thấy blank nên ORDER_CLOSED thiếu trace_id/cmd_id.

## Evidence

Git diff inspected:

- `git show add3910 -- mql5/AureusProvider_v2.mq5 services/aureus-signal`
- `git diff 5ccf0eb..9637c912b47367ae45bb1ca90721567f98ac1fad -- mql5/AureusProvider_v2.mq5 services/aureus-signal`

Runtime logs:

- `ORDER_OPENED cmd_id=ord-3c39c210dc56 ticket=1657649733`
- later `Event without cmd_id type=ORDER_CLOSED symbol=BTCUSD ticket=1657649733 trace_id= pending_count=0`
- notifier: `Skip ORDER_CLOSED notification: unresolved strategy context trace_id= ticket=1657649733`

DB evidence:

- `aureus_trade_journal` 24h: 0 rows, 0 closed
- `aureus_trades` 24h: SENT 168
- ticket lookup for failed close tickets returned 0 journal rows, proving notifier DB lookup cannot recover missing provider context.

## Fix

Files:

- `D:/Aureus/mql5/AureusProvider_v2.mq5`
- `D:/Aureus/services/aureus-gateway/main.py`
- `D:/Aureus/services/aureus-gateway/tests/test_order_events.py`

Changes:

- `PushOrderClosed` includes optional `cmdId` and emits `"cmd_id":"..."`.
- `DEAL_ENTRY_IN` now reads pending mapping with `GetPendingOrderMapping(orderTicket, ...)` instead of popping it.
- Pending fill copies same exact correlation to resulting position ticket with `StorePendingOrderMapping(ticket, ...)`.
- `DEAL_ENTRY_OUT` keeps exact close lookup via `PopPendingOrderMapping(ticket, ...)`; no symbol/time/random fallback.
- Gateway `OrderClosedEvent` now declares optional `cmd_id`, so `model_dump_json()` preserves provider payload.
- Gateway focused test asserts ORDER_CLOSED input `cmd_id` remains in published Redis payload.

## GitNexus / Impact

- `gitnexus query --repo Aureus "ORDER_CLOSED cmd_id trace_id pending fill mapping notifier unresolved strategy context"` ran.
- `_resolve_journal_context` impact: HIGH, direct callers `_handle_order_opened`, `_handle_order_closed`, affected notifier flows. Not edited.
- MQL5 symbols `PushOrderClosed`, `PushOrderOpened`, `OnTradeTransaction` not found in GitNexus index. Manual blast radius: provider close payload -> gateway/trader/notifier consumers only.
- Continuation: MCP GitNexus tools were not available in this executor namespace. Fallback impact used source-level call sites. `StorePendingOrderMapping`/`PopPendingOrderMapping`/new `GetPendingOrderMapping` affect only provider pending lifecycle call sites. `OrderClosedEvent` direct caller is `process_message`; downstream Redis/notifier receive additive optional `cmd_id`.
- CLI fallback `npx gitnexus detect-changes` failed: `unknown command 'detect-changes'`. Scoped `git diff`/`git status` used before commit.

## Verification

Passed:

- Git history/diff reviewed before edit.
- Runtime logs reproduced ORDER_OPENED then ORDER_CLOSED without cmd_id/trace_id for same tickets.
- DB evidence confirmed no exact journal row exists for affected tickets.
- Diff contains no symbol/time fallback.
- `python -m pytest "D:/Aureus/services/aureus-gateway/tests/test_order_events.py" -q` passed: 14 passed.
- Gateway preserves ORDER_CLOSED `cmd_id` through validation and `model_dump_json()`.
- Commit created: `0d1a6c5 fix(260520-9kx): preserve close event command correlation`.
- Continuation commit created: `4fe9793 fix(260520-9kx): keep close command correlation exact`.

Blocked / out-of-scope:

- MQL5 compile command from `Build_Rules.md` failed because `E:\Openclaw\MetaTrader5\MetaEditor64.exe` not available from current environment/quoting path; retry via `/mnt/e/Openclaw/MetaTrader5/MetaEditor64.exe` failed with `No such file or directory`.
- Python journal test command ran for context; 80 passed, 3 failed in pre-existing Reasoning Bank tests unrelated to MQL5-only change.
- Live E2E close after rebuild requires MT5 rebuild/deploy outside current environment.

## Deviations from Plan

- Summary created as required but not committed because user constraint says do not commit docs artifacts.
- ROADMAP.md not updated per user constraint.

## Known Stubs

None introduced.

## Threat Flags

None beyond plan threat model. New surface is existing ORDER_CLOSED payload field `cmd_id`, sourced only from exact ticket mapping.
