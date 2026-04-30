---
phase: quick-260430-roa-update-executeopenorder-entry-and-dodca
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
  - .planning/quick/260430-roa-update-executeopenorder-entry-and-dodca-/260430-roa-SUMMARY.md
autonomous: true
requirements:
  - QUICK-260430-ROA
must_haves:
  truths:
    - "BUY and SELL strategy groups with the same symbol+magic are treated as separate active groups."
    - "An existing BUY position/order blocks only new BUY entry for the same symbol+magic, not SELL entry for the same symbol+magic."
    - "An existing SELL position/order blocks only new SELL entry for the same symbol+magic, not BUY entry for the same symbol+magic."
    - "DoDCA continues to manage only the target symbol+magic+direction group and does not mix opposite-direction positions."
    - "Provider-local CISD DCA still scans all configured InpSymbols and finds DCA magic by symbol+direction."
    - "AureusProvider_v2 compiles in MetaEditor with 0 errors and 0 warnings."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Direction-aware duplicate entry guard and direction-scoped DCA management"
      contains: "ExecuteOpenOrder"
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "DCA symbol+magic+direction grouping"
      contains: "DoDCA"
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Provider-local DCA magic lookup scoped by symbol+direction"
      contains: "FindDCAMagicForSymbolDirection"
    - path: "mql5/AureusProvider_v2_compile.log"
      provides: "Generated MetaEditor compile log, ignored and not committed"
  key_links:
    - from: "ExecuteOpenOrder duplicate guard"
      to: "MT5 positions/orders"
      via: "compare symbol + magic + requested direction/order side"
      pattern: "PositionGetString\\(POSITION_SYMBOL\\).*PositionGetInteger\\(POSITION_MAGIC\\).*POSITION_TYPE"
    - from: "ExecuteOpenOrder duplicate guard"
      to: "MT5 pending orders"
      via: "map ORDER_TYPE_BUY_LIMIT/BUY_STOP to BUY and ORDER_TYPE_SELL_LIMIT/SELL_STOP to SELL before blocking"
      pattern: "OrderGetInteger\\(ORDER_TYPE\\)"
    - from: "CheckDCAEntryConditionFromCISD"
      to: "FindDCAMagicForSymbolDirection and DoDCA"
      via: "BUY signals use POSITION_TYPE_BUY and SELL signals use POSITION_TYPE_SELL"
      pattern: "FindDCAMagicForSymbolDirection\\(symbol, POSITION_TYPE_(BUY|SELL)\\)"
    - from: "DoDCA"
      to: "MT5 positions and TP modification"
      via: "filter symbol + magic + target_position_type before aggregation/open/modify"
      pattern: "PositionGetString\\(POSITION_SYMBOL\\) == symbol.*PositionGetInteger\\(POSITION_MAGIC\\) == magic"
---

<objective>
Update `AureusProvider_v2` order-entry and DCA grouping so BUY and SELL are independent strategy groups even when they share the same symbol+magic.

Purpose: Preserve strategy-symbol DCA and multi-symbol behavior while allowing hedged/opposite-direction strategy groups to coexist without blocking or managing each other.
Output: Surgical MQL5 changes in `mql5/AureusProvider_v2.mq5`, MetaEditor compile proof with 0 errors/0 warnings, and a quick summary artifact.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/mql5/Build_Rules.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5

<interfaces>
Key existing contracts in `mql5/AureusProvider_v2.mq5`:

```mql5
void DoDCA(int order_type_signal, string symbol, long magic)
```
- `order_type_signal == 1` manages/opens BUY DCA.
- `order_type_signal == -1` manages/opens SELL DCA.
- Current implementation already filters positions by `POSITION_SYMBOL`, `POSITION_MAGIC`, and target `POSITION_TYPE`; preserve this direction-scoped aggregation and TP modification.

```mql5
long FindDCAMagicForSymbolDirection(string symbol, ENUM_POSITION_TYPE position_type)
```
- Returns active magic for a symbol and position direction.
- Used by CISD DCA gate to call `DoDCA(1, symbol, magic)` or `DoDCA(-1, symbol, magic)`.

```mql5
void CheckDCAEntryConditionFromCISD(string symbol, CISDDCAState &state)
```
- Called for every configured `InpSymbols` entry from `OnTimer`.
- Must continue scanning all symbols and must keep BUY lookup separate from SELL lookup.

