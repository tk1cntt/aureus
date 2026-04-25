---
phase: quick-260425-vqn-update-file-mql5-aureusprovider-mq5-chi
plan: 01
subsystem: mt5-provider
tags: [mql5, gateway, order-safety, allowlist]
dependency_graph:
  requires: [InpSymbols, FindContextIndex, gateway order commands]
  provides: [gateway order symbol allowlist]
  affects: [ExecuteOpenOrder, ExecuteCloseOrder]
tech_stack:
  added: []
  patterns: [early validation, NACK before side effects]
key_files:
  created: []
  modified:
    - mql5/AureusProvider.mq5
decisions:
  - Used FindContextIndex(symbol) as the source of truth because g_contexts is derived from InpSymbols during OnInit.
  - Used SYMBOL_NOT_ALLOWED for allowlist rejects to make logs/NACK reason explicit.
metrics:
  completed_date: 2026-04-25
  tasks_completed: 3
---

# Quick 260425-vqn Summary: Gateway order symbol allowlist

Provider MT5 hiện chỉ ACK và xử lý gateway OPEN_ORDER/CLOSE_ORDER khi `symbol` nằm trong danh sách cấu hình `InpSymbols`; symbol ngoài allowlist bị NACK trước các side effect giao dịch.

## Tasks Completed

| Task | Status | Commit | Notes |
|------|--------|--------|-------|
| 1. Rà soát impact và edit points | Done | 2fadb8e | GitNexus không index được symbol MQL5; fallback direct review. |
| 2. Enforce InpSymbols allowlist | Done | 2fadb8e | OPEN_ORDER/CLOSE_ORDER đều dùng `FindContextIndex(symbol) < 0` trước ACK/RecordCmdId/order execution. |
| 3. Verify scope and change detection | Done | 2fadb8e | `git diff --check` pass; scope chỉ `mql5/AureusProvider.mq5`; GitNexus detect command unavailable. |

## Changes

- `ExecuteOpenOrder` giữ validation required fields và duplicate check trước allowlist, sau đó reject symbol ngoài `InpSymbols` bằng log rõ `cmd_id`, `symbol`, `SYMBOL_NOT_ALLOWED` và `SendNACK` trước `TerminalInfoInteger`, `SendACK`, `RecordCmdId`, `OrderCheck`, `OrderSend`.
- `ExecuteCloseOrder` bổ sung allowlist gate ngay sau duplicate check, trước `TerminalInfoInteger`, `SendACK`, `RecordCmdId`, `PositionSelectByTicket`, và `OrderSend`.
- Không đổi parsing `InpSymbols`, schema JSON, hoặc luồng allowed-symbol hiện có.

## Verification

- Passed: `git diff --check -- mql5/AureusProvider.mq5`
- Passed: `git diff --stat -- mql5/AureusProvider.mq5` showed only `mql5/AureusProvider.mq5` with 12 changed lines.
- Passed by direct review: allowlist checks appear before `SendACK(cmdId)` and `RecordCmdId(cmdId)` in both order paths.
- Not run: MetaEditor/MetaTrader compiler is not available in repo/CI environment.
- Not required: database E2E, because this task does not touch database/schema/persistence code.

## GitNexus Notes

- Impact checks attempted:
  - `npx gitnexus impact ExecuteOpenOrder --direction upstream --repo Aureus || true`
  - `npx gitnexus impact ExecuteCloseOrder --direction upstream --repo Aureus || true`
- Result: `Target 'ExecuteOpenOrder' not found` and `Target 'ExecuteCloseOrder' not found`; MQL5 symbols appear not indexed.
- Fallback blast radius by direct code review:
  - Direct caller: `ProcessIncomingCommands`
  - Affected process: gateway order command handling for OPEN_ORDER/CLOSE_ORDER
  - Risk level: low, because changes are early reject guards and do not alter allowed-symbol execution flow.
- Pre-commit change detection attempted: `npx gitnexus detect-changes --repo Aureus || true`
- Result: `error: unknown command 'detect-changes'`; scope verified with `git diff --check`, `git diff --stat`, and committed file list.

## Deviations from Plan

None - plan executed as written with documented fallback for unavailable GitNexus MQL5 symbol indexing/detect command.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- Summary created at `D:/Aureus/.planning/quick/260425-vqn-update-file-mql5-aureusprovider-mq5-chi-/260425-vqn-SUMMARY.md`.
- Code commit exists: `2fadb8e`.
- Modified code file exists: `D:/Aureus/.claude/worktrees/agent-a966d3e8/mql5/AureusProvider.mq5`.
