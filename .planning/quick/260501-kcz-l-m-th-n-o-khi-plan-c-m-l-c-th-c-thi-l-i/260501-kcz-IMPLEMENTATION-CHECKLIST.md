# Quick 260501-kcz — Anti-Lack Implementation Checklist

## 0. Mục tiêu và phạm vi

Artifact này là checklist bắt buộc cho lần refactor/implementation strategy-aware position management tiếp theo. Mục tiêu không phải viết code ngay, mà là tạo một cơ chế chống thiếu việc: executor sau chỉ được claim complete khi từng behavior cũ đã được kiểm kê, map sang primitive, map sang profile, có verify check, và không còn ô trống không giải thích.

Phạm vi hiện tại:

- Chỉ sửa tài liệu/checklist.
- Không sửa `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Không sửa `D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5`.
- Không sửa database files.

Nguồn bắt buộc phải đối chiếu khi implement sau:

- Current provider: `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Old/reference EA: `D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5`.
- Previous summary: `D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-SUMMARY.md`.

## 1. Diagnosis: vì sao execution trước vẫn có thể bị thiếu một phần

Quick `260501-i1p` đã implement được strategy-aware position management cấp cao, nhưng vẫn có rủi ro partial execution vì checklist ban đầu chưa buộc executor chứng minh coverage ở cấp behavior/rule.

Các điểm thiếu của quy trình trước:

1. **Plan mô tả intent, chưa khóa coverage từng rule cũ**
   - Yêu cầu “strategy-aware” đúng hướng nhưng chưa bắt buộc map từng rule trong old EA sang `KEPT / CHANGED / DEFERRED`.
   - Rủi ro: implement profile mới nhưng bỏ sót behavior phụ như cooldown sau close, signal disable, DCA/basket escape, hoặc cost-aware SL.

2. **Profile chưa được compose từ primitive rõ ràng**
   - `conservative`, `trend_runner`, `breakout_protect`, `basket_escape` có intent nhưng chưa có danh sách primitive bắt buộc.
   - Rủi ro: code có `if profile == ...` nhưng không đủ rule bảo vệ.

3. **Verification trước thiên về static presence**
   - Đã check compile, resolver, log fields, không còn global stale close.
   - Chưa đủ pass/fail scenario cho từng old behavior và từng profile.

4. **Không có bảng chống “blank item”**
   - Không có chỗ bắt buộc ghi rationale cho item không làm.
   - Rủi ro: summary ghi “completed” trong khi một rule bị bỏ qua im lặng.

5. **Old EA có side-effect stateful không hiển nhiên**
   - `ManagePositionByHistory()` và các flag `g_m30_*`, `g_h1_*` không chỉ là logging; chúng thay đổi khả năng vào lệnh sau close.
   - Rủi ro: provider không có cùng flag nên executor có thể bỏ qua mà không ghi `CHANGED/DEFERRED`.

## 2. Anti-lack execution rule cho executor sau

Trước khi sửa code, executor sau phải copy checklist này vào summary/verification và đánh dấu từng item.

Quy tắc bắt buộc:

- Không được để item `[ ]` trống trong final evidence.
- Nếu item hoàn thành: đổi thành `[x]` và ghi evidence ngắn.
- Nếu item không làm: đổi thành `[~] DEFERRED:` và ghi rationale + impact.
- Nếu item không áp dụng: đổi thành `[~] N/A:` và ghi vì sao không áp dụng.
- Nếu không thể verify: đổi thành `[!] BLOCKED:` và dừng claim complete.

Mẫu ghi item:

```markdown
- [x] Behavior X — evidence: file/function/log/scenario.
- [~] DEFERRED: Behavior Y — rationale: provider không có signal flags tương đương; impact: không làm mất command path; follow-up: plan ABC.
- [!] BLOCKED: Behavior Z — thiếu compile environment; không claim complete.
```

## 3. Required decomposition of existing management logic

Executor sau phải phân rã logic quản lý vị thế theo 5 lớp sau trước khi code:

