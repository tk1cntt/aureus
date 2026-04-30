---
phase: 260430-qmk-update-checkdcaentryconditionfromcisd-dc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
  - .planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md
autonomous: true
requirements:
  - QUICK-260430-QMK
must_haves:
  truths:
    - "CISD DCA gate evaluates DCA entry using the matching strategy magic and symbol, not only the chart symbol."
    - "DoDCA calculates profit, swap, volume, TP, and position updates only from positions matching the requested strategy magic and symbol."
    - "Existing ExecuteOpenOrder duplicate guard continues rejecting active position/order with the same symbol and magic before ACK/order side effects."
    - "mql5/AureusProvider_v2.mq5 compiles in MetaEditor with 0 errors and 0 warnings."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Strategy+symbol scoped CheckDCAEntryConditionFromCISD and DoDCA logic"
      contains: "void DoDCA"
    - path: ".planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md"
      provides: "Execution summary with GitNexus impact attempts, compile result, and duplicate guard preservation note"
  key_links:
    - from: "mql5/AureusProvider_v2.mq5::CheckDCAEntryConditionFromCISD"
      to: "mql5/AureusProvider_v2.mq5::DoDCA"
      via: "call passes symbol and strategy magic used by matching DCA positions"
      pattern: "DoDCA\\(.*symbol.*magic|DoDCA\\(.*magic.*symbol"
    - from: "mql5/AureusProvider_v2.mq5::DoDCA"
      to: "MT5 position/order state"
      via: "PositionGetString(POSITION_SYMBOL) and PositionGetInteger(POSITION_MAGIC) filters"
      pattern: "POSITION_SYMBOL.*symbol|POSITION_MAGIC.*magic"
    - from: "mql5/AureusProvider_v2.mq5::ExecuteOpenOrder"
      to: "duplicate active strategy guard"
      via: "same symbol + magic checks over PositionsTotal and OrdersTotal before SendACK"
      pattern: "STRATEGY_ORDER_EXISTS"
---

<objective>
Cập nhật DCA trong `mql5/AureusProvider_v2.mq5` để `CheckDCAEntryConditionFromCISD` kích hoạt DCA theo đúng strategy magic và symbol, còn `DoDCA` tính toán/modify/open DCA chỉ trên nhóm position khớp strategy magic + symbol.

Purpose: Tránh DCA bị trộn position giữa nhiều strategy hoặc nhiều symbol, đồng thời giữ nguyên lớp chặn duplicate order theo `symbol + magic` vừa có trong `ExecuteOpenOrder`.
Output: Một thay đổi surgical trong `mql5/AureusProvider_v2.mq5`, compile MetaEditor sạch 0 errors/0 warnings, và summary ghi rõ kiểm chứng.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/mql5/Build_Rules.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5

<interfaces>
Existing target contracts in `mql5/AureusProvider_v2.mq5`:
```mql5
void DoDCA(int order_type_signal)
void CheckDCAEntryConditionFromCISD()
void UpdateCISDDCAH1State()
void ExecuteOpenOrder(const string &raw)
```

Existing duplicate guard that must be preserved in `ExecuteOpenOrder`:
```mql5
if(PositionGetString(POSITION_SYMBOL) == symbol && PositionGetInteger(POSITION_MAGIC) == magic) { SendNACK(cmdId, "STRATEGY_ORDER_EXISTS"); return; }
if(OrderGetString(ORDER_SYMBOL) == symbol && OrderGetInteger(ORDER_MAGIC) == magic) { SendNACK(cmdId, "STRATEGY_ORDER_EXISTS"); return; }
```

