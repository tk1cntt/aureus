---
quick: 260425-lqo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md
  - .planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md
autonomous: true
requirements:
  - QUICK-260425-LQO
must_haves:
  truths:
    - "Tài liệu tư vấn kiến trúc phản biện độc lập dựa trực tiếp trên report _classify_shape hiện có."
    - "Tài liệu đi đủ 4 bước user yêu cầu: Neutral Listing, Attribute Mapping, Contextual Recommendation, Adversarial Mode."
    - "Kết luận cuối cùng nêu rõ lựa chọn tốt nhất và cập nhật thành yêu cầu thực thi/kiểm thử sau này."
  artifacts:
    - path: ".planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md"
      provides: "Tư vấn kiến trúc độc lập 4 bước cho hướng cải thiện _classify_shape/TPO shape"
    - path: ".planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md"
      provides: "Yêu cầu thực thi và kiểm thử được cập nhật từ khuyến nghị cuối cùng"
  key_links:
    - from: ".planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md"
      to: ".planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md"
      via: "source report được trích dẫn làm ngữ cảnh và bằng chứng"
    - from: ".planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md"
      to: ".planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md"
      via: "khuyến nghị cuối cùng được chuyển thành acceptance criteria/test basis"
---

<objective>
Tạo một tài liệu tư vấn kiến trúc hệ thống độc lập cho bài toán cải thiện `_classify_shape`/TPO shape dựa trên report nguồn `260425-kwd-REPORT.md`, theo đúng quy trình 4 bước user yêu cầu.

Purpose: Biến phân tích hiện trạng thành quyết định kiến trúc có phản biện nghịch đảo, kèm yêu cầu thực thi/kiểm thử rõ ràng cho các quick/phase sau.

Output: `260425-lqo-ARCHITECTURE-ADVISORY.md` và `260425-lqo-REQUIREMENTS.md` trong thư mục quick đích.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md

Các ràng buộc quan trọng:
- Mọi nội dung viết bằng tiếng Việt theo CLAUDE.md.
- Đây là quick documentation/planning-only; không sửa production source, tests, migration, database schema.
- Không chạy research phase; chỉ dùng report nguồn và context dự án hiện có.
- Nếu cần nêu giả định, nêu rõ trong tài liệu; không giả định ngầm.

