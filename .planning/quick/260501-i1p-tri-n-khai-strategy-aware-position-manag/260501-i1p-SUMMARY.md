---
phase: quick-260501-i1p-tri-n-khai-strategy-aware-position-manag
plan: 01
subsystem: mt5-provider-position-management
tags: [mql5, mt5, position-management, strategy-profile]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5, mql5/Build_Rules.md]
  provides: [strategy-aware-position-management]
  affects: [ManagePositionProfitBreakEvent, ProcessPositionsByType]
tech_stack:
  added: []
  patterns: [built-in-profile-resolver, conservative-fallback, audit-decision-log]
key_files:
  created:
    - .planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
    - .planning/STATE.md
decisions:
  - "Giữ profile built-in trong MQL5, mapping magic qua input string, không thêm JSON/config/DSL/hot reload."
metrics:
  completed_date: 2026-05-01
  tasks_completed: 3
---

# Quick 260501-i1p: Strategy-aware Position Management Summary

## Tóm tắt

Đã chuyển quản lý vị thế trong `D:/Aureus/mql5/AureusProvider_v2.mq5` từ rule global sang profile theo `magic`, giữ group identity `symbol + magic + direction`, dùng default `conservative` khi không match mapping.

## Thay đổi chính

- Thêm input `InpMagicManagementProfiles = "607000:breakout_protect;2603000:trend_runner;1391000:basket_escape"`.
- Thêm đúng 4 profile built-in: `conservative`, `trend_runner`, `breakout_protect`, `basket_escape`.
- Thêm resolver `ResolveManagementProfile()` parse `magic:profile`, trim token, reject profile lạ về `conservative`.
- Thay rule close global `single profitable age > 1800` bằng decision theo profile:
  - `trend_runner`: không close single profitable chỉ vì quá 30 phút; ưu tiên HOLD/TRAIL_SL.
  - `breakout_protect`: time-stop chỉ scoped profile, ưu tiên MOVE_SL trước close.
  - `basket_escape`: close basket khi group nhiều vị thế recover/profit.
  - `conservative`: HOLD/MOVE_SL/TRAIL_SL; CLOSE chỉ còn qua severe risk guard.
- Decision log thống nhất qua `LogManagementDecision()` với fields: `symbol`, `magic`, `direction`, `profile`, `action`, `reason`, `positions_count`, `net_profit`, `age_seconds`, và `ticket/target_sl` khi có.

## Bằng chứng GitNexus / fallback

- Đã cố chạy GitNexus CLI impact/detect changes qua `npx gitnexus ...`; CLI không trả output khả dụng trong môi trường này.
- Fallback evidence từ local call graph trong file:
  - `ManagePositionProfitBreakEvent()` group scan theo `symbol + magic + direction`.
  - `ManagePositionProfitBreakEvent()` gọi `ProcessPositionsByType(symbol, magic, type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time)`.
  - `ProcessPositionsByType()` là symbol chính được chỉnh để resolve profile và ra decision.
- Diff review trước commit chỉ stage `mql5/AureusProvider_v2.mq5`.

## Bằng chứng compile

- Command thực tế đã chạy theo Build_Rules, dùng MetaEditor64:
  - `"/e/Openclaw/MetaTrader5/MetaEditor64.exe" /compile:"D:/Aureus/mql5/AureusProvider_v2.mq5" /log:"D:/Aureus/mql5/AureusProvider_v2_compile.log"`
- Log compile `D:/Aureus/mql5/AureusProvider_v2_compile.log` báo: `Result: 0 errors, 0 warnings`.
- Lưu ý: process trả exit code 1 dù log MetaEditor ghi compile thành công 0 errors/0 warnings.

## Static checks

- Có `InpMagicManagementProfiles` và example mapping theo plan.
- Profile built-in tồn tại: `PROFILE_CONSERVATIVE`, `PROFILE_TREND_RUNNER`, `PROFILE_BREAKOUT_PROTECT`, `PROFILE_BASKET_ESCAPE`.
- Không thêm external config/JSON/DSL/hot reload.
- Không còn block close global `net_profit > 0 && positions_count == 1 && TimeCurrent() - earliest_open_time > 1800`.
- Logic decision trong `ProcessPositionsByType()` dùng `profile`, không branch hard-coded theo magic.
- Các path ngoài scope không sửa có chủ ý: unsupported symbol behavior, history cooldown helpers, `ExecuteCloseOrder`, `ExecuteRequestOrders`, `DoBackfillCountForSymbol`, `REQUEST_BACKFILL_COUNT`.

## Deviations from Plan

### Auto-fixed Issues

Không có deviation chức năng ngoài plan.

### Tooling deviations

- `cmd /c` quoting trên bash/Windows làm command bị parse sai lần đầu; đã chạy trực tiếp MetaEditor64 bằng path `/e/Openclaw/...` và xác nhận log 0 errors/0 warnings.
- GitNexus MCP tool không có sẵn trong toolset hiện tại; dùng fallback CLI/diff/static evidence như plan cho phép.

## Threat Flags

Không có threat surface mới ngoài trust boundary đã nêu trong plan: input parameter parser và provider trade operations.

## Known Stubs

Không có stub mới.

## Database Impact

Không đụng database-related files; DB E2E không áp dụng.

## Commits

- `d3f52e9`: `feat(quick-260501-i1p): implement strategy-aware position management`

## Self-Check: PASSED

- File code tồn tại: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary tồn tại: `D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-SUMMARY.md`.
- Commit code tồn tại: `d3f52e9`.
