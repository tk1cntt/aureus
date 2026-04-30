---
phase: quick-260430-rak-support-managing-and-dca-for-all-symbols
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
autonomous: true
requirements:
  - QUICK-260430-RAK
must_haves:
  truths:
    - "Provider DCA/CISD management scans every configured symbol in InpSymbols, independent of the chart symbol where the EA is attached."
    - "DCA remains scoped by symbol and magic so one strategy group cannot DCA another symbol or another strategy magic."
    - "Duplicate strategy order guard remains scoped by symbol and magic for both open positions and pending orders."
    - "MetaEditor compile finishes with 0 errors and 0 warnings."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Multi-symbol DCA/CISD scanning and management inside the provider timer loop"
      contains: "CheckDCAEntryConditionFromCISD"
    - path: "mql5/AureusProvider_v2_compile.log"
      provides: "MetaEditor compile evidence"
      contains: "0 error(s), 0 warning(s)"
  key_links:
    - from: "mql5/AureusProvider_v2.mq5:OnTimer"
      to: "mql5/AureusProvider_v2.mq5:CheckDCAEntryConditionFromCISD"
      via: "loop over g_contexts / InpSymbols instead of a single _Symbol call"
      pattern: "for\\(.*g_symbolCount.*CheckDCAEntryConditionFromCISD"
    - from: "mql5/AureusProvider_v2.mq5:CheckDCAEntryConditionFromCISD"
      to: "mql5/AureusProvider_v2.mq5:UpdateCISDDCAH1State"
      via: "explicit symbol argument used for CISD H1 and LTF scans"
      pattern: "UpdateCISDDCAH1State\\(.*symbol"
    - from: "mql5/AureusProvider_v2.mq5:CheckDCAEntryConditionFromCISD"
      to: "mql5/AureusProvider_v2.mq5:DoDCA"
      via: "DoDCA(direction, symbol, magic) with magic resolved from same symbol and position direction"
      pattern: "DoDCA\\(.*symbol.*magic"
---

<objective>
Support DCA and provider-local CISD management for every symbol configured in `InpSymbols`, regardless of which chart symbol the EA is attached to.

Purpose: The provider already streams candles for all configured symbols and accepts orders for allowed symbols, but the current DCA/CISD timer path is chart-symbol-bound through `_Symbol`. This plan makes the DCA/management path multi-symbol while preserving the recent safety fixes.

Output: A surgical update to `mql5/AureusProvider_v2.mq5` plus compile evidence showing 0 errors and 0 warnings.
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
struct SymbolContext
  {
   string            symbol;
   datetime          lastCandleTime;
   int               candlesSent;
   bool              initialBackfillDone;
  };

struct SetupInfo
  {
   bool              active;
   double            priceLevel;
   datetime          setupTime;
  };