1. **Scope/grouping**
   - Position nào thuộc cùng group.
   - Không trộn symbol.
   - Không trộn magic/strategy.
   - Không trộn BUY và SELL.
   - Không quản lý manual magic `0`.

2. **State aggregation**
   - `positions_count`.
   - `total_profit`.
   - `total_volume`.
   - `weighted_price_sum`.
   - `weighted_avg_open_price`.
   - `earliest_open_time`.
   - `total_commission`.
   - `total_swap`.
   - `net_profit`.
   - Pips max/min nếu đưa lại health/risk scoring từ old EA.

3. **Risk/exit guards**
   - Severe loss close.
   - Single-position severe loss close.
   - Basket/DCA recovery close.
   - Stale sideway single-position behavior.
   - High-risk 4-position behavior.

4. **Protective management**
   - Profit threshold trước khi quản lý SL.
   - BUY imbalance SL candidate.
   - SELL imbalance SL candidate.
   - Cost-aware breakeven gồm commission/swap.
   - Preserve TP khi modify SL.
   - MOVE_SL/TRAIL_SL theo profile.

5. **Post-action side effects**
   - Structured decision logs.
   - History cooldown sau close theo `symbol + magic + direction`.
   - Signal cooldown/disable từ old EA nếu có equivalent.
   - Không regress command paths: `CLOSE_ORDER`, `REQUEST_ORDERS`, `REQUEST_BACKFILL_COUNT`.

## 4. Old behavior inventory từ reference management code

### 4.1 Old EA `ManagePositionProfitBreakEvent()` inventory

- Group BUY và SELL riêng trong chart symbol `_Symbol`.
- Tính tổng profit/volume/weighted price riêng BUY/SELL.
- Theo dõi earliest open time.
- Theo dõi cycle state: `g_total_profit_max`, `g_total_profit_min`, `g_total_pips_max`, `g_total_pips_min`, `g_total_pips_now`.
- Tính health/risk score từ pips/profit/time.
- Gọi `ProcessPositionsByType()` riêng cho BUY và SELL.

### 4.2 Old EA `ProcessPositionsByType()` inventory

- Tính commission theo symbol class.
- Tính `net_profit = total_profit - total_commission`.
- Close all nếu:
  - `net_profit < -max_loss_amount`.
  - `net_profit < -max_loss_amount / 2 && positions_count == 1`.
  - `positions_count == 4 && net_profit > 0`.
- Sau close BUY/SELL, disable H1 signal tương ứng.
- Nếu `net_profit > 0 && positions_count == 1 && age > 1800`, close stale sideway position.
- Nếu profitable multi-position, disable M30/H1 signal và shift processed bar time.
- Chỉ manage SL khi `net_profit > positions_count * InpProfitTarget / 2`.
- BUY SL candidate từ bullish imbalance.
- SELL SL candidate từ bearish imbalance.
- Tính breakeven có commission + swap.
- Chỉ modify SL nếu proposed SL profitable sau costs.
- Loop modify từng ticket trong group.
- Preserve TP khi modify SL.

### 4.3 Old EA `ManagePositionByHistory()` inventory

- Lấy latest completed trades trong ngày.
- Nếu không còn position đang mở:
  - Single SL close: cooldown M30/H1 khoảng 30 phút, disable buy/sell signal flags.
  - Single TP giữ >= 30 phút hoặc multi-close: cooldown H1 khoảng 60 phút, disable H1 buy/sell signal flags.
- Đây là side-effect vào entry gating, không chỉ là report.

### 4.4 Current provider inventory liên quan

- Có `InpMagicManagementProfiles`.
- Có built-in profiles: `conservative`, `trend_runner`, `breakout_protect`, `basket_escape`.
- Có resolver `ResolveManagementProfile(long magic, bool &fallback_used)`.
- Có structured log `LogManagementDecision(...)`.
- `ManagePositionProfitBreakEvent()` group theo `symbol + magic + direction`.
- `ProcessPositionsByType(...)` xử lý group scoped.
- Có history cooldown helpers theo `symbol + magic + direction`.
- Có command paths cần giữ nguyên: close/order report/backfill.

## 5. Rule primitive list

