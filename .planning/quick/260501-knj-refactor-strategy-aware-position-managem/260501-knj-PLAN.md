---
phase: quick-260501-knj-refactor-strategy-aware-position-managem
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
  - .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md
autonomous: true
requirements:
  - KNJ-01
  - KNJ-02
  - KNJ-03
must_haves:
  truths:
    - "Strategy-aware management is composed from explicit rule primitives, not profile routing only."
    - "Every old behavior/rule row from the anti-lack checklist is marked KEPT, CHANGED, DEFERRED, N/A, or BLOCKED with evidence/rationale before completion."
    - "Open positions remain grouped by symbol + magic + direction; manual magic 0 and unsupported symbols are skipped."
    - "Net profit and SL profitability include commission/swap cost awareness; TP is preserved on every SL modification."
    - "No global profitable single age close exists; all time logic is profile-scoped."
    - "CLOSE_ORDER, REQUEST_ORDERS, REQUEST_BACKFILL_COUNT, unsupported-symbol behavior, and history cooldown scope do not regress."
    - "MetaEditor compile reports 0 errors and 0 warnings."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Refactored provider strategy-aware management primitives and command-path preservation"
      contains: "ProcessPositionsByType"
    - path: ".planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md"
      provides: "Final anti-lack evidence, coverage matrix, compile evidence, GitNexus/fallback evidence"
      contains: "Old behavior/rule coverage matrix"
  key_links:
    - from: "mql5/AureusProvider_v2.mq5:ManagePositionProfitBreakEvent"
      to: "mql5/AureusProvider_v2.mq5:ProcessPositionsByType"
      via: "symbol + magic + direction grouped ticket arrays"
      pattern: "ProcessPositionsByType\\(symbol, magic, type"
    - from: "mql5/AureusProvider_v2.mq5:ProcessPositionsByType"
      to: "mql5/AureusProvider_v2.mq5:ResolveManagementProfile"
      via: "single profile resolve per group"
      pattern: "ResolveManagementProfile\\(magic"
    - from: "mql5/AureusProvider_v2.mq5:ProcessPositionsByType"
      to: "mql5/AureusProvider_v2.mq5:LogManagementDecision"
      via: "every HOLD/MOVE_SL/TRAIL_SL/CLOSE branch emits primitive-aware audit log"
      pattern: "LogManagementDecision\\(symbol, magic"
---

<objective>
Refactor/extend `mql5/AureusProvider_v2.mq5` strategy-aware position management so it fully implements the anti-lack checklist from `260501-kcz-IMPLEMENTATION-CHECKLIST.md`, not only profile routing.

Purpose: close the partial-execution risk identified after quick `260501-i1p` by forcing rule primitive coverage, old behavior disposition evidence, non-regression checks, and compile proof.
Output: updated MQL5 provider plus `260501-knj-SUMMARY.md` containing final coverage matrix for every checklist row.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md
@D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-SUMMARY.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5
@D:/Aureus/mql5/Build_Rules.md
@D:/Aureus/.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md

<interfaces>
Current provider contracts to preserve/use:
```mql5
string ResolveManagementProfile(long magic, bool &fallback_used);
void LogManagementDecision(string symbol, long magic, string direction, string profile, string action, string reason, int positions_count, double net_profit, int age_seconds, ulong ticket = 0, double target_sl = 0);
void ProcessPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time);
void ManagePositionProfitBreakEvent();
int FindHistoryCooldownIndex(string symbol, long magic, string direction);
void ApplyCloseDealToHistoryCooldown(ulong dealTicket, string source);
bool IsHistoryCooldownActive(string symbol, long magic, string direction, datetime &cooldownUntil);
```

