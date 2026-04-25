---
phase: 260425-nub-fix-l-i-trend-calc-error-could-not-conve
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/signals/trend.py
  - services/aureus-signal/tests/test_trend_categorical_values.py
autonomous: true
requirements:
  - QUICK-260425-NUB
must_haves:
  truths:
    - "BTCUSD candle processing at t=1777120200 no longer logs or raises trend calc error: could not convert string to float: 'LOW'."
    - "Trend calculation keeps existing numeric EMA/close semantics when inputs are numeric."
    - "Categorical signal values such as LOW are safely ignored or coerced to missing only at numeric-conversion boundaries, not treated as numeric trend data."
  artifacts:
    - path: "services/aureus-signal/engine/signals/trend.py"
      provides: "Surgical guard around TrendSignal numeric conversion path"
      contains: "class TrendSignal"
    - path: "services/aureus-signal/tests/test_trend_categorical_values.py"
      provides: "Regression coverage for categorical string LOW entering trend calculation"
      contains: "LOW"
  key_links:
    - from: "services/aureus-signal/engine/live_engine.py"
      to: "services/aureus-signal/engine/signals/trend.py"
      via: "signal_calc.calculate(df, state, redis_client=r, symbol=symbol)"
      pattern: "signal_calc\.calculate"
    - from: "services/aureus-signal/engine/signals/trend.py"
      to: "services/aureus-signal/tests/test_trend_categorical_values.py"
      via: "pytest regression constructs df with categorical LOW in numeric trend input"
      pattern: "TrendSignal"
---

<objective>
Fix the live signal engine trend calculation failure where a categorical string value (`LOW`) reaches a numeric conversion path and causes `could not convert string to float: 'LOW'` during BTCUSD processing around `t=1777120200`.

Purpose: keep live candle execution resilient to categorical signal metadata leaking into numeric trend inputs without changing trend semantics for valid numeric data.
Output: one surgical trend conversion guard plus a regression test that fails before the fix and passes after it.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@services/aureus-signal/engine/live_engine.py
@services/aureus-signal/engine/signals/trend.py
@services/aureus-signal/engine/signals/structure.py
@services/aureus-signal/tests/test_zigzag_regression.py

<interfaces>
From `services/aureus-signal/engine/live_engine.py`: signal execution calls each signal object as `signal_calc.calculate(df, state, redis_client=r, symbol=symbol)` inside the candle loop. The quick task description names `execute_signals_for_candle`, but this worktree does not contain that symbol; use GitNexus/code search first to confirm whether it exists in the indexed graph or only in another branch/runtime label.

From `services/aureus-signal/engine/signals/trend.py`:
```python
class TrendSignal(BaseSignal):
    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        col_name = f"ema_{self.ema_period}"
        if col_name in df.columns:
            ema_series = df[col_name]
        else:
            ema_series = df['c'].ewm(span=self.ema_period, adjust=False).mean()
        current_ema = float(ema_series.iloc[-1])
        prev_ema = float(ema_series.iloc[-2]) if len(ema_series) > 1 else current_ema
        current_price = float(df['c'].iloc[-1])
```