Ngữ cảnh bắt buộc từ report nguồn:
- `_classify_shape` hiện là heuristic nội bộ trong `services/aureus-signal/engine/signals/tpo.py`, trả `shape`, `shape_confidence_pct`, `shape_scores_pct` cho D/B/p/b.
- Shape hiện đi vào `state_obj.tpo_profile`, `indicator_snapshot`, Telegram SIGNAL ALERT; chưa có bằng chứng shape được flatten vào `signal_snapshot` hoặc trực tiếp scoring strategy.
- Rủi ro chính: confidence chưa calibrate, threshold brittle, dual peak thiếu separation/valley, sparse current bucket, tick_size/binning sensitivity, outlier/wick sensitivity, UTC D1 semantic, thiếu unknown/insufficient state.
- Report nguồn khuyến nghị không nhảy thẳng sang ML; ưu tiên hybrid: calibrated heuristic + maturity gating trước, sau đó detector context và replay/backtest calibration.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Viết advisory 4 bước theo đúng yêu cầu user</name>
  <files>.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md</files>
  <action>
    Tạo tài liệu advisory bằng tiếng Việt, đóng vai chuyên gia tư vấn kiến trúc độc lập. Dựa trực tiếp trên `260425-kwd-REPORT.md`, không thêm research ngoài. Tài liệu phải có đúng 4 phần chính:

    1. `Bước 1: Liệt kê và Phân rã (Neutral Listing)` — liệt kê trung lập các phương án/công nghệ phổ biến để cải thiện TPO shape classification, ít nhất gồm: calibrated deterministic heuristic, maturity/session gating, rule-based hybrid với TPO detectors, offline replay/backtest calibration, statistical/ML classifier. Ở bước này chỉ mô tả đặc điểm kỹ thuật, không nhận xét tốt/xấu.
    2. `Bước 2: Phân tích theo Tiêu chí (Attribute Mapping)` — phân tích phương án mạnh nhất theo các tiêu chí phù hợp với context report: độ ổn định runtime/determinism, khả năng giải thích trên Telegram, tốc độ triển khai, khả năng giảm false confidence/sparse noise, giá trị kiểm chứng bằng replay/backtest, độ phức tạp bảo trì. Phải có trade-off cụ thể nếu chọn calibrated heuristic/hybrid thay vì ML và ngược lại.
    3. `Bước 3: Đề xuất dựa trên Context (Contextual Recommendation)` — dùng context cụ thể từ report: hệ thống hiện đang có TPO signal, TPOContextBuilder/detectors/replay harness đã xuất hiện trong STATE, shape chủ yếu đang là hiển thị/giải thích, confidence chưa phải xác suất, không nên đưa vào scoring trước calibration. Đề xuất phương án tối ưu nhất và giải thích vì sao.
    4. `Bước 4: Chế độ Phản biện Nghịch đảo (Adversarial Mode)` — giả sử chọn phương án đề xuất ở bước 3, tấn công lựa chọn đó với ít nhất 3 kịch bản thất bại cụ thể và các rủi ro kiến trúc thường bị bỏ qua. Sau phản biện, đưa `Suggested best choice` cuối cùng: lựa chọn tốt nhất, phạm vi nên làm trước, điều kiện không nên làm, và các guardrail bắt buộc.

    Không dùng ngôn ngữ kiểu "v1", "placeholder", "làm tạm". Không đề xuất implement production ngay trong tài liệu; đây là advisory làm nền cho yêu cầu và kiểm thử sau này.
  </action>
  <verify>
    <automated>test -f "D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md" && python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md')
s = p.read_text(encoding='utf-8')
required = [
  'Bước 1: Liệt kê và Phân rã',
  'Bước 2: Phân tích theo Tiêu chí',
  'Bước 3: Đề xuất dựa trên Context',
  'Bước 4: Chế độ Phản biện Nghịch đảo',
  'Suggested best choice',
  '260425-kwd-REPORT.md',
]
missing = [x for x in required if x not in s]
assert not missing, missing
assert s.count('THẤT BẠI') >= 3 or s.lower().count('fail') >= 3 or s.lower().count('thất bại') >= 3
PY</automated>
  </verify>
  <done>Advisory tồn tại, viết bằng tiếng Việt, có đủ 4 bước, có trade-off, có adversarial analysis ít nhất 3 fail cases, và có suggested best choice cuối cùng.</done>
</task>

<task type="auto">
  <name>Task 2: Chuyển khuyến nghị thành tài liệu yêu cầu thực thi và kiểm thử</name>
  <files>.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md</files>
  <action>
    Tạo tài liệu yêu cầu bằng tiếng Việt để làm cơ sở thực thi và kiểm thử sau này. Tài liệu phải bám theo `Suggested best choice` trong advisory và chuyển thành yêu cầu kiểm chứng được, không sửa production code.

    Nội dung bắt buộc:
    - `Decision Summary`: quyết định kiến trúc cuối cùng cho cải thiện `_classify_shape`/TPO shape.
    - `In Scope`: các yêu cầu nên thực hiện khi implement sau này, ví dụ: calibrated heuristic metrics, peak separation + valley depth, maturity/data-quality gate, confidence margin top-1/top-2, detector context như confirmation layer, replay/backtest validation trước khi dùng cho scoring.
    - `Out of Scope / Do Not Do`: không dùng ML ngay, không coi `shape_confidence_pct` là xác suất thật khi chưa calibrate, không đưa shape vào strategy scoring trước khi có replay/backtest, không đổi session D1 nếu chưa quyết định session semantics.
    - `Acceptance Criteria`: checklist đo được cho future implementation.
    - `Test Basis`: unit fixture D/B/p/b, sparse/empty/outlier/tick_size tests, integration với indicator snapshot/Telegram, replay metrics như flip rate/confidence distribution/A-B backtest nếu scoring.
    - `Traceability`: mapping các yêu cầu về nguồn `260425-kwd-REPORT.md` và advisory `260425-lqo-ARCHITECTURE-ADVISORY.md`.
  </action>
  <verify>
    <automated>test -f "D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md" && python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md')
