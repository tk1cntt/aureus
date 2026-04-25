---
phase: quick-260425-tpc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md
autonomous: true
requirements:
  - QUICK-260425-TPC
must_haves:
  truths:
    - "Người đọc có một đánh giá độc lập theo đúng quy trình 4 bước về report 260425-t9v."
    - "Advisory đánh giá rõ lựa chọn xử lý `_classify_shape` chưa chính xác và thêm `distr`/`distribution_regime`."
    - "Advisory chốt một best choice cụ thể và cập nhật basis yêu cầu/kiểm thử cho implementation tương lai."
  artifacts:
    - path: ".planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md"
      provides: "Independent architecture advisory for TPO shape/distribution report"
      contains: "## 1. Neutral Listing"
  key_links:
    - from: ".planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md"
      to: ".planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md"
      via: "source report evaluation"
      pattern: "distribution_regime|distr|_classify_shape"
---

<objective>
Tạo một tài liệu tư vấn kiến trúc độc lập đánh giá report 260425-t9v về TPO shape/distribution theo đúng 4 bước: Neutral Listing, Attribute Mapping, Contextual Recommendation, Adversarial Mode; sau đó chốt best choice và requirements/test basis cho triển khai sau.

Purpose: giúp quyết định hướng cải thiện `_classify_shape` và thêm `distr`/`distribution_regime` mà không trộn semantics shape, distribution regime, direction signal.
Output: `.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/quick/260425-t9v-ph-n-t-ch-tpo-project-master-c-i-thi-n-c/260425-t9v-REPORT.md
@D:/Aureus/services/aureus-signal/engine/signals/tpo.py
@D:/Aureus/services/aureus-signal/engine/signals/tpo_context.py
@D:/Aureus/services/aureus-signal/engine/signals/tpo_detectors.py

<interfaces>
Current relevant contracts observed during planning:

From `services/aureus-signal/engine/signals/tpo.py`:
- `TPOSignal._build_tpo_block(...)` returns `POC`, `VAH`, `VAL`, `shape`, `shape_confidence_pct`, `shape_scores_pct`.
- `TPOSignal._classify_shape(levels, counts, poc_idx)` returns `(shape, confidence_pct, scores)` for `D`, `B`, `p`, `b`.

From `services/aureus-signal/engine/signals/tpo_context.py`:
- `TPOContextBuilder._build_timeframe(...)` currently carries `poc`, `vah`, `val`, `shape`, `shape_confidence_pct`, `price_location`, distance-to-level ticks, and `va_width`.
- With history, context adds `poc_shift` and `va_width_change`.

From `services/aureus-signal/engine/signals/tpo_detectors.py`:
- Detectors use price relation with POC/VAH/VAL as primary signal condition.
- Shape is supporting metadata only; invalid cases explicitly say shape is not sufficient without price relation.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Viết advisory độc lập đúng 6 section bắt buộc</name>
  <files>.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md</files>
  <action>Tạo tài liệu advisory bằng tiếng Việt, chỉ documentation/advisory, không sửa source code. Tài liệu phải có đúng các top-level heading theo thứ tự sau và không thêm top-level heading khác: `## 1. Neutral Listing`, `## 2. Attribute Mapping`, `## 3. Contextual Recommendation`, `## 4. Adversarial Mode`, `## Suggested Best Choice`, `## Requirements & Test Basis`. Nội dung phải đánh giá report 260425-t9v độc lập, không chỉ tóm tắt lại. Trong Neutral Listing, liệt kê trung lập các lựa chọn khả thi: giữ classifier hiện tại và calibrate; thay classifier bằng rule/fixture-driven; thêm `distribution_regime` riêng từ `distr`; không thêm regime vào signal; hoặc kết hợp shape + regime ở layer context. Trong Attribute Mapping, so sánh từng lựa chọn theo correctness, semantic clarity, implementation risk, detector compatibility, testability, và risk of false positives. Trong Contextual Recommendation, đặt vào kiến trúc Aureus hiện tại: `_classify_shape` là visual profile metadata; `distr` là distribution intensity/regime, không phải direction; detectors đang dùng price relation làm primary. Trong Adversarial Mode, phản biện chính recommendation: nguy cơ overfitting, thiếu rolling baseline, nhầm TREND thành long/short, làm tăng score quá mức, phá replay/backtest comparability. Trong Suggested Best Choice, chốt một lựa chọn cụ thể, không mơ hồ. Trong Requirements & Test Basis, viết yêu cầu và test basis đủ dùng làm nguồn cho implementation tương lai.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md')
