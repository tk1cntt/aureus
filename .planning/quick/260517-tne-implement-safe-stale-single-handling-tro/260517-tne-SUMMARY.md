---
phase: 260517-tne-implement-safe-stale-single-handling-tro
plan: 01
subsystem: mql5-position-management
tags: [quick, mql5, legacy-position-management, stale-single]
key-files:
  created:
    - .planning/quick/260517-tne-implement-safe-stale-single-handling-tro/260517-tne-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - GitNexus không index symbol MQL5 ProcessLegacyPositionsByType; dùng fallback blast radius từ report/source trước khi sửa.
  - Profitable stale legacy single không còn market close; giữ nếu đạt InpBEProfitTarget hoặc move SL về weighted breakeven nếu chưa protective.
metrics:
  completed_date: 2026-05-17
  tasks_completed: 3
  source_files_modified: 1
---

# Quick 260517-tne Summary

Sửa legacy stale single handling để không close market lệnh single đang lời tốt; thay bằng HOLD khi đạt `InpBEProfitTarget` hoặc `MovePositionsSL` về weighted breakeven khi SL chưa protective.

## Tasks Completed

| Task | Kết quả | Verification |
|---|---|---|
| Task 1: Run GitNexus gate and inspect target branch | `npx gitnexus impact ProcessLegacyPositionsByType --direction upstream --repo Aureus` trả `Target 'ProcessLegacyPositionsByType' not found`; đã chạy `npx gitnexus analyze` rồi retry vẫn not found. Dùng fallback blast radius trước khi sửa. | passed |
| Task 2: Replace stale profitable single close with safe hold or breakeven SL | Chỉ sửa `ProcessLegacyPositionsByType`. Giữ `severe_risk_guard` và `legacy_basket_recovery_profit`. Xóa close reason `legacy_stale_profitable_single` trong branch. | Python static assertion passed |
| Task 3: Build and scope-verify MQL5 change | Build bằng MetaEditor fallback qua PowerShell sau khi `cmd /c` quoting lỗi; compile log 0 errors, 0 warnings. GitNexus detect-changes CLI không có command; dùng `gitnexus query`/status + git diff scope. | passed |

## Blast Radius

GitNexus impact:

```text
{
  "error": "Target 'ProcessLegacyPositionsByType' not found"
}
```

Sau `npx gitnexus analyze`, retry vẫn:

```text
{
  "error": "Target 'ProcessLegacyPositionsByType' not found"
}
```

Fallback blast radius:

| Mục | Kết quả |
|---|---|
| Direct caller | `ProcessPositionsByType` |
| Upstream flow | `ManagePositionProfitBreakEvent -> ProcessPositionsByType -> ProcessLegacyPositionsByType` |
| Downstream changed path | stale single profitable path không còn gọi `ClosePositionTickets(reason="legacy_stale_profitable_single")` |
| Retained close paths | `severe_risk_guard`, `legacy_basket_recovery_profit` |
| Risk level | Medium, vì đổi runtime close behavior cho legacy stale single lời dương |

## Implementation Notes

- `net_profit >= InpBEProfitTarget`: log `HOLD` với reason `legacy_stale_profit_target_reached`, return.
- `0 < net_profit < InpBEProfitTarget`: đọc current SL từ `PositionSelectByTicket(tickets[0])`.
- BUY protective khi `current_sl >= weighted_avg_open_price`.
- SELL protective khi `current_sl <= weighted_avg_open_price && current_sl > 0`.
- Nếu SL already protective: log `HOLD` với reason `legacy_stale_single_sl_already_protective`, return.
- Nếu chưa protective: gọi `MovePositionsSL(... PROFILE_LEGACY ..., weighted_avg_open_price, "MOVE_SL", "legacy_stale_single_breakeven_protect", "P-08")`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MetaEditor cmd quoting failed under bash**
- **Found during:** Task 3
- **Issue:** `cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:..."` bị shell làm mất `/c`, lỗi `'ompile:...' is not recognized`.
- **Fix:** Đọc `D:/Aureus/RUN_SERVICES.md` theo `CLAUDE.md`, giữ đúng MetaEditor path nhưng chạy qua `powershell.exe -NoProfile -Command "& 'E:\Openclaw\MetaTrader5\MetaEditor64.exe' ..."`.
- **Files modified:** none
- **Commit:** 77b088b

**2. [Rule 3 - Blocking] `npx gitnexus detect-changes --repo Aureus` không tồn tại trong CLI hiện tại**
- **Found during:** Task 3
- **Issue:** CLI trả `error: unknown command 'detect-changes'`.
- **Fix:** Dùng `npx gitnexus status`, `npx gitnexus query ... --repo Aureus`, và `git diff -- mql5/AureusProvider_v2.mq5` để xác nhận scope MQL5 duy nhất. GitNexus vẫn không index MQL5 symbol.
- **Files modified:** none
- **Commit:** 77b088b

## Verification

- Static assertion: passed.
- Build command used:

```powershell
powershell.exe -NoProfile -Command "& 'E:\Openclaw\MetaTrader5\MetaEditor64.exe' /compile:'D:\Aureus\mql5\AureusProvider_v2.mq5' /log:'D:\Aureus\mql5\AureusProvider_v2_compile.log'"
```

- Compile result: `Result: 0 errors, 0 warnings, 3234 msec elapsed`.
- GitNexus status before analyze: stale (`Indexed commit: f499402`, current `fc44ef5`).
- `npx gitnexus analyze`: success, then impact still target not found.
- DB E2E: not run; no database code or schema touched.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path, file access pattern, schema change, or new trust boundary.

## Self-Check: PASSED

- Code file exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary exists: `D:/Aureus/.planning/quick/260517-tne-implement-safe-stale-single-handling-tro/260517-tne-SUMMARY.md`.
- Commit exists: `77b088b`.
- Modified source scope: `mql5/AureusProvider_v2.mq5` only for code commit.