s = p.read_text(encoding='utf-8')
required = ['Decision Summary','In Scope','Out of Scope','Acceptance Criteria','Test Basis','Traceability','260425-kwd-REPORT.md','260425-lqo-ARCHITECTURE-ADVISORY.md']
missing = [x for x in required if x not in s]
assert not missing, missing
for phrase in ['ML', 'shape_confidence_pct', 'replay', 'backtest', 'maturity']:
    assert phrase.lower() in s.lower(), phrase
PY</automated>
  </verify>
  <done>Requirements document tồn tại, chuyển khuyến nghị thành in-scope/out-of-scope, acceptance criteria, test basis và traceability rõ ràng.</done>
</task>

<task type="auto">
  <name>Task 3: Kiểm tra tính nhất quán planning-only và tạo summary</name>
  <files>.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-SUMMARY.md</files>
  <action>
    Kiểm tra rằng quick task chỉ tạo/cập nhật tài liệu trong thư mục quick `260425-lqo...` và không sửa source code. Tạo `260425-lqo-SUMMARY.md` bằng tiếng Việt, tóm tắt artifact đã tạo, quyết định kiến trúc cuối cùng, các yêu cầu/test basis đã được ghi nhận, và xác nhận không có production code/database/schema thay đổi.
  </action>
  <verify>
    <automated>git -C "D:/Aureus" status --short && test -f "D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-SUMMARY.md" && python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-SUMMARY.md')
s = p.read_text(encoding='utf-8')
for phrase in ['planning-only', 'không có production code', '260425-lqo-ARCHITECTURE-ADVISORY.md', '260425-lqo-REQUIREMENTS.md']:
    assert phrase.lower() in s.lower(), phrase
PY</automated>
  </verify>
  <done>Summary tồn tại và xác nhận phạm vi thay đổi chỉ là tài liệu planning trong quick folder.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Report nguồn -> advisory/requirements | Nội dung phân tích được diễn giải thành quyết định kiến trúc; rủi ro chính là bóp méo context hoặc thêm khuyến nghị không có cơ sở. |
| Advisory -> future implementation | Tài liệu yêu cầu sẽ được dùng làm nền cho implement/test sau này; rủi ro là acceptance criteria mơ hồ khiến executor diễn giải sai. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-lqo-01 | Tampering | `260425-lqo-ARCHITECTURE-ADVISORY.md` | mitigate | Bắt buộc trace nguồn `260425-kwd-REPORT.md`, phân tách neutral listing khỏi recommendation, không thêm production claims ngoài report. |
| T-260425-lqo-02 | Repudiation | `260425-lqo-REQUIREMENTS.md` | mitigate | Thêm `Traceability` mapping từ decision/advisory sang acceptance criteria và test basis. |
| T-260425-lqo-03 | Information Disclosure | planning docs | accept | Artifact chỉ dùng thông tin nội bộ đã có trong planning report; không thêm secrets, credentials, hoặc dữ liệu khách hàng. |
</threat_model>

<verification>
Chạy các lệnh verify trong từng task. Sau khi hoàn tất, kiểm tra `git -C "D:/Aureus" status --short` chỉ có các file planning trong `.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/`.
</verification>

<success_criteria>
- Có `260425-lqo-ARCHITECTURE-ADVISORY.md` với đúng 4 bước user yêu cầu.
- Có `260425-lqo-REQUIREMENTS.md` chuyển khuyến nghị thành cơ sở thực thi/kiểm thử sau này.
- Có `260425-lqo-SUMMARY.md` xác nhận planning-only và tóm tắt quyết định.
- Không có production source, tests, migrations, runtime config hoặc database schema bị sửa.
</success_criteria>

<output>
Sau completion, tạo `.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-SUMMARY.md`.
</output>