| Primitive ID | Primitive | Description | Required data | Action vocabulary | Verification hook |
|---|---|---|---|---|---|
| P-01 | Group identity | Group by `symbol + magic + direction`; never mix strategies or BUY/SELL. | symbol, magic, position type, tickets | HOLD | Static scan + runtime decision log |
| P-02 | Manual/unsupported skip | Skip magic `0` and symbols outside `InpSymbols`. | magic, symbol, context index | HOLD | Static scan skip guards |
| P-03 | Profile resolver | Parse `magic:profile;magic:profile`; invalid/unknown -> `conservative`. | magic, mapping string | HOLD | Resolver checklist + fallback log |
| P-04 | Audit decision log | Every decision emits required fields. | symbol, magic, direction, profile, action, reason, counts/profit/age | HOLD/MOVE_SL/TRAIL_SL/CLOSE | Static scan call sites |
| P-05 | Net profit cost model | Commission/swap cost must be included where rule requires profitability. | profit, volume, commission, swap | HOLD | Scenario/static |
| P-06 | Severe loss guard | Close group on severe loss to prevent runaway drawdown. | net_profit, threshold, positions_count | CLOSE | Scenario/static |
| P-07 | Basket recovery escape | Multi-position basket closes only when scoped profile and threshold allow. | positions_count, net_profit, profile | CLOSE | Basket scenario |
| P-08 | Stale single policy | Old global stale close must become profile-scoped behavior, never silent global close. | age, net_profit, positions_count, profile | HOLD/MOVE_SL/CLOSE | Static scan no global close |
| P-09 | Profit threshold | SL management only after threshold unless profile-specific protective path. | net_profit, positions_count, target | HOLD | Below-threshold scenario |
| P-10 | BUY imbalance SL | BUY uses bullish imbalance low as candidate. | symbol, timeframe, current SL | TRAIL_SL | Static scan + scenario |
| P-11 | SELL imbalance SL | SELL uses bearish imbalance high as candidate. | symbol, timeframe, current SL | TRAIL_SL | Static scan + scenario |
| P-12 | Cost-aware profitable SL | Proposed SL must beat breakeven including costs before modify. | avg price, volume, commission, swap, tick value | HOLD/TRAIL_SL/MOVE_SL | Cost scenario |
| P-13 | Preserve TP on SL modify | Per-ticket TP must be read and reused. | ticket, current TP | MOVE_SL/TRAIL_SL | Static scan `PositionModify(ticket, sl, tp)` |
| P-14 | Trend runner preservation | Trend profile must not close winners by age alone. | profile, age, profit | HOLD/TRAIL_SL | Trend scenario |
| P-15 | Breakout time protect | Breakout profile tightens/protects aged winner instead of global close. | profile, age, profit | MOVE_SL/HOLD | Breakout scenario |
| P-16 | Conservative default | Unknown magic/profile uses safe behavior and closes only severe risk. | resolver fallback | HOLD/MOVE_SL/TRAIL_SL/CLOSE severe | Conservative scenario |
| P-17 | History cooldown preservation | Close deals still produce cooldown by symbol+magic+direction. | history deal, magic, symbol, direction | cooldown state | Static/function checklist |
| P-18 | Signal cooldown side effect | Old `g_m30_*`/`g_h1_*` entry gating must be KEPT/CHANGED/DEFERRED explicitly. | close reason, count, signal flags | cooldown/flag update | Coverage matrix rationale |
| P-19 | Command path non-regression | CLOSE_ORDER, REQUEST_ORDERS, REQUEST_BACKFILL_COUNT unchanged unless justified. | command router/functions | N/A | Diff/static checklist |
| P-20 | Cycle risk telemetry | Old max/min profit/pips health state either ported or explicitly deferred. | pips/profit history | HOLD/CLOSE optional | Coverage matrix rationale |

## 6. Old behavior/rule coverage matrix

Executor sau phải đánh dấu từng row trong cột “Final mark” trước khi claim complete.