Reference old EA behaviors are enumerated in checklist sections 4-9 and must be treated as source of truth. Do not silently omit old signal/cycle behaviors; mark KEPT/CHANGED/DEFERRED/N/A/BLOCKED with rationale.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pre-edit impact and rule primitive decomposition</name>
  <files>mql5/AureusProvider_v2.mq5, .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md</files>
  <action>Before editing any MQL5 symbol, run GitNexus impact analysis for every symbol intended to change: at minimum `ManagePositionProfitBreakEvent`, `ProcessPositionsByType`, `ResolveManagementProfile`, `LogManagementDecision`, and any helper you modify/create if GitNexus can see it. Report direct callers/affected processes/risk in the summary. If GitNexus MCP is unavailable or CLI cannot analyze MQL5, use fallback: run `npx gitnexus impact <symbol>` or nearest CLI equivalent; if still unavailable, record a fallback section with attempted commands, failure output, and local call graph evidence from the file. Then convert checklist primitive IDs P-01..P-20 into an implementation map: for each primitive, state whether it will be implemented in code, preserved unchanged, changed intentionally, deferred, or N/A. This task must not change command handlers or unsupported-symbol code except for read-only review.</action>
  <verify>
    <automated>cd /d/Aureus && (npx gitnexus impact ManagePositionProfitBreakEvent || true) && (npx gitnexus impact ProcessPositionsByType || true)</automated>
    <automated>cd /d/Aureus && test -f .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md && grep -E "P-01|P-20|GitNexus|fallback" .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md</automated>
  </verify>
  <done>Summary contains GitNexus impact/fallback evidence and a primitive map covering P-01 through P-20 with no blank primitive. No code edit starts until this evidence exists.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Refactor provider management into complete rule primitives</name>
  <files>mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - B-01/B-02/P-01: groups are symbol + magic + direction; BUY and SELL never mix; strategies never mix.
    - B-03/B-04/P-02/P-19: manual magic 0 and unsupported symbols are skipped without altering unsupported-symbol command behavior.
    - P-03/P-16: resolver parses `magic:profile;magic:profile`, trims tokens, malformed/unknown/invalid entries fall back to `conservative`; no JSON/DSL/hot reload.
    - P-04: all HOLD/MOVE_SL/TRAIL_SL/CLOSE decisions log symbol, magic, direction, profile, action, reason, positions_count, net_profit, age_seconds, and per-ticket target fields for SL actions; include a `primitive` audit field or helper-equivalent reason field that names primitive ID(s), for example `primitive=P-12`.
    - P-05/P-06/P-12: commission and swap are included where cost-aware net profit or breakeven is required; severe loss guard remains scoped to the group.
    - P-07/P-08/P-14/P-15: basket recovery is only scoped to `basket_escape`; no global stale profitable single close; `trend_runner` never closes winner by age alone; `breakout_protect` uses profile-scoped protective SL path before any close and holds if not cost-profitable.
    - P-09/P-10/P-11/P-13: threshold gates normal SL management; BUY bullish imbalance and SELL bearish imbalance candidates are used; SL target must be profitable after costs; every ticket in the group is modified and TP is preserved per ticket.
    - P-17/P-18/P-20/P-19: history cooldown scope by symbol+magic+direction is preserved or explicitly justified; old signal cooldown side effects and cycle telemetry are not silently omitted; command paths remain unchanged unless summary explicitly justifies a change.
  </behavior>
  <action>Make the smallest surgical refactor in `mql5/AureusProvider_v2.mq5` needed to satisfy the checklist. Prefer helper functions that express primitives directly (for example cost/breakeven calculation, profile checks, SL candidate selection, primitive-aware decision logging) but avoid unnecessary abstraction. Keep current command handlers and unsupported-symbol behavior unchanged: do not modify `ExecuteCloseOrder`, `ExecuteRequestOrders`, `DoBackfillCountForSymbol`, `ProcessSingleCommand` routing for `REQUEST_BACKFILL_COUNT`, `BuildPositionsJSON`, or `BuildTradeHistoryJSON` unless a checklist row forces it and summary records rationale. Do not hard-code strategy magic in decision logic beyond the default input mapping string. Do not add external config, DSL, JSON profile reader, hot reload, database files, or global stale close. Compile with MetaEditor and fix until the log is 0 errors and 0 warnings.</action>
  <verify>
    <automated>cd /d/Aureus && "/e/Openclaw/MetaTrader5/MetaEditor64.exe" /compile:"D:/Aureus/mql5/AureusProvider_v2.mq5" /log:"D:/Aureus/mql5/AureusProvider_v2_compile.log"; grep -E "Result: 0 errors, 0 warnings" D:/Aureus/mql5/AureusProvider_v2_compile.log</automated>
    <automated>cd /d/Aureus && grep -E "primitive=|P-0|P-1|P-20" mql5/AureusProvider_v2.mq5 && ! grep -E "net_profit[[:space:]]*>[[:space:]]*0.*positions_count[[:space:]]*==[[:space:]]*1.*1800.*PositionClose|positions_count[[:space:]]*==[[:space:]]*1.*1800.*PositionClose" mql5/AureusProvider_v2.mq5</automated>
    <automated>cd /d/Aureus && ! git diff -U0 -- mql5/AureusProvider_v2.mq5 | grep -E "^[+-].*(ExecuteCloseOrder|ExecuteRequestOrders|DoBackfillCountForSymbol|REQUEST_BACKFILL_COUNT|BuildPositionsJSON|BuildTradeHistoryJSON)"</automated>
  </verify>
  <done>Provider implements/preserves all required primitives; no prohibited global stale close or hard-coded magic decision branch exists; command paths and unsupported-symbol handling are unchanged or explicitly justified; compile log shows 0 errors and 0 warnings.</done>
</task>

