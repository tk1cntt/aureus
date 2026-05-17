---
phase: 260517-tne-implement-safe-stale-single-handling-tro
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
autonomous: true
requirements:
  - QUICK-260517-TNE
must_haves:
  truths:
    - "Legacy single stale position with net_profit >= InpBEProfitTarget is not closed by market order."
    - "Legacy single stale position with 0 < net_profit < InpBEProfitTarget moves SL toward breakeven when SL is not already protective, instead of market close."
    - "Legacy loss handling and basket recovery logic remain unchanged."
    - "AureusProvider_v2.mq5 builds with MetaEditor using mql5/Build_Rules.md."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Safe ProcessLegacyPositionsByType stale single handling"
      contains: "ProcessLegacyPositionsByType"
  key_links:
    - from: "ManagePositionProfitBreakEvent"
      to: "ProcessLegacyPositionsByType"
      via: "ProcessPositionsByType legacy/default-old profile route"
      pattern: "ProcessLegacyPositionsByType\\(symbol, magic, target_type"
    - from: "ProcessLegacyPositionsByType"
      to: "MovePositionsSL"
      via: "near-breakeven stale single protection"
      pattern: "MovePositionsSL\\(symbol, magic, target_type, PROFILE_LEGACY"
    - from: "ProcessLegacyPositionsByType"
      to: "ClosePositionTickets"
      via: "retained negative risk guard and basket recovery close paths only, not profitable stale single"
      pattern: "(severe_risk_guard|legacy_basket_recovery_profit)"
---

<objective>
Sửa `ProcessLegacyPositionsByType` để không đóng market lệnh single stale đang lời tốt.

Purpose: chặn close sớm theo report `260517-sf2`, giữ logic âm hiện tại, bảo vệ lệnh lời nhỏ bằng SL breakeven thay vì close.
Output: `mql5/AureusProvider_v2.mq5` cập nhật và build sạch theo `mql5/Build_Rules.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-REPORT.md
@D:/Aureus/.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-SUMMARY.md
@D:/Aureus/mql5/Build_Rules.md
@D:/Aureus/mql5/AureusProvider_v2.mq5

Key source facts from report/source:
- Current flow: `ManagePositionProfitBreakEvent -> ProcessPositionsByType -> ProcessLegacyPositionsByType -> ClosePositionTickets(reason="legacy_stale_profitable_single")`.
- Current risky branch: `positions_count == 1 && age_seconds > 1800 && net_profit > 0` closes market.
- Required behavior: `net_profit >= InpBEProfitTarget` => HOLD/no market close.
- Required behavior: `0 < net_profit < InpBEProfitTarget` => call `MovePositionsSL` toward breakeven only if SL is not already protective; do not close market.
- Preserve existing negative risk guard and basket recovery branches.

<interfaces>
Existing signatures in `mql5/AureusProvider_v2.mq5`:

```mql5
bool MovePositionsSL(string symbol,
                     long magic,
                     ENUM_POSITION_TYPE target_type,
                     string profile,
                     const ulong &tickets[],
                     double net_profit,
                     int age_seconds,
                     double proposed_sl_price,
                     string action,
                     string reason,
                     string primitive)
```

```mql5
bool IsSLProfitable(string symbol,
                    ENUM_POSITION_TYPE target_type,
                    double proposed_sl_price,
                    double weighted_avg_open_price,
                    double total_volume,
                    double total_commission,
                    double total_swap)
```

```mql5
void ProcessLegacyPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
```

Build command pattern from `mql5/Build_Rules.md`:

```bash
cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Run GitNexus gate and inspect target branch</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5, D:/Aureus/.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-REPORT.md</files>
  <action>Before editing `ProcessLegacyPositionsByType`, run GitNexus impact analysis exactly as required by `CLAUDE.md`: `npx gitnexus impact ProcessLegacyPositionsByType --direction upstream --repo Aureus` or available MCP equivalent `gitnexus_impact({target: "ProcessLegacyPositionsByType", direction: "upstream"})`. Report blast radius to user before modifying file: direct callers, affected processes, risk level. If GitNexus says symbol not found, report that exact result and use report/source flow as fallback blast radius before editing: `ManagePositionProfitBreakEvent -> ProcessPositionsByType -> ProcessLegacyPositionsByType -> ClosePositionTickets`; risk medium because runtime close behavior changes. Do not edit any other symbol yet.</action>
  <verify>
    <automated>bash -lc 'set +e; OUT=$(npx gitnexus impact ProcessLegacyPositionsByType --direction upstream --repo Aureus 2>&1); RC=$?; printf "%s\n" "$OUT"; if [ $RC -eq 0 ]; then exit 0; fi; printf "%s\n" "$OUT" | grep -Eiq "symbol.*not found|not found.*symbol|ProcessLegacyPositionsByType.*not found" && exit 0; exit $RC'</automated>
  </verify>
  <done>Either GitNexus impact succeeds, or symbol-not-found output is captured and fallback blast radius is documented before editing; executor reports direct callers/affected processes/risk level from GitNexus or fallback flow; no source edit done before gate.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Replace stale profitable single close with safe hold or breakeven SL</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Modify only `ProcessLegacyPositionsByType`. Keep negative risk guard and `positions_count == 4 && net_profit > 0` basket recovery unchanged. Replace branch `positions_count == 1 && age_seconds > 1800 && net_profit > 0` so it never calls `ClosePositionTickets` for profitable stale single. Required logic: compute `weighted_avg_open_price = weighted_price_sum / total_volume` inside stale single branch. If `net_profit >= InpBEProfitTarget`, call `LogManagementDecision(... PROFILE_LEGACY, "HOLD", "legacy_stale_profit_target_reached", positions_count, net_profit, age_seconds, "P-08")` and return. If `0 < net_profit && net_profit < InpBEProfitTarget`, inspect current SL with `PositionSelectByTicket(tickets[0])` and `POSITION_SL`. Move SL to `weighted_avg_open_price` only when SL is not already protective: BUY protective if `current_sl >= weighted_avg_open_price`; SELL protective if `current_sl <= weighted_avg_open_price && current_sl > 0`. When already protective, log `HOLD` with reason `legacy_stale_single_sl_already_protective` and return. When not protective, call `MovePositionsSL(symbol, magic, target_type, PROFILE_LEGACY, tickets, net_profit, age_seconds, weighted_avg_open_price, "MOVE_SL", "legacy_stale_single_breakeven_protect", "P-08")` and return. Do not add MFE/MAE tracking, trailing, new inputs, or database work. Remove or stop using reason `legacy_stale_profitable_single` for market close path.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/mql5/AureusProvider_v2.mq5')
