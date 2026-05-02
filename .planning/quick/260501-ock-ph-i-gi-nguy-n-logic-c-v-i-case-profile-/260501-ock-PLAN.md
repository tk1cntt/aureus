---
phase: quick-260501-ock-preserve-legacy-unmapped-profile
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - D:/Aureus/mql5/AureusProvider_v2.mq5
  - D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md
autonomous: true
requirements:
  - QUICK-260501-OCK
must_haves:
  truths:
    - "Magic chưa map trong InpMagicManagementProfiles chạy legacy/default-old path, không chạy fallback conservative nếu làm mất behavior cũ."
    - "Magic map explicit `magic:conservative` vẫn chạy đúng conservative profile mới."
    - "Legacy/default-old path giữ các rule cũ: severe loss guard, single severe loss guard, 4-position basket net positive close, stale profitable single close sau >1800s, profit threshold, BUY/SELL imbalance SL, profitability có commission/swap nếu hiện tại đã có, và preserve TP."
    - "Decision log phân biệt rõ `profile=legacy` hoặc tương đương với reason/primitive cho legacy path; explicit conservative log vẫn là `profile=conservative`."
    - "Không thay đổi unsupported symbol behavior, history cooldown scope, CLOSE_ORDER, REQUEST_ORDERS, REQUEST_BACKFILL_COUNT."
    - "MetaEditor compile `0 errors, 0 warnings`."
  artifacts:
    - path: "D:/Aureus/mql5/AureusProvider_v2.mq5"
      provides: "Provider position management resolver + legacy/default-old path cho unmapped magic"
      contains: "PROFILE_LEGACY"
    - path: "D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md"
      provides: "GSD evidence: impact/fallback, compile, static checks, non-regression, behavior matrix"
      contains: "Result: 0 errors, 0 warnings"
  key_links:
    - from: "D:/Aureus/mql5/AureusProvider_v2.mq5::ResolveManagementProfile"
      to: "D:/Aureus/mql5/AureusProvider_v2.mq5::ProcessPositionsByType"
      via: "resolver returns explicit legacy/default-old state for unmapped magic and conservative only for explicit mapping/invalid conservative-equivalent cases"
      pattern: "PROFILE_LEGACY|legacy"
    - from: "D:/Aureus/mql5/AureusProvider_v2.mq5::ProcessPositionsByType"
      to: "D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5::ProcessPositionsByType"
      via: "legacy branch mirrors old global management behavior within existing provider symbol+magic+direction scope"
      pattern: "positions_count == 4.*net_profit > 0|age_seconds > 1800"
    - from: "D:/Aureus/mql5/AureusProvider_v2.mq5::LogManagementDecision"
      to: "runtime MT5 Experts log"
      via: "profile/reason/primitive fields identify legacy fallback decisions"
      pattern: "profile=%s.*reason=%s.*primitive=%s"
---

<objective>
Sửa quick bug trong `D:/Aureus/mql5/AureusProvider_v2.mq5` để magic/profile chưa được mapping không còn rơi vào `conservative` làm thay đổi behavior cũ. Unmapped magic phải chạy legacy/default-old management path tương đương logic global cũ trước khi thêm strategy profile mapping, trong khi magic được map explicit vẫn tiếp tục dùng strategy-aware profiles.

Purpose: Bảo toàn behavior live cho các strategy/magic chưa kịp mapping sau refactor `260501-knj`, tránh silent behavior regression.
Output: MQL5 provider đã sửa, compile MetaEditor sạch, và summary evidence tiếng Việt.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md
@D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5
@D:/Aureus/mql5/Build_Rules.md

<interfaces>
Các symbol chính cần xử lý trong `D:/Aureus/mql5/AureusProvider_v2.mq5`:

```mql5
const string PROFILE_CONSERVATIVE     = "conservative";
const string PROFILE_TREND_RUNNER     = "trend_runner";
const string PROFILE_BREAKOUT_PROTECT = "breakout_protect";
const string PROFILE_BASKET_ESCAPE    = "basket_escape";

bool IsKnownManagementProfile(string profile)
string ResolveManagementProfile(long magic, bool &fallback_used)
void LogManagementDecision(string symbol, long magic, string direction, string profile, string action, string reason, int positions_count, double net_profit, int age_seconds, string primitive, ulong ticket = 0, double target_sl = 0)
void ProcessPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
void ManagePositionProfitBreakEvent()
```

Old/reference behavior trong `D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5::ProcessPositionsByType` cần preserve cho unmapped magic trong provider scope hiện tại (`symbol + magic + direction`):

