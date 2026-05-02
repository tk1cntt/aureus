---
phase: quick-260501-knj-refactor-strategy-aware-position-managem
plan: 01
subsystem: mt5-provider-position-management
tags: [mql5, mt5, position-management, strategy-profile, anti-lack]
dependency_graph:
  requires: [mql5/AureusProvider_v2.mq5, mql5/CISD_Slope_EA_v6.39_Final.mq5, mql5/Build_Rules.md]
  provides: [strategy-aware-position-management-rule-primitives]
  affects: [ManagePositionProfitBreakEvent, ProcessPositionsByType, ResolveManagementProfile, LogManagementDecision]
tech_stack:
  added: []
  patterns: [primitive-aware-decision-log, profile-scoped-risk-management, cost-aware-sl]
key_files:
  created:
    - .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
decisions:
  - "Giữ profile built-in trong MQL5; không thêm JSON/config/DSL/hot reload."
  - "Giữ provider không có signal flag `g_m30_*`/`g_h1_*`; ghi CHANGED/DEFERRED rõ thay vì port state old EA."
metrics:
  completed_date: 2026-05-01
  tasks_completed: 3
---

# Quick 260501-knj: Refactor Strategy-aware Position Management Summary

## Tóm tắt

Đã hoàn thiện refactor anti-lack cho `D:/Aureus/mql5/AureusProvider_v2.mq5`: decision log có trường `primitive`, `net_profit` dùng commission và swap, toàn bộ quản lý vẫn scoped theo `symbol + magic + direction`, không sửa command path, compile MetaEditor `0 errors, 0 warnings`.

## Thay đổi code chính

- `LogManagementDecision(...)` thêm tham số và log field `primitive=...` để audit trực tiếp P-03/P-16, P-05/P-06, P-07, P-09/P-14, P-08/P-10/P-11/P-15, P-12, P-13/P-15, P-10/P-11/P-12/P-13.
- `ProcessPositionsByType(...)` tính `total_swap` trước risk guard và dùng `net_profit = total_profit - total_commission + total_swap`, nên severe loss, basket recovery, threshold và SL management cùng dựa trên net profit cost-aware.
- Giữ nguyên các command/non-regression function: `ExecuteCloseOrder`, `ExecuteRequestOrders`, `DoBackfillCountForSymbol`, `ProcessSingleCommand` routing `REQUEST_BACKFILL_COUNT`, `BuildPositionsJSON`, `BuildTradeHistoryJSON`.

## GitNexus impact / fallback evidence

### Lệnh impact trước khi sửa code

- `npx gitnexus impact ManagePositionProfitBreakEvent || true`
- `npx gitnexus impact ProcessPositionsByType || true`
- `npx gitnexus impact ResolveManagementProfile || true`
- `npx gitnexus impact LogManagementDecision || true`
- `npx gitnexus impact ManagePositionProfitBreakEvent --repo Aureus || true`
- `npx gitnexus impact ProcessPositionsByType --repo Aureus || true`
- `npx gitnexus impact ResolveManagementProfile --repo Aureus || true`
- `npx gitnexus impact LogManagementDecision --repo Aureus || true`

Kết quả: CLI ban đầu báo nhiều repo index; khi thêm `--repo Aureus`, các target MQL5 đều báo `Target ... not found`. Vì vậy dùng fallback local call graph theo plan.

| Symbol | Direct callers/callees fallback | Blast radius | Risk |
|---|---|---|---|
| `ManagePositionProfitBreakEvent` | Được gọi trong main tick loop; gọi `ProcessPositionsByType(symbol, magic, type, ...)` | Live management cho provider positions thuộc `InpSymbols`, magic khác 0 | High |
| `ProcessPositionsByType` | Gọi resolver/log/trade close/modify/imbalance helpers | Close/modify SL theo từng group | High |
| `ResolveManagementProfile` | Được gọi một lần mỗi group trong `ProcessPositionsByType` | Chọn profile management | Medium |
| `LogManagementDecision` | Được gọi trong HOLD/CLOSE/MOVE_SL/TRAIL_SL | Audit log, không trực tiếp trade | Low |

## GitNexus detect changes / fallback evidence

