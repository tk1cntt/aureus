---
phase: 260425-foy-implement-tpo-history-store-from-tpo-pla
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/signals/tpo_history.py
  - services/aureus-signal/engine/signals/tpo_context.py
  - services/aureus-signal/tests/test_tpo_history.py
  - services/aureus-signal/tests/test_tpo_context.py
autonomous: true
requirements:
  - QUICK-260425-FOY
must_haves:
  truths:
    - "TPO history lưu facts D1/H1/M30 có giới hạn length, không tăng vô hạn."
    - "TPO history không append duplicate cùng timeframe và timestamp."
    - "Context có helper poc_shift và va_width_change tính từ 2 snapshot hợp lệ gần nhất."
    - "Context stale/misaligned hoặc thiếu timeframe bắt buộc được guard bằng trạng thái rõ ràng, không crash và không tạo trade tag."
    - "Không có thay đổi DB/schema/seed strategy/detector/trade signal, TPOSignal vẫn là indicator."
  artifacts:
    - path: "services/aureus-signal/engine/signals/tpo_history.py"
      provides: "Bounded TPOHistoryStore + snapshot facts/helpers"
      exports: ["TPOHistoryStore"]
    - path: "services/aureus-signal/engine/signals/tpo_context.py"
      provides: "TPOContextBuilder dùng history để bổ sung poc_shift, va_width_change và stale safeguards"
      exports: ["TPOContextBuilder"]
    - path: "services/aureus-signal/tests/test_tpo_history.py"
      provides: "Unit tests cho append/dedup/bounded/history helpers/stale detection"
    - path: "services/aureus-signal/tests/test_tpo_context.py"
      provides: "Regression tests cho context hiện có và history-derived fields"
  key_links:
    - from: "services/aureus-signal/engine/signals/tpo_context.py"
      to: "services/aureus-signal/engine/signals/tpo_history.py"
      via: "optional TPOHistoryStore import/use in build()"
      pattern: "TPOHistoryStore"
    - from: "services/aureus-signal/tests/test_tpo_history.py"
      to: "services/aureus-signal/engine/signals/tpo_history.py"
      via: "direct unit tests"
      pattern: "TPOHistoryStore"
    - from: "services/aureus-signal/tests/test_tpo_context.py"
      to: "services/aureus-signal/engine/signals/tpo_context.py"
      via: "TPOContextBuilder.build(..., history=...) or compatible optional argument"
      pattern: "poc_shift|va_width_change|is_stale"
---

<objective>
Implement TPO history store từ TPO implementation plan Slice 2, giữ phạm vi surgical: bounded D1/H1/M30 history, duplicate prevention, helpers `poc_shift`/`va_width_change`, stale context safeguards, và unit tests.

Purpose: Chuẩn bị feature/context layer cho detector tương lai mà không biến `TPOSignal` thành strategy signal.
Output: `tpo_history.py` mới, mở rộng nhỏ trong `tpo_context.py`, tests targeted.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md
@D:/Aureus/services/aureus-signal/engine/signals/tpo.py
@D:/Aureus/services/aureus-signal/engine/signals/tpo_context.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_context.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py

<interfaces>
Existing `TPOContextBuilder.build(tpo_value: Dict[str, Any], close: float) -> Dict[str, Any>` returns:
- `timeframes`: keys `D1`, `H1`, `M30`, each timeframe has `poc`, `vah`, `val`, `shape`, `shape_confidence_pct`, `price_location`, distance ticks, `va_width` or `None`.
- `bias`: currently `{"d1": "bullish" | "bearish" | "neutral"}`.