| ID | Old behavior/rule | Source reference | Primitive(s) | Conservative | Trend runner | Breakout protect | Basket escape | Required disposition | Verification checklist | Final mark |
|---|---|---|---|---|---|---|---|---|---|---|
| B-01 | Group BUY/SELL riêng | Old `ManagePositionProfitBreakEvent` | P-01 | KEPT | KEPT | KEPT | KEPT | Must keep semantic | `ProcessPositionsByType(symbol, magic, type, ...)` | [ ] |
| B-02 | Provider group thêm symbol+magic | Current provider improvement | P-01 | KEPT | KEPT | KEPT | KEPT | Must keep | Static scan group identity | [ ] |
| B-03 | Skip manual magic=0 | Provider current behavior | P-02 | KEPT | KEPT | KEPT | KEPT | Must keep | `magic == 0` guard | [ ] |
| B-04 | Skip unsupported symbols | Provider current behavior | P-02/P-19 | KEPT | KEPT | KEPT | KEPT | Must keep | `FindContextIndex(symbol) < 0` guard | [ ] |
| B-05 | Aggregate total profit/volume/weighted price | Old + provider | P-01/P-05 | KEPT | KEPT | KEPT | KEPT | Must keep | Static aggregation scan | [ ] |
| B-06 | Earliest open time | Old + provider | P-08/P-15 | KEPT | KEPT | KEPT | KEPT | Must keep | Age calculation uses earliest time | [ ] |
| B-07 | Cycle max/min profit/pips health tracking | Old EA only | P-20 | DEFER/CHANGE allowed | DEFER/CHANGE allowed | DEFER/CHANGE allowed | DEFER/CHANGE allowed | Must not omit; rationale required | Summary explains port/defer | [ ] |
| B-08 | Commission-adjusted net profit | Old + provider | P-05/P-06/P-12 | KEPT | KEPT | KEPT | KEPT | Must keep | `net_profit` includes commission | [ ] |
| B-09 | Swap included in SL profitability | Old + provider | P-12 | KEPT | KEPT | KEPT | KEPT | Must keep | total_swap loop before breakeven | [ ] |
| B-10 | Severe loss closes all group positions | Old | P-06 | KEPT | KEPT | KEPT | KEPT | Must keep unless risk model changed explicitly | Scenario severe loss closes scoped group | [ ] |
| B-11 | Single severe loss closes without DCA | Old | P-06 | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | Must map threshold | Scenario single half threshold | [ ] |
| B-12 | 4-position profitable basket closes all | Old | P-07 | CHANGED: not default | CHANGED: not default | CHANGED: not default | KEPT/CHANGED scoped | Must be profile-scoped, not global | Basket profile scenario | [ ] |
| B-13 | Single profitable >30m global close | Old | P-08/P-14/P-15 | CHANGED: no global close | CHANGED: preserve | CHANGED: protect SL | CHANGED: no single basket close | Must change; no silent global close | Static scan no global stale close | [ ] |
| B-14 | Multi-position profitable disables M30/H1 signals | Old | P-18 | DEFER/CHANGE | DEFER/CHANGE | DEFER/CHANGE | DEFER/CHANGE | Must write rationale if provider lacks flags | Summary has rationale | [ ] |
| B-15 | 3+ positions extend H1 cooldown to 60m | Old | P-18/P-17 | DEFER/CHANGE | DEFER/CHANGE | DEFER/CHANGE | DEFER/CHANGE | Must map to cooldown or defer | History/summary evidence | [ ] |
| B-16 | Single SL close disables M30/H1 for 30m | Old `ManagePositionByHistory` | P-17/P-18 | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | Must preserve via history cooldown or defer | History cooldown scenario/static | [ ] |
| B-17 | Single TP held >=30m or multi-close disables H1 60m | Old `ManagePositionByHistory` | P-17/P-18 | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | Must map/defer | History cooldown scenario/static | [ ] |
| B-18 | Profit threshold before SL management | Old | P-09 | KEPT/CHANGED named input | KEPT/CHANGED | KEPT/CHANGED | KEPT/CHANGED | Must map threshold input | Below-threshold HOLD log | [ ] |
| B-19 | BUY imbalance SL candidate | Old | P-10 | KEPT | KEPT | KEPT | KEPT | Must keep | BUY branch candidate > current SL | [ ] |
| B-20 | SELL imbalance SL candidate | Old | P-11 | KEPT | KEPT | KEPT | KEPT | Must keep | SELL branch candidate < current SL or SL=0 | [ ] |
| B-21 | Proposed SL must be profitable after commission/swap | Old | P-12 | KEPT | KEPT | KEPT | KEPT | Must keep | Non-profitable SL logs HOLD | [ ] |
| B-22 | Modify SL for every ticket in group | Old | P-13 | KEPT | KEPT | KEPT | KEPT | Must keep | Loop over all tickets | [ ] |
| B-23 | Preserve TP per ticket when moving SL | Old | P-13 | KEPT | KEPT | KEPT | KEPT | Must keep | Reads `POSITION_TP` per ticket | [ ] |
| B-24 | Structured/auditable logs | New requirement replacing ad hoc logs | P-04 | CHANGED | CHANGED | CHANGED | CHANGED | Must implement | All branches call log | [ ] |
| B-25 | Resolver fallback to conservative | New requirement | P-03/P-16 | KEPT | N/A | N/A | N/A | Must implement | Unknown magic/profile scenario | [ ] |
| B-26 | No hard-coded magic in decision logic | New requirement | P-03 | KEPT | KEPT | KEPT | KEPT | Must implement | Static scan no `magic == strategy` branch | [ ] |
| B-27 | Close path still creates history cooldown via deals | Provider current behavior | P-17 | KEPT | KEPT | KEPT | KEPT | Must keep | Helpers unchanged/evidence | [ ] |
| B-28 | CLOSE_ORDER command unchanged | Provider command path | P-19 | KEPT | KEPT | KEPT | KEPT | Must keep | Diff/static no unintended change | [ ] |
| B-29 | REQUEST_ORDERS unchanged | Provider command path | P-19 | KEPT | KEPT | KEPT | KEPT | Must keep | Diff/static no unintended change | [ ] |
| B-30 | REQUEST_BACKFILL_COUNT unchanged | Provider command path | P-19 | KEPT | KEPT | KEPT | KEPT | Must keep | Diff/static no unintended change | [ ] |