Reference behavior source: `mql5/CISD_Slope_EA_v6.39_Final.mq5` contains the original `DoDCA(int order_type_signal)` and CISD stateful trigger style, but provider implementation must remain provider-safe and scoped by command/position metadata.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Perform GitNexus impact attempts and confirm surgical edit scope</name>
  <files>mql5/AureusProvider_v2.mq5, .planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md</files>
  <action>Before editing any symbol, attempt GitNexus impact analysis for `DoDCA` and `CheckDCAEntryConditionFromCISD` with upstream direction, per `D:/Aureus/CLAUDE.md`. If GitNexus MCP/tools are unavailable or these MQL5 symbols are not indexed, record the exact fallback reason in the summary and continue only after manually reading the existing callers in `AureusProvider_v2.mq5`. Also inspect `ExecuteOpenOrder` and explicitly preserve its `symbol + magic` duplicate guard; do not refactor unrelated order execution, JSON parsing, socket, candle, or journal code.</action>
  <verify>
    <automated>git diff -- D:/Aureus/mql5/AureusProvider_v2.mq5</automated>
  </verify>
  <done>Impact attempts or fallback documentation exist in the summary draft/notes; executor can name direct callers to be affected (`CheckDCAEntryConditionFromCISD`, market-order post-fill `DoDCA` call, timer gate if signature changes); no unrelated files are modified.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Scope DoDCA and CISD trigger by strategy magic and symbol</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - Given multiple open positions across symbols, `DoDCA` only includes positions where `POSITION_SYMBOL == requested symbol`.
    - Given multiple open positions on the same symbol with different magic numbers, `DoDCA` only includes positions where `POSITION_MAGIC == requested magic`.
    - When `CheckDCAEntryConditionFromCISD` fires a BUY/SELL DCA signal, it passes the matching symbol and strategy magic into `DoDCA` so volume/profit/TP calculations are scoped to that strategy group.
    - Existing `ExecuteOpenOrder` duplicate active strategy order guard remains semantically identical: same symbol + same magic active position or pending order returns `STRATEGY_ORDER_EXISTS` before ACK/order side effects.
  </behavior>
  <action>Update `DoDCA` signature to accept strategy scope, e.g. `void DoDCA(int order_type_signal, string symbol, long magic)`, and replace every `_Symbol` use inside DCA position selection, price lookup, broker constraints, trade open, TP modify filtering, and logging with the scoped `symbol` where it refers to the traded instrument. Add `POSITION_MAGIC == magic` filters to all DCA position collection and TP modification loops. Set `trade.SetExpertMagicNumber(magic)` before opening the DCA order so new DCA positions inherit the same strategy identity. Update all `DoDCA` callers: `CheckDCAEntryConditionFromCISD` must pass the symbol/magic for the matched strategy group; the existing post-market-fill call in `ExecuteOpenOrder` must pass `symbol` and `magic` instead of using chart-only `_Symbol`. If the current `CheckDCAEntryConditionFromCISD` has no magic parameter/state, change it to iterate or accept strategy scope from active positions in a surgical way: trigger DCA only for a group where at least one existing position matches `symbol + magic + direction`, and do not introduce new persistence or external files. Preserve `ExecuteOpenOrder` duplicate guard exactly in behavior and do not weaken the `PositionsTotal`/`OrdersTotal` checks.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
  </verify>
  <done>`DoDCA` calculations, trade open, and TP modifications are scoped by `symbol + magic`; `CheckDCAEntryConditionFromCISD` no longer causes chart-symbol-only DCA for unrelated strategies; MetaEditor compile completes with 0 errors and 0 warnings.</done>
</task>

<task type="auto">
  <name>Task 3: Verify compile log, duplicate guard, and changed-symbol scope</name>
  <files>mql5/AureusProvider_v2.mq5, .planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md</files>
  <action>Read `D:/Aureus/mql5/AureusProvider_v2_compile.log` and confirm it reports 0 errors and 0 warnings. Re-check `ExecuteOpenOrder` still rejects `STRATEGY_ORDER_EXISTS` for both active positions and pending orders with same `symbol + magic` before `SendACK`. Run GitNexus detect changes if available; if unavailable/not indexed, document fallback and manually summarize changed functions. Create the summary file with assumptions, impact results/fallback, exact files changed, compile outcome, duplicate guard preservation, and any residual risk.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
  </verify>
  <done>Summary exists; compile log confirms 0 errors/0 warnings; Git diff is limited to `mql5/AureusProvider_v2.mq5` and the quick planning summary; duplicate guard is explicitly verified as preserved.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gateway command -> MT5 provider | Untrusted command fields (`symbol`, `magic`, order details) influence trade execution and DCA grouping. |
| MT5 account state -> DCA calculation | Live positions/orders across strategies and symbols are read to calculate DCA sizing/TP. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260430-qmk-01 | T/E | `DoDCA` | mitigate | Filter all DCA position collection and TP modification by both `POSITION_SYMBOL == symbol` and `POSITION_MAGIC == magic`; set trade magic before DCA order open. |
| T-260430-qmk-02 | T | `CheckDCAEntryConditionFromCISD` | mitigate | Pass or derive explicit `symbol + magic` strategy scope before calling `DoDCA`; never call DCA with chart symbol only for unrelated active strategies. |
| T-260430-qmk-03 | D/T | `ExecuteOpenOrder` | mitigate | Preserve existing duplicate active strategy guard over `PositionsTotal` and `OrdersTotal` with same `symbol + magic` before ACK/order side effects. |
</threat_model>

<verification>
Overall checks:
1. GitNexus impact attempted for `DoDCA` and `CheckDCAEntryConditionFromCISD`, with fallback documented if unavailable/not indexed.
2. `mql5/AureusProvider_v2.mq5` compiles via MetaEditor using `D:/Aureus/mql5/Build_Rules.md` command adapted to `AureusProvider_v2.mq5`.
3. Compile log reports 0 errors and 0 warnings.
4. `git diff -- D:/Aureus/mql5/AureusProvider_v2.mq5` shows only DCA strategy/symbol scoping and necessary caller updates.
5. `STRATEGY_ORDER_EXISTS` duplicate guard in `ExecuteOpenOrder` remains present for positions and pending orders before `SendACK`.
</verification>

<success_criteria>
- `CheckDCAEntryConditionFromCISD` triggers DCA using strategy-aware `symbol + magic` scope.
- `DoDCA` calculations and modifications cannot aggregate positions from another strategy or symbol.
- Existing duplicate order protection by `symbol + magic` remains intact.
- MetaEditor compile is clean: 0 errors, 0 warnings.
- Summary documents impact analysis attempts, verification commands, and changed files.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md`
</output>