- Đã chạy: `npx gitnexus detect-changes --repo Aureus || npx gitnexus detect_changes --repo Aureus || true`.
- Kết quả: GitNexus CLI báo `unknown command 'detect-changes'` và `unknown command 'detect_changes'`.
- Fallback đã chạy:
  - `git -C "D:/Aureus" diff --stat -- mql5/AureusProvider_v2.mq5`: chỉ `mql5/AureusProvider_v2.mq5`, 34 dòng thay đổi.
  - Targeted diff command path không thấy thay đổi trên các function bị cấm.
  - Diff name check xác nhận không có database files thay đổi.

## Primitive implementation map P-01..P-20

| Primitive | Mark | Evidence |
|---|---|---|
| P-01 | [x] KEPT | `ManagePositionProfitBreakEvent` dedupe/aggregate theo `symbol + magic + type`, gọi `ProcessPositionsByType(symbol, magic, type, ...)`. |
| P-02 | [x] KEPT | Guard `magic == 0 || FindContextIndex(symbol) < 0`; history cooldown cũng skip magic 0 và unsupported symbol. |
| P-03 | [x] KEPT | `ResolveManagementProfile` parse `magic:profile;...`, trim, skip malformed/empty, unknown về conservative. |
| P-04 | [x] CHANGED | `LogManagementDecision` thêm `primitive=%s`, mọi branch quản lý hiện có truyền primitive IDs. |
| P-05 | [x] CHANGED | `net_profit = total_profit - total_commission + total_swap`. |
| P-06 | [x] KEPT | `severe_risk_guard` close group tickets khi loss vượt ngưỡng. |
| P-07 | [x] KEPT | Basket close chỉ khi `profile == PROFILE_BASKET_ESCAPE && positions_count >= 4 && net_profit > 0`. |
| P-08 | [x] CHANGED | Không có global age close; stale single được HOLD/protect theo profile. |
| P-09 | [x] KEPT | HOLD `profit_below_sl_management_threshold` trước normal SL management. |
| P-10 | [x] KEPT | BUY dùng bullish imbalance `IsImbalanceUp` và `iLow`. |
| P-11 | [x] KEPT | SELL dùng bearish imbalance `IsImbalanceDown` và `iHigh`. |
| P-12 | [x] CHANGED | SL profitability dùng breakeven có `total_commission + total_swap`; log `primitive=P-12`. |
| P-13 | [x] KEPT | Loop từng ticket, đọc `POSITION_TP`, gọi `PositionModify(ticket, proposed_sl_price, tp_for_this_pos)`. |
| P-14 | [x] KEPT | `trend_runner` không có age-only close; branch threshold/HOLD log `P-09/P-14`. |
| P-15 | [x] KEPT | `breakout_time_stop` chỉ khi profile breakout, chọn MOVE_SL hoặc HOLD nếu không profitable. |
| P-16 | [x] KEPT | Unknown magic/profile fallback conservative; fallback log có `P-03/P-16`. |
| P-17 | [x] KEPT | History cooldown helpers scoped `symbol + magic + direction`, không sửa. |
| P-18 | [~] DEFERRED | Old EA signal flags không tồn tại trong provider; xem deferred table. |
| P-19 | [x] KEPT | Targeted diff xác nhận command paths không đổi. |
| P-20 | [~] DEFERRED | Old cycle max/min telemetry chưa port; xem deferred table. |

## Old behavior/rule coverage matrix B-01..B-30

