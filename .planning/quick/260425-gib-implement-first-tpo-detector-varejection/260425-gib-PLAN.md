---
phase: quick-260425-gib-implement-first-tpo-detector-varejection
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/signals/tpo_detectors.py
  - services/aureus-signal/tests/test_tpo_detectors.py
autonomous: true
requirements:
  - QUICK-260425-GIB
must_haves:
  truths:
    - "VARejectionDetector nhận context output từ TPOContextBuilder và trả candidate valid cho long reclaim VAL hợp lệ."
    - "VARejectionDetector trả candidate valid cho short reject VAH hợp lệ theo logic đối xứng."
    - "Detector không tạo candidate valid khi thiếu D1/H1/M30 context bắt buộc hoặc history_guard stale/missing."
    - "Detector không tạo candidate valid khi context conflict rõ ràng giữa side được phát hiện và D1 bias."
    - "Detector luôn có reasons giải thích điều kiện chính và shape không được dùng làm gate duy nhất."
    - "Không có thay đổi DB/schema/seed strategy/strategy tag/trade execution/production integration."
  artifacts:
    - path: "services/aureus-signal/engine/signals/tpo_detectors.py"
      provides: "VARejectionDetector và output candidate dict cho setup va_rejection"
    - path: "services/aureus-signal/tests/test_tpo_detectors.py"
      provides: "Unit tests cho long valid, short valid, missing context invalid, conflict invalid, reasons, shape not sole gate"
  key_links:
    - from: "services/aureus-signal/engine/signals/tpo_context.py"
      to: "services/aureus-signal/engine/signals/tpo_detectors.py"
      via: "VARejectionDetector.detect(context, previous_close, current_close) đọc context['timeframes'] và context['bias']"
      pattern: "context\[\"timeframes\"\]"
    - from: "services/aureus-signal/tests/test_tpo_detectors.py"
      to: "services/aureus-signal/engine/signals/tpo_detectors.py"
      via: "import VARejectionDetector và assert candidate contract"
      pattern: "from engine\.signals\.tpo_detectors import VARejectionDetector"
---

<objective>
Implement first TPO detector only: `VARejectionDetector`.

Purpose: Convert existing `TPOContextBuilder` output into a deterministic va_rejection setup candidate with explicit reasons, while keeping TPO indicator/context/history pure and avoiding premature strategy/production wiring.

Output: New detector module plus targeted unit tests. No DB, schema, seed strategy, strategy tag, trade execution, scorer, bridge, breakout detector, trend pullback detector, or production integration changes.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md
@D:/Aureus/services/aureus-signal/engine/signals/tpo_context.py
@D:/Aureus/services/aureus-signal/engine/signals/tpo_history.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_context.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_history.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py

<interfaces>
Existing context contract from `TPOContextBuilder.build(...)`:
```python
{
    "timeframes": {
        "D1": {
            "poc": float,
            "vah": float,
            "val": float,
            "shape": str | None,
            "shape_confidence_pct": float | None,
            "price_location": "near_poc" | "above_vah" | "below_val" | "inside_value_area",
            "distance_to_poc_ticks": float,
            "distance_to_vah_ticks": float,
            "distance_to_val_ticks": float,
            "va_width": float,
            # optional when history provided:
            "poc_shift": "unknown" | "flat" | "up" | "down",
            "va_width_change": float | None,
        } | None,
        "H1": {...} | None,
        "M30": {...} | None,
    },
    "bias": {"d1": "bullish" | "bearish" | "neutral"},
    # optional when history provided:
    "history_guard": {
        "is_stale": bool,
        "stale_timeframes": list[str],
        "missing_timeframes": list[str],
    }
}
```