## 7. Per-profile complete strategy checklist

### 7.1 Profile `conservative`

Purpose: safe default cho unknown/invalid magic; tránh surprise close.

Required primitives: P-01, P-02, P-03, P-04, P-05, P-06, P-08, P-09, P-10, P-11, P-12, P-13, P-16, P-17, P-19.

Checklist bắt buộc:

- [ ] Unknown magic resolves to `conservative`; evidence: resolver scenario/log.
- [ ] Invalid profile name resolves to `conservative`; evidence: fallback log.
- [ ] Manual magic `0` is skipped; evidence: static guard.
- [ ] Unsupported symbol is skipped; evidence: static guard.
- [ ] Single profitable position older than 30m is not closed only due to age.
- [ ] Severe loss can close scoped group with `reason=severe_risk_guard`.
- [ ] Below threshold logs HOLD and does not modify SL.
- [ ] BUY imbalance profitable SL can TRAIL/MOVE SL.
- [ ] SELL imbalance profitable SL can TRAIL/MOVE SL.
- [ ] Non-profitable SL after commission/swap logs HOLD.
- [ ] Basket recovery close is not enabled except severe risk guard.
- [ ] Close/history cooldown side effects are preserved or deferred with rationale.
- [ ] Command paths are unchanged.

### 7.2 Profile `trend_runner`

Purpose: giữ winner chạy theo trend; không cắt lệnh thắng chỉ vì age.

Required primitives: P-01, P-02, P-03, P-04, P-05, P-06, P-09, P-10, P-11, P-12, P-13, P-14, P-17, P-19.

Checklist bắt buộc:

- [ ] Magic mapped to `trend_runner` selects trend profile.
- [ ] Single profitable position older than 30m never CLOSE due solely to age.
- [ ] Aged winner logs HOLD/TRAIL_SL/MOVE_SL with trend-safe reason.
- [ ] Imbalance trailing remains available when profitable after costs.
- [ ] Severe risk guard still closes excessive loss.
- [ ] Basket recovery close does not apply unless explicitly justified.
- [ ] No hard-coded trend magic branch in decision logic.
- [ ] Decision log has `profile=trend_runner` and all required audit fields.
- [ ] History cooldown behavior is preserved or deferred with rationale.

### 7.3 Profile `breakout_protect`

Purpose: bảo vệ breakout entry khi giữ quá lâu; ưu tiên tighten SL thay vì hard close.

Required primitives: P-01, P-02, P-03, P-04, P-05, P-06, P-08, P-09, P-10, P-11, P-12, P-13, P-15, P-17, P-19.

Checklist bắt buộc:

- [ ] Magic mapped to `breakout_protect` selects breakout profile.
- [ ] Profitable single older than 30m triggers profile-scoped protective path.
- [ ] Protective path first attempts MOVE_SL/tighten to profitable target.
- [ ] If MOVE_SL target is not profitable after costs, logs HOLD instead of unsafe modify.
- [ ] CLOSE is not used for normal profitable stale single unless explicitly specified and justified.
- [ ] Severe risk guard still closes excessive loss.
- [ ] No hard-coded breakout magic branch in decision logic.
- [ ] Decision log has `profile=breakout_protect` and reason such as `breakout_time_stop_tighten`.
- [ ] History cooldown behavior is preserved or deferred with rationale.

### 7.4 Profile `basket_escape`

Purpose: thoát DCA/basket cycle khi group recover; close đúng group, không close lan.

Required primitives: P-01, P-02, P-03, P-04, P-05, P-06, P-07, P-09, P-10, P-11, P-12, P-13, P-17, P-19.

Checklist bắt buộc:

- [ ] Magic mapped to `basket_escape` selects basket profile.
- [ ] Multi-position group meeting recovery/profit threshold closes all tickets in same group only.
- [ ] Close scope remains `symbol + magic + direction`.
- [ ] Single profitable stale position is not closed by basket rule.
- [ ] Severe risk guard still protects downside.
- [ ] If basket threshold not met, profile can still use normal SL protection.
- [ ] No hard-coded basket magic branch in decision logic.
- [ ] Decision log has `profile=basket_escape`, `action=CLOSE`, and reason such as `basket_recovery_profit`.
- [ ] History cooldown after basket close is preserved or explicitly deferred with rationale.

## 8. Function-level implementation checklist for future refactor

### 8.1 `ResolveManagementProfile(long magic, bool &fallback_used)`

- [ ] Input mapping format documented: `magic:profile;magic:profile`.
- [ ] Trims whitespace around pair, magic, and profile.
- [ ] Skips empty pairs.
- [ ] Rejects malformed pairs without crashing.
- [ ] Rejects unknown profiles to `conservative`.
- [ ] Unknown magic returns `conservative`.
- [ ] Sets `fallback_used=false` only for valid explicit match.
- [ ] Emits or enables fallback evidence for unknown profile.
- [ ] No external file, JSON config, DSL, or hot reload.
- [ ] No hard-coded magic branches in decision logic outside default input string.

### 8.2 `LogManagementDecision(...)`

- [ ] Emits `symbol`.
- [ ] Emits `magic`.
- [ ] Emits `direction`.
- [ ] Emits `profile`.
- [ ] Emits `action`.
- [ ] Emits `reason`.
- [ ] Emits `positions_count`.
- [ ] Emits `net_profit`.
- [ ] Emits `age_seconds`.
- [ ] Emits `ticket` for per-ticket SL actions.
- [ ] Emits `target_sl` for SL actions.
- [ ] Every close/hold/modify branch has a log call or documented reason why not.

### 8.3 `ManagePositionProfitBreakEvent()`