| ID | Final mark | Evidence/rationale |
|---|---|---|
| B-01 | [x] KEPT | BUY/SELL tách bằng `ENUM_POSITION_TYPE type` và `ProcessPositionsByType(... type ...)`. |
| B-02 | [x] KEPT | Provider group thêm `symbol + magic + direction`. |
| B-03 | [x] KEPT | `magic == 0` guard trong position management và history cooldown. |
| B-04 | [x] KEPT | `FindContextIndex(symbol) < 0` skip unsupported symbols. |
| B-05 | [x] KEPT | Aggregate `total_profit`, `total_volume`, `weighted_price_sum`. |
| B-06 | [x] KEPT | `earliest_open_time` aggregate và `age_seconds` tính từ earliest. |
| B-07 | [~] DEFERRED | Cycle max/min profit/pips health old EA không có state tương đương trong provider; không port để tránh stateful side-effect mới. |
| B-08 | [x] CHANGED | Net profit nay include commission và swap: `total_profit - total_commission + total_swap`. |
| B-09 | [x] KEPT | Swap được cộng vào `total_swap` trước breakeven/SL profitability. |
| B-10 | [x] KEPT | Severe loss close all tickets trong scoped group. |
| B-11 | [x] KEPT | Single severe loss dùng half threshold trong cùng guard. |
| B-12 | [x] CHANGED | 4-position profitable basket close chỉ under `basket_escape`, không global. |
| B-13 | [x] CHANGED | Global stale close bị loại; breakout protect dùng MOVE_SL, trend/conservative HOLD/SL management. |
| B-14 | [~] DEFERRED | Old M30/H1 signal flag disable không có provider equivalent; history cooldown giữ phần close cooldown. |
| B-15 | [x] CHANGED | Multi-close 2s trong history cooldown đặt 60m scoped by symbol+magic+direction; không dùng H1 flag. |
| B-16 | [x] CHANGED | Single SL close đặt 30m history cooldown scoped; không có signal flag disable. |
| B-17 | [x] CHANGED | Multi-close đặt 60m cooldown; single TP held>=30m old-specific không port vì provider deal handler không có entry-hold classifier tương đương. |
| B-18 | [x] KEPT | `net_profit <= positions_count * InpBEProfitTarget / 2` HOLD trước normal SL. |
| B-19 | [x] KEPT | BUY candidate từ bullish imbalance low. |
| B-20 | [x] KEPT | SELL candidate từ bearish imbalance high. |
| B-21 | [x] KEPT | Reject SL nếu không vượt breakeven cost-aware. |
| B-22 | [x] KEPT | Loop modify toàn bộ `tickets[]`. |
| B-23 | [x] KEPT | Preserve TP per ticket bằng `POSITION_TP`. |
| B-24 | [x] CHANGED | Structured log có required fields và `primitive`. |
| B-25 | [x] KEPT | Resolver fallback conservative cho unknown/invalid. |
| B-26 | [x] KEPT | Decision logic branch theo profile string, không hard-coded magic ngoài default input string. |
| B-27 | [x] KEPT | Close deal path `ApplyCloseDealToHistoryCooldown` không sửa. |
| B-28 | [x] KEPT | `ExecuteCloseOrder` targeted diff unchanged. |
| B-29 | [x] KEPT | `ExecuteRequestOrders` targeted diff unchanged. |
| B-30 | [x] KEPT | `REQUEST_BACKFILL_COUNT`/`DoBackfillCountForSymbol` targeted diff unchanged. |

## Profile checklists 7.1..7.4

### 7.1 Profile `conservative`

- [x] Unknown magic resolves to `conservative`; evidence: resolver final return.
- [x] Invalid profile name resolves to `conservative`; evidence: unknown profile print + return.
- [x] Manual magic `0` is skipped; evidence: static guard.
- [x] Unsupported symbol is skipped; evidence: static guard.
- [x] Single profitable position older than 30m is not closed only due to age; evidence: no global stale close grep.
- [x] Severe loss can close scoped group with `reason=severe_risk_guard`.
- [x] Below threshold logs HOLD and does not modify SL.
- [x] BUY imbalance profitable SL can TRAIL/MOVE SL.
- [x] SELL imbalance profitable SL can TRAIL/MOVE SL.
- [x] Non-profitable SL after commission/swap logs HOLD.
- [x] Basket recovery close is not enabled except severe risk guard; evidence: basket branch profile-gated.
- [x] Close/history cooldown side effects preserved as scoped cooldown; old signal flags deferred in P-18.
- [x] Command paths are unchanged.

### 7.2 Profile `trend_runner`

- [x] Magic mapped to `trend_runner` selects trend profile via input mapping.
- [x] Single profitable position older than 30m never CLOSE due solely to age.
- [x] Aged winner logs HOLD/TRAIL_SL/MOVE_SL via threshold/imbalance paths, not age close.
- [x] Imbalance trailing remains available when profitable after costs.
- [x] Severe risk guard still closes excessive loss.
- [x] Basket recovery close does not apply because basket branch requires basket profile.
- [x] No hard-coded trend magic branch in decision logic.
- [x] Decision log has `profile=trend_runner` and required audit fields when resolver maps it.
- [x] History cooldown preserved; old signal flags deferred with rationale.

### 7.3 Profile `breakout_protect`

