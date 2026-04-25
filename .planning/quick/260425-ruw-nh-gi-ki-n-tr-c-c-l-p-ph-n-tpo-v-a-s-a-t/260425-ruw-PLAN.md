---
phase: 260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md
autonomous: true
requirements:
  - QUICK-260425-RUW
must_haves:
  truths:
    - "Tài liệu advisory đánh giá trung lập vấn đề TPO CPU/stuck và fix vừa áp dụng theo đúng 4 bước của user"
    - "Tài liệu so sánh peak-pair cap + existing level cap/delta prefix-sum với các hướng thay thế khả thi"
    - "Tài liệu đưa ra khuyến nghị cụ thể và implications cho requirement/test để làm cơ sở implement/test tiếp theo"
  artifacts:
    - path: ".planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md"
      provides: "Independent architecture consultant advisory for TPO stuck fix"
      min_lines: 80
      contains: "Neutral Listing"
  key_links:
    - from: ".planning/debug/tpo-signal-stuck.md"
      to: ".planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md"
      via: "evidence and verification summary"
      pattern: "981\.95ms|134\.40ms|67\.52ms|consumer lag 0"
    - from: "services/aureus-signal/engine/signals/tpo.py"
      to: ".planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md"
      via: "current algorithm/fix assessment"
      pattern: "peak-pair cap|64 strongest peaks|max_levels|prefix-sum"
---

<objective>
Tạo một architecture advisory document độc lập cho phần TPO vừa sửa, theo đúng framework 4 bước của user: Neutral Listing, Attribute Mapping, Contextual Recommendation, Adversarial Mode.

Purpose: Biến evidence debug/fix TPO CPU-stuck thành đánh giá kiến trúc có thể dùng làm cơ sở quyết định, requirement, và kiểm thử tiếp theo mà không sửa source code.
Output: `.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/debug/tpo-signal-stuck.md
@services/aureus-signal/engine/signals/tpo.py
@services/aureus-signal/engine/live_engine.py

<interfaces>
Relevant implementation facts the advisory must account for:

From `services/aureus-signal/engine/signals/tpo.py`:
- `TPOSignal.calculate()` computes D1, H1, and M30 TPO payloads every calculation and stores `state_obj.tpo_profile`.
- `_build_levels_and_counts()` uses `AUREUS_TPO_MAX_LEVELS` default `5000`, caps level count, and builds counts via delta prefix-sum.
- `_classify_shape()` scans levels/counts, detects peaks, caps B-shape peak-pair candidates to the strongest 64 peaks, then runs pair comparison.
- `_build_profile_from_counts()` derives POC/VAH/VAL from counts.

From `services/aureus-signal/engine/live_engine.py`:
- `execute_signals_for_candle()` synchronously calls each signal calculator during candle processing.
- TPO slow logs emit when `signal_name == "tpo"` and elapsed time exceeds `AUREUS_TPO_SLOW_SIGNAL_MS`, default `250ms`.
- Signal payload publication happens after signal calculation; a stuck/slow TPO calculation can delay signal emission and ACK flow.
- `indicator_snapshot` for Telegram is built after signals, using `build_indicator_snapshot_for_telegram(state, m1_df=df)`.

From `.planning/debug/tpo-signal-stuck.md`:
- Root cause confirmed: unbounded nested peak-pair comparison in `_classify_shape()` with `max_levels=5000` could produce ~1s classification per block, repeated for D1/H1/M30.
- Fix applied: cap peak-pair comparison to 64 strongest peaks, sorted back by price index before pair scanning.
- Verification evidence: synthetic `_classify_shape` n=5000 improved from ~981.95ms to ~134.40ms; live-like `TPOSignal.calculate` with max_levels=5000 averaged ~67.52ms/max ~136.88ms; focused TPO live integration tests passed; docker runtime with TPO enabled showed stable CPU, all symbols Engine ready, no TPO errors/slow logs, and BTCUSD/ETHUSD candle consumer lag 0.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Draft independent TPO architecture advisory using exact 4-step framework</name>
  <files>.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md</files>
  <action>Create the advisory document in Vietnamese. Do not modify source code. Use exactly these top-level sections in order: `## 1. Neutral Listing`, `## 2. Attribute Mapping`, `## 3. Contextual Recommendation`, `## 4. Adversarial Mode`, then `## Concrete Recommendation`, `## Requirements & Test Implications`. The advisory must evaluate the current applied path (peak-pair cap + existing max-level cap + delta prefix-sum) against at least these alternatives: lower global `AUREUS_TPO_MAX_LEVELS`, fully incremental/session-level TPO cache, approximate/histogram binning, background/off-thread TPO computation, disabling TPO/live tag kill-switch, and removing/deferring shape classification. Keep tone as independent architecture consultant: neutral first, recommendation later. Cite concrete evidence from the debug file, including pre/post timings and docker/runtime verification.</action>
  <verify>
    <automated>test -f .planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md && python - <<'PY'