text = p.read_text(encoding='utf-8')
required = [
    '## 1. Neutral Listing',
    '## 2. Attribute Mapping',
    '## 3. Contextual Recommendation',
    '## 4. Adversarial Mode',
    '## Suggested Best Choice',
    '## Requirements & Test Basis',
]
headings = [line.strip() for line in text.splitlines() if line.startswith('## ')]
assert headings == required, headings
for term in ['_classify_shape', 'distr', 'distribution_regime', 'Suggested Best Choice', 'Requirements & Test Basis']:
    assert term in text, term
PY</automated>
  </verify>
  <done>Advisory file exists, has exactly the six required top-level sections in order, and explicitly discusses `_classify_shape`, `distr`, `distribution_regime`, best choice, and requirement/test basis.</done>
</task>

<task type="auto">
  <name>Task 2: Khóa best choice và future implementation basis</name>
  <files>.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md</files>
  <action>Rà soát và chỉnh nội dung advisory để best choice là concrete: giữ/cải thiện `_classify_shape` như visual-shape classifier riêng bằng fixture/calibration, đồng thời thêm `distribution_regime` riêng dựa trên `distr = total_tpo_count / max_tpo_count` với baseline lịch sử/rolling; regime chỉ là context modifier cho detector scoring/tagging khi setup vốn đã valid theo price relation, không tự emit buy/sell và không thay D1 bias. Requirements & Test Basis phải có checklist cụ thể: synthetic shape fixtures cho D/B/p/b và immature profile; unit test tính `distr`; baseline/quantile hoặc rolling-history test cho TREND/NORMAL/NEUTRAL/UNKNOWN; context builder propagation test; detector tests chứng minh regime không tự tạo setup; replay/backtest regression basis. Tránh ngôn ngữ implement ngay hoặc sửa code trong task này.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md')
text = p.read_text(encoding='utf-8')
required_phrases = [
    'visual-shape',
    'distr = total_tpo_count / max_tpo_count',
    'không tự emit buy/sell',
    'không thay D1 bias',
    'TREND',
    'NORMAL',
    'NEUTRAL',
    'UNKNOWN',
    'synthetic',
    'replay/backtest',
]
missing = [phrase for phrase in required_phrases if phrase not in text]
assert not missing, missing
assert 'sửa source code' not in text.lower() or 'không sửa source code' in text.lower()
PY</automated>
  </verify>
  <done>Best choice is explicit and requirements/test basis can be used directly by a future implementation plan without re-deciding semantics.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Advisory document -> future implementation | Human/Claude may later use this advisory as requirement source for code changes. |
| Reference report -> architecture decision | Existing 260425-t9v report may contain assumptions that should not be copied uncritically. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-tpc-01 | Tampering | Requirements semantics | mitigate | State explicitly that `distr`/`distribution_regime` is not direction and must not replace price relation or D1 bias. |
| T-260425-tpc-02 | Information Disclosure | Source code context | accept | Advisory references local code paths and non-secret implementation semantics only; no credentials or private runtime data. |
| T-260425-tpc-03 | Denial of Service | Future detector behavior | mitigate | Requirements include replay/backtest regression and tests that regime cannot independently emit signals. |
</threat_model>

<verification>
Run the automated checks embedded in both tasks. Confirm no source files under `D:/Aureus/services/` are modified; only the advisory markdown is created.
</verification>

<success_criteria>
- A single advisory markdown exists at `D:/Aureus/.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-ARCHITECTURE-ADVISORY.md`.
- It uses exactly the six requested top-level sections in the requested order.
- It explicitly evaluates options for inaccurate `_classify_shape` and `distr`/`distribution_regime` logic.
- It gives a concrete best choice and future requirements/test basis.
- No production source code is modified.
</success_criteria>

<output>
After completion, create `.planning/quick/260425-tpc-nh-gi-c-l-p-report-tpo-shape-distributio/260425-tpc-SUMMARY.md`.
</output>