- [x] Magic mapped to `breakout_protect` selects breakout profile.
- [x] Profitable single older than 30m triggers profile-scoped `breakout_time_stop`.
- [x] Protective path first attempts MOVE_SL/tighten to profitable target.
- [x] If MOVE_SL target is not profitable after costs, logs HOLD.
- [x] CLOSE is not used for normal profitable stale single.
- [x] Severe risk guard still closes excessive loss.
- [x] No hard-coded breakout magic branch in decision logic.
- [x] Decision log reason includes `breakout_time_stop_tighten` on successful MOVE_SL.
- [x] History cooldown preserved; old signal flags deferred with rationale.

### 7.4 Profile `basket_escape`

- [x] Magic mapped to `basket_escape` selects basket profile.
- [x] Multi-position group meeting recovery/profit threshold closes all tickets in same group only.
- [x] Close scope remains `symbol + magic + direction` through `tickets[]` group.
- [x] Single profitable stale position is not closed by basket rule.
- [x] Severe risk guard still protects downside.
- [x] If basket threshold not met, profile can still use normal SL protection.
- [x] No hard-coded basket magic branch in decision logic.
- [x] Decision log has `profile=basket_escape`, `action=CLOSE`, `reason=basket_recovery_profit`, `primitive=P-07`.
- [x] History cooldown after basket close preserved through existing deal hook.

## Function-level checklist 8.1..8.6

### 8.1 `ResolveManagementProfile(long magic, bool &fallback_used)`

- [x] Format `magic:profile;magic:profile` documented in input comment.
- [x] Trims pair/magic/profile tokens.
- [x] Skips empty pairs.
- [x] Rejects malformed pairs without crashing.
- [x] Rejects unknown profiles to `conservative`.
- [x] Unknown magic returns `conservative`.
- [x] Sets `fallback_used=false` only for valid explicit match.
- [x] Emits fallback evidence for unknown profile via `PrintFormat`.
- [x] No external file, JSON config, DSL, or hot reload.
- [x] No hard-coded magic branches in decision logic outside default input string.

### 8.2 `LogManagementDecision(...)`

- [x] Emits `symbol`.
- [x] Emits `magic`.
- [x] Emits `direction`.
- [x] Emits `profile`.
- [x] Emits `action`.
- [x] Emits `reason`.
- [x] Emits `positions_count`.
- [x] Emits `net_profit`.
- [x] Emits `age_seconds`.
- [x] Emits `ticket` for per-ticket SL actions.
- [x] Emits `target_sl` for SL actions.
- [x] Every close/hold/modify branch has a log call or non-trade failure print.
- [x] Emits `primitive` field for audit.

### 8.3 `ManagePositionProfitBreakEvent()`

- [x] Iterates MT5 open positions safely.
- [x] Skips ticket `0`.
- [x] Skips unselectable ticket.
- [x] Skips `magic == 0`.
- [x] Skips unsupported symbols via `FindContextIndex`.
- [x] Dedupes processed group by `symbol + magic + direction`.
- [x] Aggregates tickets only for same `symbol + magic + direction`.
- [x] Aggregates `total_profit`.
- [x] Aggregates `total_volume`.
- [x] Aggregates `weighted_price_sum`.
- [x] Aggregates `earliest_open_time`.
- [x] Does not read or write command/backfill state.
- [x] Calls `ProcessPositionsByType(symbol, magic, type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time)`.

### 8.4 `ProcessPositionsByType(...)`

- [x] Handles empty group by return.
- [x] Handles zero volume by return.
- [x] Computes direction string.
- [x] Computes commission by symbol class consistently.
- [x] Computes `net_profit` with commission and swap.
- [x] Computes `age_seconds`.
- [x] Resolves profile once per group.
- [x] Logs fallback when resolver fallback is used.
- [x] Applies severe risk guard before non-critical management.
- [x] Applies basket recovery only under basket profile.
- [x] Does not contain global stale profitable single close.
- [x] Applies trend runner age preservation by absence of age-only close.
- [x] Applies breakout time protect only under breakout profile.
- [x] Applies profit threshold / HOLD logic.
- [x] Finds BUY imbalance SL candidate.
- [x] Finds SELL imbalance SL candidate.
- [x] Computes weighted average open price.
- [x] Computes commission + swap cost-aware breakeven.
- [x] Rejects non-profitable SL target.
- [x] Normalizes SL by symbol digits.
- [x] Modifies all tickets in group.
- [x] Preserves each ticket TP.
- [x] Logs every HOLD/MOVE_SL/TRAIL_SL/CLOSE path.
- [x] Does not change command routing behavior.

