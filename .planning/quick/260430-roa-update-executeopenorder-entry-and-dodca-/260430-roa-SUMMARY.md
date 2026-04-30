---
phase: quick-260430-roa-update-executeopenorder-entry-and-dodca
plan: 01
subsystem: mql5-provider
tags: [mql5, mt5, order-entry, dca]
dependency_graph:
  requires: [AureusProvider_v2]
  provides: [direction-aware-duplicate-entry-guard, dca-direction-scope-audit]
  affects: [ExecuteOpenOrder, DoDCA, FindDCAMagicForSymbolDirection, CheckDCAEntryConditionFromCISD]
tech_stack:
  added: []
  patterns: [symbol-magic-direction-scoping]
key_files:
  created:
    - D:/Aureus/.planning/quick/260430-roa-update-executeopenorder-entry-and-dodca-/260430-roa-SUMMARY.md
  modified:
    - D:/Aureus/mql5/AureusProvider_v2.mq5
decisions:
  - Giữ nguyên luồng ACK/idempotency/symbol allow-list và chỉ thu hẹp duplicate guard theo direction.
  - Không sửa DoDCA vì source hiện tại đã lọc theo symbol + magic + target POSITION_TYPE.
metrics:
  completed_date: 2026-04-30
  tasks_completed: 3
---

# Quick 260430-roa Summary

Direction-aware duplicate entry guard cho `ExecuteOpenOrder`, đồng thời audit xác nhận DCA vẫn quản lý theo `symbol + magic + direction`.

## Kết quả chính

- `ExecuteOpenOrder` không còn chặn cross-side entry khi cùng `symbol + magic`:
  - Existing BUY position/order chỉ chặn BUY mới.
  - Existing SELL position/order chỉ chặn SELL mới.
- Pending order duplicate guard đã map side rõ ràng:
  - BUY: `ORDER_TYPE_BUY_LIMIT`, `ORDER_TYPE_BUY_STOP`, `ORDER_TYPE_BUY_STOP_LIMIT`.
  - SELL: `ORDER_TYPE_SELL_LIMIT`, `ORDER_TYPE_SELL_STOP`, `ORDER_TYPE_SELL_STOP_LIMIT`.
- Giữ nguyên NACK reason `STRATEGY_ORDER_EXISTS`, command idempotency, allow-list symbol, ACK timing và logic gửi order.
- Audit DCA xác nhận không cần patch thêm:
  - `DoDCA(1, symbol, magic)` lọc `POSITION_TYPE_BUY` trước khi aggregate/open/modify TP.
  - `DoDCA(-1, symbol, magic)` lọc `POSITION_TYPE_SELL` trước khi aggregate/open/modify TP.
  - `FindDCAMagicForSymbolDirection(symbol, POSITION_TYPE_BUY/SELL)` vẫn lookup theo symbol + direction.
  - `CheckDCAEntryConditionFromCISD` vẫn gọi BUY/SELL lookup riêng và `OnTimer` từ quick 260430-rak vẫn duy trì scan theo từng `InpSymbols` context.

## Commits

| Task | Commit | Nội dung |
|---|---|---|
| Task 1 | 50083a1 | `fix(quick-260430-roa): scope duplicate entries by direction` |
| Task 2 | 48811f3 | `chore(quick-260430-roa): audit dca direction scope` |
| Task 3 | Không commit docs theo constraint | Tạo summary và ghi compile verification |

## Verification

- Lệnh compile đã chạy bằng MetaEditor:
  - `E:/Openclaw/MetaTrader5/MetaEditor64.exe /compile:"D:/Aureus/mql5/AureusProvider_v2.mq5" /log:"D:/Aureus/mql5/AureusProvider_v2_compile.log"`
- Kết quả trong `D:/Aureus/mql5/AureusProvider_v2_compile.log`:
  - `Result: 0 errors, 0 warnings`
- Ghi chú: MetaEditor trả exit code `1` dù compile log báo thành công; xem đây là hành vi CLI/Windows của tool, bằng chứng nguồn là compile log.
- `D:/Aureus/mql5/AureusProvider_v2_compile.log` là generated/ignored evidence và không được commit.
- `D:/Aureus/mql5/AureusProvider_v2.ex5` là artifact generated, không commit.

## GitNexus

Không có MCP tool `gitnexus_*` trong toolset của phiên executor này, nên không thể chạy trực tiếp:

- `gitnexus_impact({target: "ExecuteOpenOrder", direction: "upstream"})`
- `gitnexus_impact({target: "DoDCA", direction: "upstream"})`
- `gitnexus_impact({target: "FindDCAMagicForSymbolDirection", direction: "upstream"})`
- `gitnexus_impact({target: "CheckDCAEntryConditionFromCISD", direction: "upstream"})`
- `gitnexus_detect_changes()`

Fallback evidence đã dùng:

- Đọc trực tiếp `D:/Aureus/mql5/AureusProvider_v2.mq5` quanh các symbol liên quan.
- Diff chỉ sửa guard duplicate trong `ExecuteOpenOrder`.
- DCA audit không thay đổi source vì invariant đã đúng trong code hiện tại.
- MetaEditor compile xác nhận 0 errors/0 warnings.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Điều chỉnh cách gọi MetaEditor từ bash**
- **Found during:** Task 1 verification
- **Issue:** Cách quoting `cmd /c ""E:\Openclaw...` bị shell chuyển sai thành lỗi `'ompile:...' is not recognized`.
- **Fix:** Gọi trực tiếp `E:/Openclaw/MetaTrader5/MetaEditor64.exe` với path slash-style từ bash.
- **Files modified:** Không có source file.
- **Commit:** Không áp dụng.

## Known Stubs

Không có stub mới trong file source đã sửa.

## Threat Flags

Không phát sinh network endpoint, auth path, file access pattern hoặc schema/trust-boundary mới ngoài threat model của plan.

## Self-Check: PASSED

- Source modified: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary exists: `D:/Aureus/.planning/quick/260430-roa-update-executeopenorder-entry-and-dodca-/260430-roa-SUMMARY.md`.
- Task commits exist: `50083a1`, `48811f3`.
- Compile evidence: `D:/Aureus/mql5/AureusProvider_v2_compile.log` shows `0 errors, 0 warnings`.