Existing `TPOSignal` must remain `SignalType.INDICATOR` and output `{"tag": "tpo", "value": {"tpo_d1", "tpo_h1", "tpo_m30"}, "t": ts}`. Do not integrate the new store into `TPOSignal` unless a test proves no alternative.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create bounded TPO history store</name>
  <files>services/aureus-signal/engine/signals/tpo_history.py, services/aureus-signal/tests/test_tpo_history.py</files>
  <behavior>
    - Appending valid D1/H1/M30 blocks stores snapshot facts: `t`, `POC`, `VAH`, `VAL`, `shape`, `shape_confidence_pct`, `va_width`.
    - Appending the same timeframe + timestamp twice does not duplicate or inflate length.
    - Per-timeframe history is bounded by configured max length; oldest entries are dropped first.
    - `poc_shift(tf)` returns `up`, `down`, `flat`, or `unknown` from the latest two snapshots using tick-size tolerance.
    - `va_width_change(tf)` returns numeric latest width minus previous width, or `None` when insufficient data.
    - Stale/misaligned guard returns false/flagged when required D1/H1/M30 timestamps are missing or older than max age.
  </behavior>
  <action>First write failing tests in `test_tpo_history.py`. Then create `TPOHistoryStore` in new `tpo_history.py` only. Keep it in-memory and dependency-free. Use simple dict/list storage shaped like the TPO plan: `{"D1": [], "H1": [], "M30": []}`. Normalize lowercase/uppercase timeframe inputs to uppercase. Ignore invalid/missing TPO blocks without crashing. Do not touch DB, schema, seed strategies, detectors, or `TPOSignal`. Because this creates a new symbol and does not modify existing symbols, no GitNexus impact is required for this task; still run `gitnexus_detect_changes()` before any commit if committing later.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_history.py -q</automated>
  </verify>
  <done>`test_tpo_history.py` passes and proves bounded history, duplicate prevention, poc_shift, va_width_change, stale/misaligned guard, and no trade tags.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add optional history-derived fields to TPOContextBuilder</name>
  <files>services/aureus-signal/engine/signals/tpo_context.py, services/aureus-signal/tests/test_tpo_context.py</files>
  <behavior>
    - Existing `TPOContextBuilder().build(tpo_value, close)` tests remain backward compatible.
    - When optional history is supplied, each timeframe context includes `poc_shift` and `va_width_change` from the store.
    - Missing/invalid timeframe blocks still return `None` for that timeframe and `bias.d1 == neutral`.
    - Stale/misaligned history adds explicit context guard fields such as `is_stale`/`stale_timeframes` or equivalent, without emitting any strategy/trade tag.
  </behavior>
  <action>Before editing existing `TPOContextBuilder` methods, run GitNexus impact analysis for `TPOContextBuilder`, `TPOContextBuilder.build`, and any private method you change; report direct callers and risk in the execution summary. Then extend `build` with optional arguments only, e.g. `history: Optional[TPOHistoryStore] = None` and stale settings if needed, preserving existing call sites. Import `TPOHistoryStore` locally or via typing-safe import without circular dependency. Add history-derived fields to each non-None timeframe block. Keep stale safeguards as context metadata only; do not add detectors, strategy tags, seed strategy changes, or `TPOSignal` integration.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_context.py tests/test_tpo_history.py -q</automated>
  </verify>
  <done>Context tests prove backward compatibility plus optional history fields and stale safeguards; `TPOSignal.signal_type` remains indicator and no trade tags appear.</done>
</task>

<task type="auto">
  <name>Task 3: Run targeted regression and scope guard checks</name>
  <files>services/aureus-signal/tests/test_tpo_signal.py, services/aureus-signal/tests/test_tpo_context.py, services/aureus-signal/tests/test_tpo_history.py</files>
  <action>Run the focused TPO test suite to ensure the new history layer does not change current indicator behavior. Then run GitNexus change detection before finishing/committing to confirm only expected files/symbols changed. If `gitnexus_detect_changes` reports unexpected DB/schema/seed strategy/detector/trade signal files, stop and revert those unrelated changes.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_history.py tests/test_tpo_context.py tests/test_tpo_signal.py -q</automated>
    <automated>git -C D:/Aureus diff --name-only -- services/aureus-signal/engine/signals services/aureus-signal/engine/strategies services/aureus-signal/tests db prisma migrations</automated>
  </verify>
  <done>All targeted tests pass; GitNexus scope check was attempted/documented per CLAUDE.md, or fallback scoped git diff was used if the CLI/tool is unavailable; scope shows only expected history/context/test changes and no DB/schema/seed strategy/detector/trade signal changes exist.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| indicator facts -> context/history | TPO blocks may be missing, malformed, stale, duplicated, or misaligned across D1/H1/M30. |
| in-memory state -> future detectors | Future detector logic may consume context fields; stale/duplicate history must not look like fresh signal evidence. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-foy-01 | T | TPOHistoryStore.append | mitigate | Validate required fields and ignore invalid blocks without mutating history. |
| T-260425-foy-02 | D | TPOHistoryStore storage | mitigate | Bound per-timeframe length and deduplicate by timeframe+timestamp. |
| T-260425-foy-03 | I | TPOContextBuilder history metadata | mitigate | Expose stale/misaligned flags so future consumers can reject unsafe context. |
| T-260425-foy-04 | E | TPO context -> trade logic | accept | This plan does not create detectors, strategy tags, seed strategies, or trade execution paths. |
</threat_model>

<verification>
Run targeted checks:

```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_history.py tests/test_tpo_context.py tests/test_tpo_signal.py -q
```

Before any commit, run GitNexus scope check per project rules and confirm no unexpected affected flows. If the GitNexus detect_changes command/tool is unavailable in this runtime, document the limitation and use scoped `git diff --name-only` plus targeted tests as fallback verification.
</verification>

<success_criteria>
- Bounded history exists for D1/H1/M30 with configurable per-timeframe max length.
- Duplicate prevention works for same timeframe + timestamp.
- `poc_shift` helper reports up/down/flat/unknown from recent snapshots.
- `va_width_change` helper reports latest-minus-previous VA width or `None` when insufficient data.
- Stale/misaligned context safeguards exist and are covered by unit tests.
- Existing context behavior and `TPOSignal` indicator tests remain passing.
- No DB/schema changes.
- No seed strategy changes.
- No detector files or detector logic.
- No trade signal tags or production strategy integration.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-foy-implement-tpo-history-store-from-tpo-pla/260425-foy-SUMMARY.md`.
</output>