### 8.5 History cooldown helpers

- [x] `FindHistoryCooldownIndex` unchanged.
- [x] `EnsureHistoryCooldownState` unchanged.
- [x] `DirectionFromCloseDealType` maps close deal direction unchanged.
- [x] `ApplyCloseDealToHistoryCooldown` still skips manual magic `0`.
- [x] `ApplyCloseDealToHistoryCooldown` still skips unsupported symbols.
- [x] `ApplyCloseDealToHistoryCooldown` still dedupes processed deals.
- [x] `IsHistoryCooldownActive` still scoped by `symbol + magic + direction`.
- [x] Bootstrap still runs in `OnInit` unchanged.

### 8.6 Non-regression functions

- [x] `ExecuteCloseOrder` unchanged by targeted diff.
- [x] `ExecuteRequestOrders` unchanged by targeted diff.
- [x] `DoBackfillCountForSymbol` unchanged by targeted diff.
- [x] `ProcessSingleCommand` routing for `REQUEST_BACKFILL_COUNT` unchanged by targeted diff.
- [x] `BuildPositionsJSON` unchanged by targeted diff.
- [x] `BuildTradeHistoryJSON` unchanged by targeted diff.
- [x] Unsupported symbol guards using `FindContextIndex` unchanged/preserved.

## Scenario verification matrix 9.2

| Scenario | Expected result | Evidence | Pass/Fail |
|---|---|---|---|
| Unknown magic, profitable single, age > 30m | conservative, HOLD/SL, not age close | resolver fallback + no global stale close grep | [x] PASS |
| Invalid profile mapping | fallback conservative | unknown profile print + fallback return | [x] PASS |
| `trend_runner`, profitable single, age > 30m | HOLD/TRAIL_SL, not age close | no trend age close branch | [x] PASS |
| `breakout_protect`, profitable single, age > 30m | MOVE_SL if profitable else HOLD | `breakout_time_stop` + SL profitability guard | [x] PASS |
| `basket_escape`, positions >= configured basket threshold, net_profit > 0 | CLOSE same group only | profile-gated basket close loop over grouped `tickets[]` | [x] PASS |
| Any profile, severe loss | CLOSE severe risk | `severe_risk_guard` before other branches | [x] PASS |
| Profit below threshold | HOLD threshold | `profit_below_sl_management_threshold` | [x] PASS |
| BUY imbalance SL not profitable after costs | HOLD no modify | `sl_target_not_profitable` before modify | [x] PASS |
| SELL imbalance SL not profitable after costs | HOLD no modify | same cost-aware guard | [x] PASS |
| BUY imbalance SL profitable after costs | TRAIL/MOVE each ticket, TP preserved | per-ticket modify loop | [x] PASS |
| SELL imbalance SL profitable after costs | TRAIL/MOVE each ticket, TP preserved | per-ticket modify loop | [x] PASS |
| Unsupported symbol command/position | Ignored/skipped as before | `FindContextIndex` guard + command diff unchanged | [x] PASS |
| Manual magic `0` position | Ignored/skipped | `magic == 0` guard | [x] PASS |
| CLOSE_ORDER command | Existing behavior unchanged | targeted diff | [x] PASS |
| REQUEST_ORDERS command | Existing behavior unchanged | targeted diff | [x] PASS |
| REQUEST_BACKFILL_COUNT command | Existing behavior unchanged | targeted diff | [x] PASS |
| Single SL close history | Cooldown preserved | `ApplyCloseDealToHistoryCooldown` unchanged, `single_sl` 30m | [x] PASS |
| Multi-close history | Cooldown preserved | `multi_close_2s` 60m unchanged | [x] PASS |

## Summary evidence checklist 9.3

- [x] Summary records changed behavior per profile.
- [x] Summary includes compile command and compile result.
- [x] Summary includes static check evidence.
- [x] Summary includes coverage matrix with all old behaviors marked `KEPT / CHANGED / DEFERRED`.
- [x] Summary includes every deferred item rationale.
- [x] Summary states signal cooldown side effects are changed/deferred.
- [x] Summary states cycle risk telemetry is deferred.
- [x] Summary confirms no MQL5 command path regression.
- [x] Summary confirms no database files changed.