```mql5
void ExecuteOpenOrder(const string &raw)
```
- Parses `direction`, `orderType`, `symbol`, and `magic`.
- Current duplicate guard blocks by symbol+magic only; update it to block by symbol+magic+direction/order side.
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Make ExecuteOpenOrder duplicate guard direction-aware</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <action>Before editing, attempt GitNexus impact analysis for `ExecuteOpenOrder` using `gitnexus_impact({target: "ExecuteOpenOrder", direction: "upstream"})`; if MQL5 symbols are not indexed or the tool is unavailable, document the failed attempt and fallback reasoning in the summary before changing code. Update only the duplicate active strategy guard inside `ExecuteOpenOrder`: compute requested side from parsed `direction`, then for existing positions block only when `POSITION_SYMBOL == symbol`, `POSITION_MAGIC == magic`, and `POSITION_TYPE` matches the requested side. For existing pending orders, block only when `ORDER_SYMBOL == symbol`, `ORDER_MAGIC == magic`, and order type maps to the requested side (`ORDER_TYPE_BUY_LIMIT`, `ORDER_TYPE_BUY_STOP`, `ORDER_TYPE_BUY_STOP_LIMIT` for BUY; `ORDER_TYPE_SELL_LIMIT`, `ORDER_TYPE_SELL_STOP`, `ORDER_TYPE_SELL_STOP_LIMIT` for SELL). Keep the NACK reason `STRATEGY_ORDER_EXISTS`, command idempotency, symbol allow-list behavior, ACK timing, and all order execution logic unchanged. Do not change files outside `mql5/AureusProvider_v2.mq5` and planning artifacts.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
  </verify>
  <done>Same-direction duplicate positions/orders for the same symbol+magic still return `STRATEGY_ORDER_EXISTS`; opposite-direction positions/orders with the same symbol+magic no longer block entry. Compile log is generated but remains ignored/not committed.</done>
</task>

<task type="auto">
  <name>Task 2: Audit and preserve DoDCA direction-scoped grouping</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <action>Before editing any DCA-related symbol, attempt GitNexus impact analysis for `DoDCA`, `FindDCAMagicForSymbolDirection`, and `CheckDCAEntryConditionFromCISD` using upstream direction; if MQL5 symbols are not indexed or the tool is unavailable, document the attempts and fallback in the summary. Inspect the current DCA flow and only patch if a BUY/SELL mixing defect remains. Preserve these invariants: `DoDCA(1, symbol, magic)` aggregates, opens, and modifies only BUY positions for that symbol+magic; `DoDCA(-1, symbol, magic)` aggregates, opens, and modifies only SELL positions for that symbol+magic; `FindDCAMagicForSymbolDirection` returns magic by symbol+position_type; `OnTimer` continues calling `CheckDCAEntryConditionFromCISD` for every `InpSymbols` context. Do not simplify prior behavior from quick tasks 260430-qmk and 260430-rak.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
  </verify>
  <done>DCA remains scoped by symbol+magic+direction, multi-symbol DCA over `InpSymbols` is preserved, and MetaEditor compile reports 0 errors and 0 warnings.</done>
</task>

<task type="auto">
  <name>Task 3: Verify compile cleanliness and record scope summary</name>
  <files>.planning/quick/260430-roa-update-executeopenorder-entry-and-dodca-/260430-roa-SUMMARY.md</files>
  <action>Run the MetaEditor compile command from `mql5/Build_Rules.md` against `D:\Aureus\mql5\AureusProvider_v2.mq5` and inspect `D:\Aureus\mql5\AureusProvider_v2_compile.log` until it shows 0 errors and 0 warnings. Run `gitnexus_detect_changes()` before finishing if GitNexus is available; otherwise document the unavailable/stale-index fallback. Create the summary with the exact behavior changes, GitNexus impact attempts/blast-radius notes, compile result, and confirmation that `mql5/AureusProvider_v2_compile.log` is generated/ignored and not included as a planned source artifact.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
  </verify>
  <done>`260430-roa-SUMMARY.md` exists, states 0 errors/0 warnings, lists only expected modified source/planning files, and documents GitNexus impact/detect-change results or fallback attempts.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gateway TCP command -> MT5 provider | Untrusted/raw JSON-like order commands cross into live trading execution logic. |
| MT5 account state -> provider grouping logic | Existing positions and pending orders determine whether a new order is accepted or rejected. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260430-roa-01 | Tampering | `ExecuteOpenOrder` duplicate guard | mitigate | Keep symbol allow-list and idempotency unchanged; add direction-aware matching so only same symbol+magic+side blocks. |
| T-260430-roa-02 | Denial of Service | Opposite-direction entry on same symbol+magic | mitigate | Prevent existing BUY from denying SELL and existing SELL from denying BUY by mapping positions/orders to requested side. |
| T-260430-roa-03 | Tampering | `DoDCA` TP modification | mitigate | Preserve filtering by symbol+magic+target `POSITION_TYPE` before aggregating or modifying positions. |
| T-260430-roa-04 | Repudiation | Compile and change verification | mitigate | Require MetaEditor compile log with 0 errors/0 warnings plus GitNexus impact/detect-change attempts or documented fallback. |
</threat_model>

<verification>
Overall verification:
1. MetaEditor compile command completes for `D:\Aureus\mql5\AureusProvider_v2.mq5`.
2. `D:\Aureus\mql5\AureusProvider_v2_compile.log` shows 0 errors and 0 warnings.
3. Source changes are surgical: only direction-aware duplicate/order grouping and any necessary DCA direction-scope preservation in `mql5/AureusProvider_v2.mq5`.
4. Compile log remains generated/ignored and is not committed.
</verification>

<success_criteria>
- BUY and SELL groups sharing symbol+magic can coexist without duplicate-entry cross-blocking.
- Same-direction duplicate guard behavior remains intact for positions and pending orders.
- DoDCA and CISD DCA gate remain symbol+magic+direction scoped and multi-symbol over `InpSymbols`.
- MetaEditor compile reports 0 errors and 0 warnings.
- Summary documents GitNexus impact attempts and final verification.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260430-roa-update-executeopenorder-entry-and-dodca-/260430-roa-SUMMARY.md`.
</output>