s = p.read_text(encoding='utf-8')
assert 'void ProcessLegacyPositionsByType' in s
assert 'legacy_stale_profit_target_reached' in s
assert 'legacy_stale_single_breakeven_protect' in s
assert 'legacy_stale_single_sl_already_protective' in s
assert 'MovePositionsSL(symbol, magic, target_type, PROFILE_LEGACY' in s
branch = s[s.index('void ProcessLegacyPositionsByType'):s.index('//+------------------------------------------------------------------+', s.index('void ProcessLegacyPositionsByType') + 1)]
assert 'legacy_stale_profitable_single' not in branch
assert 'ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_LEGACY, tickets, net_profit, age_seconds, "severe_risk_guard", "P-05/P-06")' in branch
assert 'ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_LEGACY, tickets, net_profit, age_seconds, "legacy_basket_recovery_profit", "P-07")' in branch
PY</automated>
  </verify>
  <done>Profitable stale single branch holds when `net_profit >= InpBEProfitTarget`; near-breakeven stale single moves SL only when SL not protective; no profitable stale single market close remains; existing loss/basket closes intact.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Build and scope-verify MQL5 change</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5, D:/Aureus/mql5/AureusProvider_v2_compile.log</files>
  <action>Build `AureusProvider_v2.mq5` using `MetaEditor64.exe` command example from `mql5/Build_Rules.md`, even though `Build_Rules.md` also mentions `terminal64.exe`; treat the documented `MetaEditor64.exe /compile` example as the primary compile command. Use compile log `D:\Aureus\mql5\AureusProvider_v2_compile.log`. If the `MetaEditor64.exe` command fails, read `D:/Aureus/RUN_SERVICES.md` per `CLAUDE.md`, then compare with `D:/Aureus/mql5/Build_Rules.md` to choose the correct local build fallback without changing source scope. If build has errors or warnings, fix only lines caused by this change and rebuild until clean per Build_Rules. Then run GitNexus detect changes before commit/summarize: `npx gitnexus detect-changes --repo Aureus` or MCP equivalent. Confirm database unrelated, so no DB E2E needed.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
    <automated>npx gitnexus detect-changes --repo Aureus</automated>
  </verify>
  <done>Compile log has zero errors and zero warnings; GitNexus change detection shows expected MQL5 scope only; summary records no DB E2E because database unrelated.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5 position state -> provider management logic | Live account position data drives hold, SL modify, or close decisions. |
| provider management logic -> MT5 trade API | Code can modify SL or close positions through `trade.PositionModify`/`trade.PositionClose`. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|
| T-260517-tne-01 | Tampering | `ProcessLegacyPositionsByType` profitable stale single branch | mitigate | Remove market close for profitable stale single; only HOLD or `MovePositionsSL` to weighted breakeven. |
| T-260517-tne-02 | Denial of Service | repeated SL modify on already-protective SL | mitigate | Check current SL before `MovePositionsSL`; log HOLD when SL already protects breakeven. |
| T-260517-tne-03 | Elevation of Privilege | unintended changes to other management profiles | mitigate | Edit only `ProcessLegacyPositionsByType`; verify conservative/trend/breakout symbols unchanged except no intended edits. |
| T-260517-tne-04 | Repudiation | unclear stale single decision path | mitigate | Use distinct log reasons: `legacy_stale_profit_target_reached`, `legacy_stale_single_breakeven_protect`, `legacy_stale_single_sl_already_protective`. |
</threat_model>

<verification>
Overall checks:
- GitNexus impact gate run before edit and blast radius reported.
- Static Python assertion confirms no `legacy_stale_profitable_single` market close remains inside `ProcessLegacyPositionsByType`.
- MetaEditor build command from `mql5/Build_Rules.md` passes with zero errors/warnings.
- GitNexus detect changes confirms expected scope.
</verification>

<success_criteria>
- `ProcessLegacyPositionsByType` preserves negative risk guard and basket recovery close behavior.
- `net_profit >= InpBEProfitTarget` for stale single produces HOLD, not close.
- `0 < net_profit < InpBEProfitTarget` for stale single moves SL to weighted breakeven only if current SL is not already protective.
- No database code touched; no DB E2E required.
- `mql5/AureusProvider_v2.mq5` builds clean using `mql5/Build_Rules.md`.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260517-tne-implement-safe-stale-single-handling-tro/260517-tne-SUMMARY.md`.
</output>