<task type="auto">
  <name>Task 3: Final anti-lack coverage matrix and change detection</name>
  <files>.planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md, mql5/AureusProvider_v2.mq5</files>
  <action>Complete the summary/evidence artifact as a hard gate. Copy or recreate checklist coverage at sufficient detail so every row B-01..B-30 has final mark KEPT, CHANGED, DEFERRED, N/A, or BLOCKED plus evidence/rationale. Also cover all profile checklist sections 7.1..7.4, function-level checklist sections 8.1..8.6, scenario verification rows 9.2, and summary evidence section 9.3. For every DEFERRED row, fill a deferred rationale table with impact and safety check. Include compile command/result, static checks, command-path non-regression, no database files changed, and final GitNexus `detect_changes` result. If GitNexus detect changes is unavailable for MQL5, record fallback with attempted command and `git diff --stat`/targeted diff evidence. If any checklist item remains blank or BLOCKED, write `INCOMPLETE — anti-lack gate failed` and do not claim complete.</action>
  <verify>
    <automated>cd /d/Aureus && (npx gitnexus detect-changes || npx gitnexus detect_changes || true)</automated>
    <automated>cd /d/Aureus && grep -E "B-01|B-30|7\\.1|7\\.4|8\\.1|8\\.6|9\\.2|Result: 0 errors, 0 warnings|No database files changed|GitNexus" .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md</automated>
    <automated>cd /d/Aureus && ! grep -E "\| B-[0-9]+ .*\| \[ \]" .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md</automated>
    <automated>cd /d/Aureus && ! grep -E "\[ \]" .planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md</automated>
  </verify>
  <done>Summary contains final coverage matrix marks for every checklist row and no blank item across coverage matrix, profile checklist, function-level checklist, scenario checklist, and summary checklist. GitNexus detect changes or fallback evidence is recorded. The task is incomplete if the final artifact does not explicitly cover every checklist row.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gateway command JSON -> provider command handlers | Existing untrusted command input enters MT5 provider; this plan must not change command routing/unsupported-symbol behavior. |
| MT5 account positions/history -> management logic | Live broker state drives close/modify decisions; rule primitives must be scoped to symbol + magic + direction to avoid cross-strategy side effects. |
| Input string `InpMagicManagementProfiles` -> profile resolver | User-editable mapping controls profile selection; malformed/unknown values must safely fall back to conservative. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-KNJ-01 | Tampering | `InpMagicManagementProfiles` parser | mitigate | Trim/validate mapping pairs; unknown/malformed profiles fall back to `conservative`; no external config/DSL/hot reload. |
| T-KNJ-02 | Elevation of Privilege | Position grouping/close loop | mitigate | Require symbol + magic + direction grouping and skip magic 0/unsupported symbols before any close/modify operation. |
| T-KNJ-03 | Repudiation | Management decisions | mitigate | Emit structured decision logs with primitive field/helper-equivalent plus symbol, magic, direction, profile, action, reason, counts/profit/age/ticket/target_sl. |
| T-KNJ-04 | Denial of Service | Aggressive stale close/basket close | mitigate | Remove/forbid global profitable single age close; basket recovery only scoped to `basket_escape`; severe risk guard remains group-scoped. |
| T-KNJ-05 | Tampering | Command paths | mitigate | Do not modify CLOSE_ORDER, REQUEST_ORDERS, REQUEST_BACKFILL_COUNT paths unless explicitly justified in coverage matrix; verify via targeted diff. |
</threat_model>

<verification>
Overall checks:
1. MetaEditor compile log at `D:/Aureus/mql5/AureusProvider_v2_compile.log` contains `Result: 0 errors, 0 warnings`.
2. `260501-knj-SUMMARY.md` contains final coverage matrix marks for B-01..B-30, profile checklists, function-level checklists, scenario matrix, deferred rationale table, no DB changes, GitNexus/fallback evidence.
3. Static grep/diff confirms no global stale close, no hard-coded magic decision branch, no external config/DSL/hot reload, and command path non-regression.
4. `gitnexus_detect_changes` or CLI/fallback detects only expected MQL5 provider and summary artifacts.
</verification>

<success_criteria>
- `mql5/AureusProvider_v2.mq5` implements/preserves P-01..P-20 with evidence.
- Every old behavior/rule row B-01..B-30 is marked KEPT, CHANGED, DEFERRED, N/A, or BLOCKED with evidence/rationale; no blank final mark exists.
- `conservative`, `trend_runner`, `breakout_protect`, and `basket_escape` each satisfy their required primitive checklist or explicitly justify defer/change.
- Command handlers and unsupported symbol behavior remain unchanged.
- No database files are modified.
- Compile is 0 errors and 0 warnings.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260501-knj-refactor-strategy-aware-position-managem/260501-knj-SUMMARY.md`.
</output>