Required detector output contract:
```python
{
    "setup": "va_rejection",
    "side": "long" | "short" | None,
    "valid": bool,
    "score": float,
    "entry_zone": [float, float] | None,
    "invalidation": float | None,
    "reasons": list[str],
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add focused VA rejection detector tests first</name>
  <files>services/aureus-signal/tests/test_tpo_detectors.py</files>
  <behavior>
    - Long valid: previous_close is below H1 or M30 VAL, current_close reclaims above that VAL, current_close remains at/below or near POC, D1 bias is bullish/neutral, candidate valid long with reasons.
    - Short valid: previous_close is above H1 or M30 VAH, current_close rejects below that VAH, current_close remains at/above or near POC, D1 bias is bearish/neutral, candidate valid short with reasons.
    - Missing context invalid: any required D1/H1/M30 timeframe missing returns valid False and no side candidate.
    - Conflicting context invalid: long with D1 bearish or short with D1 bullish returns valid False and reasons explain conflict.
    - Shape not sole gate: a context with supportive shape but no VAL/VAH reclaim/reject price relation remains invalid; a valid price relation with non-preferred shape can still be valid with lower/support-neutral score.
    - Reasons present: every valid and invalid candidate has non-empty reasons.
  </behavior>
  <action>Create `test_tpo_detectors.py` using the same lightweight import/sys.path style as existing TPO tests. Import only `VARejectionDetector`. Build context fixtures matching `TPOContextBuilder` output shape; do not call DB, strategies, seed strategy, or trade execution code. Tests should fail before implementation because `engine.signals.tpo_detectors` does not exist.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-signal/tests/test_tpo_detectors.py -q</automated>
  </verify>
  <done>Targeted tests encode long valid, short valid, missing context invalid, conflicting context invalid/no candidate, reasons present, and shape-not-sole-gate behavior.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement VARejectionDetector only</name>
  <files>services/aureus-signal/engine/signals/tpo_detectors.py</files>
  <behavior>
    - `detect(context, previous_close, current_close)` consumes the context dict produced by `TPOContextBuilder.build`.
    - Long condition: previous close below H1 or M30 VAL; current close reclaimed above same VAL; current close at/below POC or near POC using context distance fields; D1 bias not bearish.
    - Short condition: previous close above H1 or M30 VAH; current close rejected below same VAH; current close at/above POC or near POC using context distance fields; D1 bias not bullish.
    - Missing D1/H1/M30 context, stale/missing `history_guard` when present, or obvious long/short conflict returns invalid candidate with reasons and no trade tag.
    - Shape is only a small score/reason modifier, never sufficient by itself and never mandatory when price/context conditions are valid.
  </behavior>
  <action>Create `VARejectionDetector` in new `tpo_detectors.py`. Keep it simple: no base class hierarchy, no scorer framework, no breakout/trend detector, no strategy tag emission. If editing any existing symbol becomes necessary, first run GitNexus impact analysis for that symbol and report blast radius; preferred path is no existing symbol edits. Candidate should always include `setup`, `side`, `valid`, `score`, `entry_zone`, `invalidation`, and `reasons`. Invalid candidates should set `valid=False`, `side=None`, `entry_zone=None`, `invalidation=None`, `score=0.0`, and explain why. Do not modify `tpo_context.py`, `tpo_history.py`, `tpo.py`, `seed_strategies.py`, DB/schema/migrations, or trade execution files unless a blocking test failure proves it is unavoidable.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-signal/tests/test_tpo_detectors.py services/aureus-signal/tests/test_tpo_context.py services/aureus-signal/tests/test_tpo_history.py -q</automated>
  </verify>
  <done>`VARejectionDetector` passes detector tests and does not regress existing TPO context/history tests; only the new detector module is added in production code.</done>
</task>

<task type="auto">
  <name>Task 3: Verify scope and no premature integrations</name>
  <files>services/aureus-signal/engine/signals/tpo_detectors.py, services/aureus-signal/tests/test_tpo_detectors.py</files>
  <action>Run focused regression and scope checks. Per `CLAUDE.md`, run GitNexus detect changes before any commit to confirm affected scope is limited to expected detector/test files. Do not add strategy tags to seed strategies, do not wire detector into live signal flow, do not touch DB/schema/migrations, and do not create breakout/trend pullback/scorer/strategy bridge code.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-signal/tests/test_tpo_detectors.py services/aureus-signal/tests/test_tpo_context.py services/aureus-signal/tests/test_tpo_history.py services/aureus-signal/tests/test_tpo_signal.py -q</automated>
    <automated>git -C D:/Aureus diff --name-only -- services/aureus-signal/engine/signals services/aureus-signal/engine/strategies services/aureus-signal/tests db prisma migrations</automated>
  </verify>
  <done>Focused pytest suite passes; GitNexus change detection was attempted/documented per CLAUDE.md, or fallback scoped git diff was used if the CLI/tool is unavailable; scope shows only expected detector/test changes and no DB/schema/seed strategy/strategy tag/trade execution/live integration files changed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| TPOContextBuilder output → VARejectionDetector | Detector consumes in-memory derived market context; malformed/missing context must not produce candidate. |
| Detector candidate → future strategy/scorer layers | This quick task must not emit live strategy tags or trade execution payloads. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-gib-01 | Tampering | `VARejectionDetector.detect` context input | mitigate | Validate required `timeframes.D1/H1/M30` and reject missing/malformed required levels with explicit reasons. |
| T-260425-gib-02 | Information Disclosure | Detector reasons | accept | Reasons contain only derived market/context facts, no secrets or PII. |
| T-260425-gib-03 | Elevation of Privilege | Future strategy integration boundary | mitigate | Do not emit strategy tags, seed strategy entries, or trade execution payloads in this plan. |
| T-260425-gib-04 | Denial of Service | Detector runtime | mitigate | Keep deterministic O(1) checks over D1/H1/M30 only; no loops over candles/history. |
</threat_model>

<verification>
Run:
```bash
cd D:/Aureus && python -m pytest services/aureus-signal/tests/test_tpo_detectors.py services/aureus-signal/tests/test_tpo_context.py services/aureus-signal/tests/test_tpo_history.py services/aureus-signal/tests/test_tpo_signal.py -q
```
Before commit, run:
```text
gitnexus_detect_changes(scope="all")
```
If any existing function/class/method must be edited, run `gitnexus_impact({target: "<symbol>", direction: "upstream"})` before editing and include blast radius in the execution summary.
</verification>

<success_criteria>
- Long valid VA rejection candidate works from `TPOContextBuilder`-shaped context.
- Short valid VA rejection candidate works from `TPOContextBuilder`-shaped context.
- Missing D1/H1/M30 context returns invalid/no candidate.
- Stale or missing history guard, when present, returns invalid/no candidate.
- Conflicting context returns invalid/no candidate.
- Every candidate includes non-empty `reasons`.
- Shape is not the sole gate: supportive shape alone cannot validate; valid price/context relation is not rejected only because shape is non-preferred.
- No DB/schema/migration changes.
- No seed strategy changes.
- No strategy tag emission or strategy bridge.
- No trade execution or production live-flow wiring.
- No breakout detector, no trend pullback detector.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-gib-implement-first-tpo-detector-varejection/260425-gib-SUMMARY.md`.
</output>