- [ ] Iterates MT5 open positions safely.
- [ ] Skips ticket `0`.
- [ ] Skips unselectable ticket.
- [ ] Skips `magic == 0`.
- [ ] Skips symbols outside `InpSymbols` / `FindContextIndex`.
- [ ] Dedupes processed group by `symbol + magic + direction`.
- [ ] Aggregates tickets only for same `symbol + magic + direction`.
- [ ] Aggregates `total_profit`.
- [ ] Aggregates `total_volume`.
- [ ] Aggregates `weighted_price_sum`.
- [ ] Aggregates `earliest_open_time`.
- [ ] Does not read or write unrelated command/backfill state.
- [ ] Calls `ProcessPositionsByType(symbol, magic, type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time)`.

### 8.4 `ProcessPositionsByType(...)`

- [ ] Handles empty group by return.
- [ ] Handles zero volume by return.
- [ ] Computes direction string.
- [ ] Computes commission by symbol class consistently.
- [ ] Computes `net_profit`.
- [ ] Computes `age_seconds`.
- [ ] Resolves profile once per group.
- [ ] Logs fallback when resolver fallback is used.
- [ ] Applies severe risk guard before non-critical management.
- [ ] Applies basket recovery only under basket profile.
- [ ] Does not contain global stale profitable single close.
- [ ] Applies trend runner age preservation.
- [ ] Applies breakout time protect only under breakout profile.
- [ ] Applies profit threshold / HOLD logic.
- [ ] Finds BUY imbalance SL candidate.
- [ ] Finds SELL imbalance SL candidate.
- [ ] Computes weighted average open price.
- [ ] Computes commission + swap cost-aware breakeven.
- [ ] Rejects non-profitable SL target.
- [ ] Normalizes SL by symbol digits.
- [ ] Modifies all tickets in group.
- [ ] Preserves each ticket TP.
- [ ] Logs every HOLD/MOVE_SL/TRAIL_SL/CLOSE path.
- [ ] Does not change command routing behavior.

### 8.5 History cooldown helpers

- [ ] `FindHistoryCooldownIndex` unchanged or justified.
- [ ] `EnsureHistoryCooldownState` unchanged or justified.
- [ ] `DirectionFromCloseDealType` maps close deal direction correctly.
- [ ] `ApplyCloseDealToHistoryCooldown` still skips manual magic `0`.
- [ ] `ApplyCloseDealToHistoryCooldown` still skips unsupported symbols.
- [ ] `ApplyCloseDealToHistoryCooldown` still dedupes processed deals.
- [ ] `IsHistoryCooldownActive` still scoped by `symbol + magic + direction`.
- [ ] Bootstrap still runs in `OnInit` if required.

### 8.6 Non-regression functions

These functions must not be modified unless explicitly listed in summary with rationale:

- [ ] `ExecuteCloseOrder`.
- [ ] `ExecuteRequestOrders`.
- [ ] `DoBackfillCountForSymbol`.
- [ ] `ProcessSingleCommand` routing for `REQUEST_BACKFILL_COUNT`.
- [ ] `BuildPositionsJSON` unless audit fields require change.
- [ ] `BuildTradeHistoryJSON` unless cooldown/report evidence requires change.
- [ ] Unsupported symbol guards using `FindContextIndex`.

## 9. Verification checklist

### 9.1 Static verification

- [ ] Compile log reports `Result: 0 errors, 0 warnings`.
- [ ] `InpMagicManagementProfiles` exists.
- [ ] Built-in profiles are exactly: `conservative`, `trend_runner`, `breakout_protect`, `basket_escape`.
- [ ] No external profile config file reader.
- [ ] No JSON/DSL/hot-reload for profile rules.
- [ ] No hard-coded magic branches in decision logic.
- [ ] No global `net_profit > 0 && positions_count == 1 && age > 1800 -> close` behavior.
- [ ] All decision actions log required fields.
- [ ] Diff confirms command/backfill/history cooldown paths are unchanged or explicitly justified.
- [ ] Diff confirms no database files changed.

### 9.2 Scenario verification matrix

