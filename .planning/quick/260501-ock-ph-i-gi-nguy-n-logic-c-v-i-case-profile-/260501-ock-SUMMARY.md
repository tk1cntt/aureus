---
phase: quick-260501-ock-preserve-legacy-unmapped-profile
plan: 01
subsystem: mt5-provider-position-management
tags: [mql5, mt5, legacy-profile, unmapped-magic]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5, mql5/CISD_Slope_EA_v6.39_Final.mq5, mql5/Build_Rules.md]
  provides: [legacy-default-old-management-path]
  affects: [ResolveManagementProfile, ProcessPositionsByType, LogManagementDecision]
tech_stack:
  added: []
  patterns: [legacy-profile-fallback, scoped-position-management, cost-aware-sl]
key_files:
  created:
    - .planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - "Unmapped magic dùng PROFILE_LEGACY thay vì fallback conservative để giữ behavior cũ."
  - "Explicit invalid profile mapping vẫn fallback conservative theo safety behavior hiện hữu."
metrics:
  completed_date: 2026-05-01
  tasks_completed: 3
---

# Quick 260501-ock: Preserve Legacy Unmapped Profile Summary

## Tóm tắt

Đã sửa `D:/Aureus/mql5/AureusProvider_v2.mq5` để magic chưa map trong `InpMagicManagementProfiles` đi vào `profile=legacy`, không còn silent dùng `conservative`. Explicit `magic:conservative` vẫn trả `conservative`, các profile `trend_runner`, `breakout_protect`, `basket_escape` giữ strategy-aware behavior hiện tại.

## Commit code

- `9daeb2b` — `fix(quick-260501-ock): preserve legacy unmapped profile management`

## GitNexus impact / fallback evidence

Đã chạy trước khi sửa code:

- `npx gitnexus impact ResolveManagementProfile --repo Aureus || true` → `Target 'ResolveManagementProfile' not found`
- `npx gitnexus impact ProcessPositionsByType --repo Aureus || true` → `Target 'ProcessPositionsByType' not found`
- `npx gitnexus impact LogManagementDecision --repo Aureus || true` → `Target 'LogManagementDecision' not found`

Fallback blast radius:

| Symbol | Blast radius fallback | Risk |
|---|---|---|
| `ResolveManagementProfile` | Chọn profile quản lý cho từng group `symbol + magic + direction` trong `ProcessPositionsByType` | Medium |
| `ProcessPositionsByType` | Live close/modify SL cho các vị thế provider thuộc `InpSymbols`, magic khác 0 | High |
| `LogManagementDecision` | Audit log quyết định; không trực tiếp trade nhưng cần phân biệt `profile=legacy` | Low |

## Thay đổi chính

- Thêm `PROFILE_LEGACY = "legacy"`.
- `ResolveManagementProfile(...)`:
  - Explicit mapping hợp lệ như `123:conservative` trả đúng `conservative`, `fallback_used=false`.
  - Explicit mapping hợp lệ sang `trend_runner`, `breakout_protect`, `basket_escape` giữ nguyên.
  - Explicit mapping có profile không hỗ trợ vẫn fallback `conservative` như behavior an toàn hiện hữu.
  - Unmapped magic trả `legacy`, `fallback_used=true`, nên decision log có `profile=legacy` với reason `profile_fallback`.
- `ProcessPositionsByType(...)`:
  - Severe risk guard vẫn chạy trước cho mọi profile với `reason=severe_risk_guard`.
  - `profile=legacy` close scoped group khi `positions_count == 4 && net_profit > 0` với `reason=legacy_basket_recovery_profit`.
  - `profile=legacy` close scoped single profitable stale khi `positions_count == 1 && age_seconds > 1800 && net_profit > 0` với `reason=legacy_stale_profitable_single`.
  - Profit threshold, BUY/SELL imbalance SL, cost-aware breakeven gồm commission/swap, normalize SL, modify từng ticket và preserve `POSITION_TP` giữ nguyên.

## Behavior matrix