```mql5
if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount/2 && positions_count == 1) || (positions_count == 4 && net_profit > 0)) { close all tickets; return; }
if(net_profit > 0 && positions_count == 1 && TimeCurrent() - earliest_open_time > 1800) { close all tickets; }
if(positions_count > 0 && net_profit > positions_count * InpProfitTarget / 2) { find BUY/SELL imbalance SL; require breakeven after commission/swap; PositionModify(ticket, proposed_sl_price, tp_for_this_pos); }
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Tách resolver explicit profile khỏi legacy fallback cho unmapped magic</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - Unmapped magic không được return `conservative`; phải return `legacy`/`default_old` hoặc state tương đương và set fallback/log reason phù hợp.
    - Explicit mapping `123:conservative` phải return `conservative` với `fallback_used=false`.
    - Explicit mapping sang `trend_runner`, `breakout_protect`, `basket_escape` giữ nguyên.
    - Malformed pair vẫn bị skip an toàn; unknown profile name phải không biến thành unmapped legacy nếu magic đã explicit match với profile sai. Giữ cách an toàn hiện hữu hoặc ghi rõ rationale trong summary, nhưng phải phân biệt được case unmapped magic với explicit conservative.
  </behavior>
  <action>Trước khi sửa symbol, chạy GitNexus impact theo project rule: `npx gitnexus impact ResolveManagementProfile --repo Aureus || true`, `npx gitnexus impact ProcessPositionsByType --repo Aureus || true`, `npx gitnexus impact LogManagementDecision --repo Aureus || true`; nếu GitNexus không thấy MQL5 symbol như quick `260501-knj`, ghi fallback blast radius trong summary. Sau đó sửa surgical trong provider: thêm constant `PROFILE_LEGACY` hoặc tên tương đương; cập nhật `IsKnownManagementProfile` nếu cần; sửa `ResolveManagementProfile` để unmapped magic trả legacy/default-old chứ không trả conservative. Không thêm JSON/config/DSL/hot reload. Không sửa unsupported symbol guard, history cooldown helpers, CLOSE_ORDER, REQUEST_ORDERS, REQUEST_BACKFILL_COUNT.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p=Path('D:/Aureus/mql5/AureusProvider_v2.mq5')
s=p.read_text(encoding='utf-8', errors='ignore')
assert 'PROFILE_LEGACY' in s or 'legacy' in s.lower() or 'default_old' in s.lower()
assert 'PROFILE_CONSERVATIVE' in s and 'PROFILE_TREND_RUNNER' in s and 'PROFILE_BREAKOUT_PROTECT' in s and 'PROFILE_BASKET_ESCAPE' in s
assert 'InpMagicManagementProfiles' in s
print('resolver static checks passed')
PY</automated>
  </verify>
  <done>Resolver phân biệt explicit conservative mapping với unmapped legacy fallback; mapped profiles hiện hữu không đổi; có evidence impact/fallback được ghi vào summary.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement legacy/default-old management path cho unmapped magic</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - Với `profile=legacy`/default-old: severe loss close và single severe loss close chạy trước các rule khác.
    - Với `profile=legacy`/default-old: `positions_count >= 4` hoặc đúng old threshold 4-position net positive close phải close toàn bộ tickets trong scoped group khi `net_profit > 0`.
    - Với `profile=legacy`/default-old: single profitable stale `positions_count == 1 && age_seconds > 1800 && net_profit > 0` phải close scoped ticket như old behavior.
    - Với `profile=legacy`/default-old: profit threshold, BUY bullish imbalance SL, SELL bearish imbalance SL, breakeven/profitability có commission/swap nếu hiện tại đã có, normalize SL, modify all tickets, preserve each TP phải tiếp tục hoạt động.
    - Mapped `conservative`, `trend_runner`, `breakout_protect`, `basket_escape` giữ behavior strategy-aware từ quick `260501-knj`.
  </behavior>
  <action>Sửa `ProcessPositionsByType` theo hướng ít thay đổi nhất: branch theo `profile == PROFILE_LEGACY` cho old-only exits trước profile-aware strategy exits. Severe risk guard vẫn áp dụng cho mọi profile. Basket net positive close và stale profitable single close chỉ áp dụng cho legacy/default-old; không áp dụng cho mapped conservative/trend/breakout/basket ngoài logic đã có. Đảm bảo decision logs cho legacy close/HOLD/MOVE/TRAIL có `profile=legacy` hoặc equivalent, `reason` rõ (`legacy_basket_recovery_profit`, `legacy_stale_profitable_single`, `severe_risk_guard`, `profit_below_sl_management_threshold`, `sl_target_not_profitable`, v.v.) và `primitive` map P-06/P-07/P-08/P-09/P-10/P-11/P-12/P-13/P-16. Không đổi group identity `symbol + magic + direction`; không đổi manual magic 0 skip; không đổi unsupported symbol skip.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
s=Path('D:/Aureus/mql5/AureusProvider_v2.mq5').read_text(encoding='utf-8', errors='ignore')
low=s.lower()
assert 'profile=legacy' in low or 'profile_legacy' in low or 'default_old' in low
assert 'severe_risk_guard' in s
assert 'basket_recovery_profit' in s
assert 'stale' in low and '1800' in s
assert 'PositionModify(tickets[i], proposed_sl_price, tp_for_this_pos)' in s
assert 'POSITION_TP' in s
assert 'FindContextIndex(symbol) < 0' in s
print('legacy behavior static checks passed')
PY</automated>
  </verify>
  <done>Unmapped magic chạy path legacy/default-old đầy đủ trong scoped group; mapped profiles vẫn strategy-aware; decision logs phân biệt legacy vs explicit conservative.</done>
</task>

<task type="auto">
  <name>Task 3: Compile, non-regression checks, và ghi GSD summary</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5, D:/Aureus/mql5/AureusProvider_v2_compile.log, D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md</files>
  <action>Compile theo `D:/Aureus/mql5/Build_Rules.md` bằng MetaEditor64 cho `AureusProvider_v2.mq5`; fix đến khi log có `Result: 0 errors, 0 warnings`. Chạy static non-regression checks bằng script hoặc targeted diff để chứng minh không đổi unsupported symbol behavior, history cooldown scope, `ExecuteCloseOrder`, `ExecuteRequestOrders`, `DoBackfillCountForSymbol`, `REQUEST_ORDERS`, `REQUEST_BACKFILL_COUNT`, `CLOSE_ORDER`, `BuildPositionsJSON`, `BuildTradeHistoryJSON` trừ khi diff chỉ là context không thay đổi behavior. Chạy `npx gitnexus detect-changes --repo Aureus || npx gitnexus detect_changes --repo Aureus || true`; nếu CLI không hỗ trợ, dùng fallback `git diff --stat` và targeted diff, ghi rõ. Tạo summary tiếng Việt theo anti-lack checklist: behavior matrix cho unmapped legacy vs mapped conservative/trend/breakout/basket, compile evidence, impact/fallback, no DB changes, no command path regression, no blank checklist item.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
    <automated>python - <<'PY'
from pathlib import Path
log=Path('D:/Aureus/mql5/AureusProvider_v2_compile.log').read_text(encoding='utf-16', errors='ignore')
assert '0 errors, 0 warnings' in log or 'Result: 0 errors, 0 warnings' in log
summary=Path('D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md')
assert summary.exists()
s=summary.read_text(encoding='utf-8', errors='ignore')
for needle in ['legacy', 'conservative', '0 errors, 0 warnings', 'No database files changed', 'CLOSE_ORDER', 'REQUEST_ORDERS', 'REQUEST_BACKFILL_COUNT']:
    assert needle in s
print('compile and summary checks passed')
PY</automated>
  </verify>
  <done>Compile sạch 0/0; summary tồn tại có evidence đầy đủ; GitNexus detect/fallback và non-regression command/history/unsupported-symbol checks được ghi; không có database changes.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `InpMagicManagementProfiles` input → resolver | Chuỗi mapping do user cấu hình trong MT5 input quyết định profile runtime. |
| MT5 live positions/history → management logic | State vị thế/deal từ terminal quyết định close/modify lệnh live. |
| Provider management logic → broker trade API | `trade.PositionClose` và `trade.PositionModify` tạo side effect tài chính. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-OCK-01 | Tampering | `InpMagicManagementProfiles` parsing | mitigate | Resolver trim/skip malformed pair; explicit mapping hợp lệ mới chọn strategy profile; unmapped magic về legacy/default-old rõ ràng thay vì accidental conservative. |
| T-OCK-02 | Repudiation | `LogManagementDecision` | mitigate | Mọi branch legacy và mapped profile phải log `symbol`, `magic`, `direction`, `profile`, `action`, `reason`, `primitive`, `net_profit`, `age_seconds`. |
| T-OCK-03 | Denial of Service / Safety | `ProcessPositionsByType` close/modify live trades | mitigate | Giữ severe risk guard cho mọi profile; giới hạn close legacy theo scoped `symbol + magic + direction`; preserve unsupported symbol/manual magic skip. |
| T-OCK-04 | Elevation of Privilege | Command paths | accept | Task không thay đổi command routing/execution; targeted diff xác nhận `CLOSE_ORDER`, `REQUEST_ORDERS`, `REQUEST_BACKFILL_COUNT` không đổi. |
</threat_model>

<verification>
- MetaEditor compile `D:/Aureus/mql5/AureusProvider_v2.mq5` trả `Result: 0 errors, 0 warnings`.
- Static checks xác nhận resolver có legacy/default-old fallback riêng cho unmapped magic và explicit conservative vẫn tồn tại.
- Static checks xác nhận legacy/default-old có severe loss, single severe, 4-position net positive close, stale profitable single >1800s close, threshold, imbalance SL, cost-aware profitability, preserve TP.
- Targeted diff/non-regression xác nhận unsupported symbol behavior, history cooldown scope, CLOSE_ORDER, REQUEST_ORDERS, REQUEST_BACKFILL_COUNT không đổi.
- Summary có no database changes; DB E2E không áp dụng vì chỉ sửa MQL5 provider và artifact.
</verification>

<success_criteria>
Quick hoàn tất khi `D:/Aureus/mql5/AureusProvider_v2.mq5` phân biệt unmapped legacy/default-old với explicit conservative, mapped profiles giữ strategy-aware behavior, compile sạch 0/0, và `D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md` ghi đầy đủ evidence không thiếu checklist.
</success_criteria>

<output>
Sau khi hoàn thành, tạo `D:/Aureus/.planning/quick/260501-ock-ph-i-gi-nguy-n-logic-c-v-i-case-profile-/260501-ock-SUMMARY.md`.
</output>