From `services/aureus-signal/engine/signals/structure.py`: categorical quality values include `"LOW"` (`quality = "HIGH" if body_ratio > 0.8 else "MEDIUM" if body_ratio > 0.5 else "LOW"`), so treat `LOW` as categorical metadata, not a price/EMA value.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Locate exact LOW-to-trend path and write failing regression</name>
  <files>services/aureus-signal/tests/test_trend_categorical_values.py</files>
  <behavior>
    - Test 1: A `TrendSignal(ema_period=3)` call with a DataFrame whose configured EMA column contains a categorical `"LOW"` at the latest candle must not raise `ValueError`.
    - Test 2: When the latest EMA value is categorical but prior values and close are numeric, trend state remains safe (`NEUTRAL` or previous untouched state as implemented by the fix) and no `LOW` is interpreted as a numeric price.
    - Test 3: Existing numeric EMA/close input still returns a normal `htf_trend` payload with `value`, `regime`, `ema_ref`, and `slope`.
  </behavior>
  <action>Use GitNexus first: run `gitnexus_query` for `trend calc LOW execute_signals_for_candle`, then `gitnexus_context`/`gitnexus_impact` on the located trend calculation symbol if available. If GitNexus tools are unavailable in this executor environment, use source search for `execute_signals_for_candle`, `TrendSignal`, `float(`, and `LOW`, then record the limitation in the summary. Add a pytest regression file under `services/aureus-signal/tests/` that imports `TrendSignal`, constructs a minimal dummy state object with `htf_trend` and `market_regime` attributes, and reproduces the current failure by placing string `"LOW"` in the numeric EMA series consumed by `TrendSignal.calculate`. Do not modify production code in this task.</action>
  <verify>
    <automated>cd services/aureus-signal && python -m pytest tests/test_trend_categorical_values.py -q</automated>
  </verify>
  <done>The new regression test file exists, confirms the current LOW conversion failure before production changes, and includes a numeric-control case so the later fix cannot silently disable trend calculation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add surgical numeric coercion guard in TrendSignal</name>
  <files>services/aureus-signal/engine/signals/trend.py, services/aureus-signal/tests/test_trend_categorical_values.py</files>
  <behavior>
    - Categorical strings (`LOW`, `MEDIUM`, `HIGH`, other non-numeric labels) in `ema_{period}` or close input do not raise from `TrendSignal.calculate`.
    - If numeric conversion is impossible for the current candle, `TrendSignal.calculate` returns `None` and leaves state in a safe neutral/no-update condition without fabricating BULLISH/BEARISH values.
    - Fully numeric inputs keep the existing slope/regime calculation behavior.
  </behavior>
  <action>Before editing `TrendSignal.calculate`, run GitNexus impact analysis for `TrendSignal.calculate` or `TrendSignal` with upstream direction and report direct callers/risk in the execution summary; if unavailable, document fallback source-search limitation. Make a minimal change in `services/aureus-signal/engine/signals/trend.py`: use `pd.to_numeric(..., errors="coerce")` or a small local helper around the existing `ema_series.iloc[-1]`, `ema_series.iloc[-2]`, and `df['c'].iloc[-1]` conversions so categorical strings become missing instead of raising. If the current EMA, previous EMA, or current close is missing/non-finite after coercion, return `None` after setting `state_obj.htf_trend`/`market_regime` to a safe neutral value only if the existing early-return path already does so. Do not change threshold constants, bullish/bearish comparisons, returned payload shape for numeric data, or unrelated signals. Keep the fix inside `TrendSignal.calculate` unless discovery proves the exact error comes from a narrower helper.</action>
  <verify>
    <automated>cd services/aureus-signal && python -m pytest tests/test_trend_categorical_values.py -q</automated>
  </verify>
  <done>The LOW regression passes, the numeric-control trend test passes, and the implementation remains limited to the trend numeric conversion boundary.</done>
</task>

<task type="auto">
  <name>Task 3: Run focused signal test suite and scope checks</name>
  <files>services/aureus-signal/engine/signals/trend.py, services/aureus-signal/tests/test_trend_categorical_values.py</files>
  <action>Run focused tests that cover trend/indicator behavior and any existing nearby signal tests that are fast. Also run GitNexus detect changes before any commit or final summary if available, per project instructions; if GitNexus is unavailable, record that limitation. Do not run database tests because this quick fix has no DB changes.</action>
  <verify>
    <automated>cd services/aureus-signal && python -m pytest tests/test_trend_categorical_values.py tests/test_atr_o1.py tests/test_dynamic_amplitude.py -q</automated>
  </verify>
  <done>Focused tests pass, changed files are only `trend.py` plus the new regression test, and the summary records the GitNexus impact/detect_changes result or explicit tool-unavailable fallback.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| market-data/signal metadata → trend calculation | Candle DataFrame values and derived signal columns may contain untrusted categorical strings where numeric trend code expects floats. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-NUB-01 | D | `TrendSignal.calculate` | mitigate | Coerce only numeric trend inputs with invalid values becoming missing, then return safely instead of raising and interrupting candle signal execution. |
| T-260425-NUB-02 | T | `TrendSignal.calculate` | mitigate | Regression test proves categorical `LOW` is not interpreted as numeric EMA/price and numeric semantics remain unchanged. |
</threat_model>

<verification>
Run the automated commands embedded in each task. The final verification command is:

```bash
cd services/aureus-signal && python -m pytest tests/test_trend_categorical_values.py tests/test_atr_o1.py tests/test_dynamic_amplitude.py -q
```
</verification>

<success_criteria>
- The original error `could not convert string to float: 'LOW'` is reproduced by a regression test before the fix and no longer occurs after the fix.
- Trend calculation behavior for valid numeric inputs remains equivalent: same directional state/payload shape and no changed threshold semantics.
- The implementation is surgical: no DB changes, no broad refactor, no unrelated signal behavior changes.
- GitNexus impact analysis and detect-changes checks are performed when available; otherwise the summary explicitly records fallback source-search limitations.
</success_criteria>

<output>
After completion, create `.planning/quick/260425-nub-fix-l-i-trend-calc-error-could-not-conve/260425-nub-SUMMARY.md`
</output>