| Scenario | Expected | Evidence | Pass |
|---|---|---|---|
| Unmapped magic | `profile=legacy`, không dùng `conservative` | resolver final return `PROFILE_LEGACY`; fallback log qua `LogManagementDecision(... profile, ..., "profile_fallback")` | [x] |
| Explicit `magic:conservative` | `profile=conservative`, strategy-aware conservative hiện hữu | explicit valid branch `fallback_used=false; return profile` | [x] |
| Explicit `trend_runner` | Giữ trend runner behavior hiện hữu | không đổi branch profile-aware | [x] |
| Explicit `breakout_protect` | Giữ breakout protective MOVE_SL/HOLD | không đổi `breakout_time_stop` branch | [x] |
| Explicit `basket_escape` | Giữ basket escape `positions_count >= 4` | không đổi branch `PROFILE_BASKET_ESCAPE` | [x] |
| Legacy severe loss | Close group trước các rule khác | `severe_risk_guard` trước legacy basket/stale branch | [x] |
| Legacy single severe loss | Close group khi single half-threshold | cùng guard `net_profit < -max_loss_amount / 2 && positions_count == 1` | [x] |
| Legacy 4-position net positive | Close scoped tickets | branch `PROFILE_LEGACY && positions_count == 4 && net_profit > 0` | [x] |
| Legacy stale profitable single >1800s | Close scoped ticket | branch `PROFILE_LEGACY && positions_count == 1 && age_seconds > 1800 && net_profit > 0` | [x] |
| Legacy SL management | Threshold + BUY/SELL imbalance + cost-aware + preserve TP | existing `PositionModify(tickets[i], proposed_sl_price, tp_for_this_pos)` unchanged | [x] |

## Static verification

- Resolver static checks: passed.
- Legacy behavior static checks: passed.
- No external JSON/config/DSL/hot reload added.
- No hard-coded magic decision branch added.
- Unsupported symbol behavior preserved: `FindContextIndex(symbol) < 0` guard still present and untouched.
- Manual magic `0` skip preserved.

## Compile evidence

- Command attempted from plan via `cmd /c` had quoting issue in bash shell; retried using executable Unix path per `Build_Rules.md` target:
  - `"/e/Openclaw/MetaTrader5/MetaEditor64.exe" /compile:"D:/Aureus/mql5/AureusProvider_v2.mq5" /log:"D:/Aureus/mql5/AureusProvider_v2_compile.log"`
- Result: `0 errors, 0 warnings`.
- Compile log path: `D:/Aureus/mql5/AureusProvider_v2_compile.log`.

## GitNexus detect changes / fallback evidence

- `npx gitnexus detect-changes --repo Aureus` → `unknown command 'detect-changes'`.
- `npx gitnexus detect_changes --repo Aureus` → `unknown command 'detect_changes'`.
- Fallback checks:
  - `git diff --stat -- mql5/AureusProvider_v2.mq5` trước commit: chỉ `mql5/AureusProvider_v2.mq5`, 18 insertions, 1 deletion.
  - Targeted diff chỉ chạm `PROFILE_*`, `ResolveManagementProfile`, và `ProcessPositionsByType` legacy branches.
  - Không có thay đổi `ExecuteCloseOrder`, `ExecuteRequestOrders`, `DoBackfillCountForSymbol`, `BuildPositionsJSON`, `BuildTradeHistoryJSON`, command strings `CLOSE_ORDER`, `REQUEST_ORDERS`, `REQUEST_BACKFILL_COUNT`.

## Non-regression command/history/unsupported-symbol checks

| Area | Result |
|---|---|
| Unsupported symbol behavior | Preserved; guard `FindContextIndex(symbol) < 0` untouched |
| History cooldown scope | Preserved; no history cooldown helper changed |
| `CLOSE_ORDER` / `ExecuteCloseOrder` | Unchanged |
| `REQUEST_ORDERS` / `ExecuteRequestOrders` | Unchanged |
| `REQUEST_BACKFILL_COUNT` / `DoBackfillCountForSymbol` | Unchanged |
| `BuildPositionsJSON` | Unchanged |
| `BuildTradeHistoryJSON` | Unchanged |
| Database | No database files changed. DB E2E không áp dụng vì chỉ sửa MQL5 provider. |

## Deviations from Plan

None - plan executed as written. Fallback evidence used only because GitNexus CLI did not index/support required MQL5 symbol/change commands.

## Known Stubs

Không có stub mới.

## Threat Flags

Không có threat surface mới. Chỉ sửa resolver input string hiện hữu và live position management branch hiện hữu; không thêm endpoint, file access, database schema, external config, JSON/DSL/hot reload.

## Self-Check: PASSED

- Code file exists: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary exists: `D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md`.
- Compile log exists and contains `0 errors, 0 warnings`.
- Code commit exists: `9daeb2b`.