## Deferred rationale table

| Item ID | Deferred behavior | Why deferred | Current impact | Safety check | Follow-up owner/plan |
|---|---|---|---|---|---|
| P-18/B-14 | Old `g_m30_*`/`g_h1_*` signal disable flags for profitable multi-position | Provider không có old EA entry flag state; thêm state mới sẽ là architectural behavior change | Entry gating không mirror 1:1 old EA flags; history cooldown vẫn bảo vệ close cooldown scoped | `ApplyCloseDealToHistoryCooldown` unchanged and scoped | Follow-up nếu cần parity entry gating theo strategy profile |
| B-17 partial | Single TP held>=30m H1 flag disable | Provider deal hook không lưu đủ context old EA held-time signal flag; không thêm state mới trong surgical refactor | Multi-close cooldown vẫn 60m; single SL cooldown 30m giữ nguyên | History helper unchanged | Follow-up nếu cần classify TP held-time trong provider |
| P-20/B-07 | Cycle max/min profit/pips health telemetry | Provider hiện không có cycle state old EA; port telemetry có thể làm tăng state live ngoài mục tiêu | Không ảnh hưởng close/SL correctness hiện tại; thiếu observability old health score | Severe risk + scoped logs vẫn có | Follow-up observability/telemetry task nếu cần |

## Compile evidence

- Command: `"/e/Openclaw/MetaTrader5/MetaEditor64.exe" /compile:"D:/Aureus/mql5/AureusProvider_v2.mq5" /log:"D:/Aureus/mql5/AureusProvider_v2_compile.log"`
- Result: `Result: 0 errors, 0 warnings`.
- Ghi chú: log MetaEditor là UTF-16; verification dùng Python đọc log để xác nhận chuỗi result.

## Static checks

- [x] `primitive=` xuất hiện trong `LogManagementDecision` output.
- [x] `P-03/P-16`, `P-05/P-06`, `P-07`, `P-09/P-14`, `P-08/P-10/P-11/P-15`, `P-12`, `P-13/P-15`, `P-10/P-11/P-12/P-13` xuất hiện ở call sites.
- [x] No global stale close: grep không thấy pattern `positions_count == 1` + `1800` + `PositionClose`.
- [x] Command path non-regression: targeted `git diff -U0` không có changed lines chứa `ExecuteCloseOrder`, `ExecuteRequestOrders`, `DoBackfillCountForSymbol`, `REQUEST_BACKFILL_COUNT`, `BuildPositionsJSON`, `BuildTradeHistoryJSON`.
- [x] No hard-coded magic decision branch: decision branch theo profile, magic chỉ dùng resolver/default input mapping.
- [x] No external config/JSON/DSL/hot reload added.
- [x] No database files changed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Critical functionality] Thêm `primitive` audit field vào structured decision log**
- **Found during:** Task 2
- **Issue:** Previous implementation có structured fields nhưng chưa có `primitive` field/helper-equivalent explicit enough for anti-lack evidence.
- **Fix:** Thêm tham số `primitive` vào `LogManagementDecision` và cập nhật mọi management branch.
- **Files modified:** `D:/Aureus/mql5/AureusProvider_v2.mq5`

**2. [Rule 1 - Bug] Net profit chưa cộng swap ở severe/basket/threshold decisions**
- **Found during:** Task 2
- **Issue:** Swap chỉ được tính muộn trong SL breakeven, còn `net_profit` cho severe/basket/threshold dùng profit minus commission.
- **Fix:** Tính `total_swap` trước `net_profit`, dùng `total_profit - total_commission + total_swap` cho toàn bộ decision.
- **Files modified:** `D:/Aureus/mql5/AureusProvider_v2.mq5`

## Threat Flags

Không có threat surface mới. Không thêm endpoint, file access, database schema, external config, JSON/DSL/hot reload. Trust boundary duy nhất được chạm là input profile string hiện hữu và live MT5 position state hiện hữu.

## Known Stubs

Không có stub mới.

## Database Impact

No database files changed. DB E2E không áp dụng vì task chỉ sửa MQL5 provider và summary artifact.

## Self-Check: PASSED

- File code tồn tại: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Summary tồn tại: `D:/Aureus/.planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md`.
- Compile log tồn tại và có `Result: 0 errors, 0 warnings`.
- Final artifact không còn checklist blank marker.