int FindContextIndex(string symbol);
void DoDCA(int order_type_signal, string symbol, long magic);
long FindDCAMagicForSymbolDirection(string symbol, ENUM_POSITION_TYPE position_type);
void UpdateCISDDCAH1State();
void CheckDCAEntryConditionFromCISD();
void OnTimer();
```

Current chart-bound problem areas:
- `UpdateCISDDCAH1State()` reads H1 bars using `_Symbol`.
- `CheckDCAEntryConditionFromCISD()` stores static setup state once globally and scans `_Symbol` / `_Period` only.
- `OnTimer()` calls `CheckDCAEntryConditionFromCISD()` once after candle polling, so only the chart symbol gets DCA gate processing.

Recent behavior that must be preserved:
- `DoDCA(int order_type_signal, string symbol, long magic)` already filters positions by both `POSITION_SYMBOL == symbol` and `POSITION_MAGIC == magic` before opening/TP-modifying DCA positions.
- `FindDCAMagicForSymbolDirection(string symbol, ENUM_POSITION_TYPE position_type)` resolves magic from the same symbol and direction.
- `ExecuteOpenOrder()` duplicate guard rejects active positions and pending orders using both symbol and magic; do not widen this to magic-only or symbol-only.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Convert provider-local CISD/DCA state to symbol-scoped scanning</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Before editing, attempt GitNexus impact analysis for `OnTimer`, `CheckDCAEntryConditionFromCISD`, `UpdateCISDDCAH1State`, `DoDCA`, and any helper you touch. Report direct callers, affected processes, and risk level; if MQL5 symbols are not indexed, document the failed tool result/fallback in the task summary and continue with code-local analysis. Then make the smallest code change needed so CISD/DCA scans every `g_contexts[i].symbol` from `InpSymbols`, not only `_Symbol`. Prefer changing `UpdateCISDDCAH1State` and `CheckDCAEntryConditionFromCISD` to accept an explicit `string symbol` parameter, and call them from an `OnTimer` loop over `g_symbolCount`. Replace `_Symbol` usages inside these DCA/CISD helper paths with the explicit symbol. Preserve `_Period` unless compile/runtime constraints force a specific timeframe; do not add new configurable inputs. Ensure per-symbol CISD state does not bleed across symbols: any previously global/static DCA gate state such as H1 signal type/time, scan start time, last trade signal time, and bull/bear setup state must be indexed per configured symbol or stored in a symbol-scoped struct/arrays sized from `g_symbolCount`. Keep scope surgical: do not refactor unrelated order execution, socket, backfill, or reporting code.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""</automated>
  </verify>
  <done>`OnTimer()` processes DCA/CISD for every configured symbol; CISD/DCA state is symbol-scoped; no code path in `CheckDCAEntryConditionFromCISD` or `UpdateCISDDCAH1State` depends on `_Symbol` for symbol identity.</done>
</task>

<task type="auto">
  <name>Task 2: Preserve symbol+magic safety invariants while validating compile output</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5, D:/Aureus/mql5/AureusProvider_v2_compile.log</files>
  <action>Review the implementation specifically against these invariants: `DoDCA` must still filter and modify positions by both `symbol` and `magic`; `FindDCAMagicForSymbolDirection` must still resolve magic for the same `symbol` and direction; `ExecuteOpenOrder` duplicate strategy guard must still reject both positions and pending orders only when both symbol and magic match. Do not change those semantics while making multi-symbol DCA work. Compile using the MetaEditor command from `mql5/Build_Rules.md` and fix until the compile log reports 0 errors and 0 warnings. If compile produces warnings, fix the source rather than accepting the warnings. Before finishing, run `gitnexus_detect_changes()` if available; if unavailable for this environment or MQL5 scope, document the fallback and manually confirm only `mql5/AureusProvider_v2.mq5` and compile log/planning artifacts changed.</action>
  <verify>
    <automated>cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log"" && node -e "const fs=require('fs'); const p='D:/Aureus/mql5/AureusProvider_v2_compile.log'; const s=fs.readFileSync(p,'utf8'); if(!/0 error\(s\), 0 warning\(s\)|0 errors?, 0 warnings?/i.test(s)){ console.error(s); process.exit(1); }"</automated>
  </verify>
  <done>Compile log confirms 0 errors and 0 warnings; symbol+magic DCA and duplicate-order guard semantics are unchanged; final summary includes GitNexus impact/detect_changes results or explicit fallback notes.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gateway to provider command handling | Incoming order commands are untrusted socket payloads and must remain constrained to allowed symbols and strategy ownership. |
| Provider timer to broker trade operations | Timer-driven DCA can open or modify live trades, so symbol/magic scoping is the safety boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260430-rak-01 | T | `CheckDCAEntryConditionFromCISD` / `DoDCA` | mitigate | Scope CISD/DCA state and execution by explicit symbol; call `DoDCA(order_type_signal, symbol, magic)` only after magic is resolved for the same symbol and direction. |
| T-260430-rak-02 | E | `ExecuteOpenOrder` duplicate guard | mitigate | Preserve existing duplicate active strategy guard matching both `POSITION_SYMBOL/ORDER_SYMBOL` and `POSITION_MAGIC/ORDER_MAGIC`; do not change it to global magic-only. |
| T-260430-rak-03 | D | `OnTimer` multi-symbol scan | accept | Additional per-symbol timer work is bounded by `g_symbolCount` and existing candle polling already loops all symbols; keep implementation surgical and avoid expensive new history scans beyond existing CISD gate logic. |
</threat_model>

<verification>
Run MetaEditor compile from `mql5/Build_Rules.md` and require `D:/Aureus/mql5/AureusProvider_v2_compile.log` to report 0 errors and 0 warnings. Also review final diff to ensure only `D:/Aureus/mql5/AureusProvider_v2.mq5` and expected planning/compile artifacts changed.
</verification>

<success_criteria>
- DCA/CISD gate runs for all symbols in `InpSymbols`, not just the chart `_Symbol`.
- Per-symbol DCA gate state prevents one symbol's H1/LTF setup from triggering another symbol's DCA.
- DCA remains scoped by symbol + magic.
- Duplicate strategy order guard remains scoped by symbol + magic for positions and pending orders.
- MetaEditor compile reports 0 errors and 0 warnings.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260430-rak-support-managing-and-dca-for-all-symbols/260430-rak-SUMMARY.md`.
</output>
