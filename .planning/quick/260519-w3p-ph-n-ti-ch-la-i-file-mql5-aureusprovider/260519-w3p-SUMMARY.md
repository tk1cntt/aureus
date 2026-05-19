---
phase: 260519-w3p-ph-n-ti-ch-la-i-file-mql5-aureusprovider
plan: 01
subsystem: mql5-provider
tags: [quick, mql5, provider, pending-order, reconciliation]
key-files:
  modified:
    - D:/Aureus/mql5/AureusProvider_v2.mq5
decisions:
  - Stored pending-order mapping is valid evidence of pending fill when HistoryOrderSelect cannot recover pending order type.
metrics:
  tasks: 3
  completed: 2026-05-19
---

# Quick 260519-w3p Summary

## Kết quả

Fix provider/reconciliation path trong `D:/Aureus/mql5/AureusProvider_v2.mq5` để pending ORDER_FILLED vẫn gửi về gateway khi `HistoryOrderSelect(orderTicket)` không trả được `ORDER_TYPE`, nhưng provider vẫn còn mapping `pending_order_id -> trace_id/cmd_id`.

## Root cause

Commit liên quan pending fill mapping: `5ccf0eb fix(260512-q15): map pending fills to command correlation`.

Cơ chế lỗi hiện tại: `OnTradeTransaction` kiểm tra `HistoryOrderSelect(orderTicket)` rồi suy ra pending fill từ `ORDER_TYPE`. Khi history order type không sẵn sàng/không select được, `orderType = -1`, provider return ở gate `not pending fill` trước khi dùng mapping đã lưu. Kết quả `PopPendingOrderMapping` không chạy, `ORDER_FILLED` không gửi, gateway không nhận `trace_id/cmd_id/pending_order_id` để reconcile journal.

## Fix

Trong `OnTradeTransaction`, lấy `PopPendingOrderMapping(orderTicket, ...)` trước pending-fill gate và coi `hasPendingMapping` là bằng chứng pending fill hợp lệ cùng với `ORDER_TYPE` pending. Log gate thêm `mapped=true/false` để giữ observability.

Không đổi market order path, không đổi SL safety logic gần đây, không đổi backend/database.

## GitNexus

- `npx gitnexus query --repo Aureus "provider reconciliation pending fill ORDER_FILLED"` chạy được nhưng index không chứa symbol MQL5 chi tiết.
- `npx gitnexus context --repo Aureus OnTradeTransaction` không tìm thấy symbol.
- `npx gitnexus impact --repo Aureus --direction upstream OnTradeTransaction` không tìm thấy symbol.
- Fallback impact cấp file: `npx gitnexus impact --repo Aureus --direction upstream AureusProvider_v2.mq5` trả `risk: LOW`, `impactedCount: 0`, `direct: 0`, `processes_affected: 0`.
- `gitnexus detect_changes` không có trong CLI hiện tại (`unknown command 'detect_changes'`).
- Sau commit, `npx gitnexus status` báo index stale. `npx gitnexus analyze /d/Aureus` bị blocker môi trường: `EPERM: operation not permitted, open 'D:\Aureus\AGENTS.md'`.

## Verify

- Preflight root thật: `/d/Aureus`; `D:/Aureus/mql5/AureusProvider_v2.mq5` tồn tại.
- Git history reviewed: `git log --follow --oneline -- mql5/AureusProvider_v2.mq5` gồm `5ccf0eb`, `cb42dee`, `77b088b`, `27ad8ec`, `eb164e8`.
- Diff reviewed từ `5ccf0eb..HEAD` chỉ ra pending fill gate và recent SL safety changes.
- `git diff --check -- mql5/AureusProvider_v2.mq5`: pass.
- Build theo `D:/Aureus/mql5/Build_Rules.md`: `MetaEditor64.exe /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log"`; log báo `Result: 0 errors, 0 warnings`.

## Commit

- `add3910 fix(260519-w3p): preserve pending fill mapping when history order type is unavailable`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] GitNexus symbol-level MQL5 lookup unavailable**
- Found during: Task 2
- Issue: GitNexus CLI did not find `OnTradeTransaction` symbol in indexed graph.
- Fix: Used GitNexus query/context attempts, then fallback file-level impact on `AureusProvider_v2.mq5` before editing.
- Files modified: none
- Commit: n/a

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- Modified file exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`
- Commit exists: `add3910`
- Build log exists: `D:/Aureus/mql5/AureusProvider_v2_compile.log`