| Scenario | Expected result | Evidence required | Pass/Fail |
|---|---|---|---|
| Unknown magic, profitable single, age > 30m | `profile=conservative`, HOLD or SL management, not CLOSE by age | log/static | [ ] |
| Invalid profile mapping | fallback to conservative | fallback log | [ ] |
| `trend_runner`, profitable single, age > 30m | HOLD/TRAIL_SL, not CLOSE by age | log/static | [ ] |
| `breakout_protect`, profitable single, age > 30m | MOVE_SL/tighten if profitable after costs; otherwise HOLD | log/static | [ ] |
| `basket_escape`, positions >= configured basket threshold, net_profit > 0 | CLOSE all tickets in same symbol+magic+direction group only | log/static | [ ] |
| Any profile, severe loss | CLOSE with `reason=severe_risk_guard` | log/static | [ ] |
| Profit below threshold | HOLD with threshold reason | log/static | [ ] |
| BUY imbalance SL not profitable after costs | HOLD, no modify | log/static | [ ] |
| SELL imbalance SL not profitable after costs | HOLD, no modify | log/static | [ ] |
| BUY imbalance SL profitable after costs | TRAIL_SL/MOVE_SL for each ticket, TP preserved | log/static | [ ] |
| SELL imbalance SL profitable after costs | TRAIL_SL/MOVE_SL for each ticket, TP preserved | log/static | [ ] |
| Unsupported symbol command/position | Ignored/skipped as before | diff/static | [ ] |
| Manual magic `0` position | Ignored/skipped | diff/static | [ ] |
| CLOSE_ORDER command | Existing close behavior unchanged | diff/static | [ ] |
| REQUEST_ORDERS command | Existing report behavior unchanged | diff/static | [ ] |
| REQUEST_BACKFILL_COUNT command | Existing count backfill behavior unchanged | diff/static | [ ] |
| Single SL close history | Cooldown preserved or deferred with rationale | log/static/summary | [ ] |
| Multi-close history | Cooldown preserved or deferred with rationale | log/static/summary | [ ] |

### 9.3 Summary evidence checklist

- [ ] Summary records changed behavior per profile.
- [ ] Summary includes compile command and compile result.
- [ ] Summary includes static check evidence.
- [ ] Summary includes coverage matrix with all old behaviors marked `KEPT / CHANGED / DEFERRED`.
- [ ] Summary includes every deferred item rationale.
- [ ] Summary states whether signal cooldown side effects are kept, changed, or deferred.
- [ ] Summary states whether cycle risk telemetry is kept, changed, or deferred.
- [ ] Summary confirms no MQL5 command path regression.
- [ ] Summary confirms no database files changed.

## 10. Deferred rationale table template

Executor sau must fill this table for every `[~] DEFERRED` item.

| Item ID | Deferred behavior | Why deferred | Current impact | Safety check | Follow-up owner/plan |
|---|---|---|---|---|---|
| Example | B-14 signal flags | Provider không có `g_m30_*`/`g_h1_*` entry flags equivalent | Không áp dụng trực tiếp nếu gateway strategy gating xử lý cooldown | History cooldown vẫn scoped by symbol+magic+direction | Create follow-up if strategy entry gating needs parity |

If no deferred items exist, write: `No deferred items`.

## 11. Anti-lack gate

Implementation is **not complete** unless all conditions below are true:

1. Every row in **Old behavior/rule coverage matrix** has `Final mark` checked or explicitly deferred with rationale.
2. Every `CHANGED` row names affected profile(s) and why the change is intentional.
3. Every `DEFERRED` row has a row in **Deferred rationale table template** or equivalent summary table.
4. Every profile checklist item is checked or explicitly deferred with rationale.
5. Every function-level checklist item is checked or explicitly deferred with rationale.
6. Every scenario verification row is checked or explicitly marked not runnable with rationale.
7. Signal cooldown side effects from old EA are not omitted silently.
8. Cycle risk telemetry from old EA is not omitted silently.
9. Command path non-regression is verified.
10. No database files are changed unless a separate DB task explicitly requires it and runs DB E2E.
11. No MQL5 source change is claimed complete without compile evidence.
12. No checklist item remains blank in final summary.

If any item remains unchecked without rationale, executor must stop and report:

```text
INCOMPLETE — anti-lack gate failed
```

The executor must not claim “complete” until the blank/deferred item is resolved.