from pathlib import Path
p=Path('.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md')
s=p.read_text(encoding='utf-8')
required=['## 1. Neutral Listing','## 2. Attribute Mapping','## 3. Contextual Recommendation','## 4. Adversarial Mode','## Concrete Recommendation','## Requirements & Test Implications','981.95ms','134.40ms','67.52ms','64']
missing=[x for x in required if x not in s]
assert not missing, missing
PY</automated>
  </verify>
  <done>Advisory exists, follows exact 4-step framework, compares current fix with alternatives, includes concrete recommendation and requirement/test implications.</done>
</task>

<task type="auto">
  <name>Task 2: Add decision-quality implications and adversarial checks</name>
  <files>.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md</files>
  <action>Review and strengthen the advisory so it can become a basis for implementation/testing. Include: (1) explicit acceptance thresholds for TPO runtime in live-like benchmark and docker runtime observation, (2) risk that peak-pair cap may alter weak B-shape detection and how tests should cover it, (3) when to escalate from the current fix to incremental caching/background computation, (4) monitoring hooks already present in live_engine (`AUREUS_TPO_SLOW_SIGNAL_MS`, profiling stream/logs, Redis consumer lag), and (5) a final recommended path with short rationale. Avoid speculative new features; keep implications tied to existing code and observed evidence.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
s=Path('.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md').read_text(encoding='utf-8')
checks=['AUREUS_TPO_SLOW_SIGNAL_MS','consumer lag','B-shape','incremental','background','acceptance','monitoring','khuyến nghị']
missing=[c for c in checks if c.lower() not in s.lower()]
assert not missing, missing
PY</automated>
  </verify>
  <done>Document contains actionable thresholds, known risks, escalation criteria, monitoring/test implications, and a clear final recommendation.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Documentation-only quick task | No runtime trust boundary changes; reads local debug/source context and writes planning advisory only. |
| Advisory to future implementation | Risk is mis-specification: future executor may over-apply recommendations if advisory is vague. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-ruw-01 | I | Architecture advisory | mitigate | Do not include secrets or environment values beyond non-secret tuning variable names already in source (`AUREUS_TPO_MAX_LEVELS`, `AUREUS_TPO_SLOW_SIGNAL_MS`). |
| T-260425-ruw-02 | T | Future requirements derived from advisory | mitigate | Tie recommendations to observed evidence and explicit test implications; separate current recommendation from escalation options. |
| T-260425-ruw-03 | D | Future TPO live runtime | mitigate | Advisory must preserve performance acceptance criteria and monitoring hooks to prevent reintroducing candle-loop stall. |
</threat_model>

<verification>
Run both task automated checks. No source-code tests are required because this plan is documentation/advisory only and must not modify source code.
</verification>

<success_criteria>
- One advisory document is created at `.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-ARCHITECTURE-ADVISORY.md`.
- The advisory uses exactly the user’s 4-step independent architecture consultant framework.
- It evaluates the just-applied TPO fix against realistic alternatives and gives a concrete recommendation.
- It includes requirements/test implications suitable for later implementation/testing.
- No source code is modified.
</success_criteria>

<output>
After completion, create `.planning/quick/260425-ruw-nh-gi-ki-n-tr-c-c-l-p-ph-n-tpo-v-a-s-a-t/260425-ruw-SUMMARY.md`.
</output>
