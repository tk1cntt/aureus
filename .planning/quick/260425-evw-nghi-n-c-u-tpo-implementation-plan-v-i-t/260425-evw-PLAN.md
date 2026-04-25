---
quick_task: 260425-evw
type: docs-only
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md
autonomous: true
requirements:
  - QT-260425-EVW
gsd_mode: quick
must_haves:
  truths:
    - "Tài liệu TPO implementation plan có phần tư vấn kiến trúc độc lập theo đủ 4 bước: Neutral Listing, Attribute Mapping, Contextual Recommendation, Adversarial Mode."
    - "Khuyến nghị cuối cùng bám context Aureus: Python signal service, seed strategy contract hiện hữu, TPOSignal giữ vai trò indicator, ưu tiên ổn định và tránh overfit."
    - "Tài liệu sau cập nhật đủ rõ để làm cơ sở thực thi và kiểm thử runtime sau này, nhưng quick task này không sửa code runtime."
  artifacts:
    - path: ".planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md"
      provides: "Tài liệu yêu cầu/kiến trúc TPO signal đã bổ sung independent architecture review"
      contains: "## Independent Architecture Review"
  key_links:
    - from: ".planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md"
      to: "services/aureus-signal/engine/strategies/seed_strategies.py"
      via: "Ràng buộc strategy template phải theo seed strategy contract hiện hữu"
      pattern: "seed_strategies.py|Strategy template contract"
---

<objective>
Tạo một plan docs-only để executor cập nhật tài liệu TPO implementation plan bằng góc nhìn chuyên gia tư vấn kiến trúc hệ thống độc lập.

Purpose: Bổ sung cơ sở ra quyết định trước khi implement TPO signal từ indicator, tránh overfit, tránh phá contract strategy hiện hữu, và biến tài liệu thành nguồn yêu cầu/kiểm thử cho các bước sau.
Output: `.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md` được cập nhật với review 4 bước và khuyến nghị cuối cùng.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md
@D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py

<assumptions>
- Đây là docs-only quick task: không sửa runtime code, tests, migrations, config hoặc database.
- Không cần GitNexus impact analysis vì không chỉnh sửa symbol/function/class runtime; nếu executor phát hiện cần sửa code thì phải dừng và lập task/plan khác.
- Tài liệu cần được cập nhật trực tiếp vào TPO implementation plan hiện hữu để làm cơ sở thực thi/kiểm thử sau này.
</assumptions>

<interfaces>
Từ `services/aureus-signal/engine/strategies/seed_strategies.py`, strategy templates hiện hữu nằm trong list `strategies` của `seed_system_strategies` và thường có contract:
- top-level: `name`, `is_active`, `description`, `min_score`, `config`
- `config.min_score_threshold`, `config.context_filters`, `config.sequence`, `config.trade_execution`
- `sequence` item: `tag`, `weight`, `required`, `max_wait`, và với phần lớn strategy mới có `reset_signals`
- `trade_execution`: `direction`, `size_mode`, `size_value`, `sl`, `tp`, `trailing`, `early_exits`; nhiều strategy mới còn có `entry_type`, `entry_method`, `capital_risk_pct`

Từ plan TPO hiện tại:
- `TPOSignal` phải giữ là indicator gốc, không nhồi logic vào lệnh vào class này.
- Pipeline mục tiêu: `TPOSignal indicator → TPO feature/context layer → setup rule engine → strategy signal → backtest/calibration → production`.
- Các slice hiện tại gồm context builder, history store, detector, strategy seed templates/scorer alignment, replay/backtest/calibration, production readiness.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bổ sung independent architecture review 4 bước vào TPO plan</name>
  <files>.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md</files>
  <action>
Thêm một section mới gần sau `## Mục tiêu kiến trúc` hoặc trước `## Slice 1` với tiêu đề `## Independent Architecture Review`. Nội dung bắt buộc có đúng 4 subsection:

1. `### Step 1 — Neutral Listing`: liệt kê trung lập các phương án phổ biến để triển khai TPO signal từ indicator, tối thiểu gồm:
   - Monolithic indicator-driven signal: nhồi detector/trade signal vào `TPOSignal`.
   - Feature/context layer + rule detectors + scorer/strategy bridge.
   - Pure strategy-template gating: chỉ thêm `context_filters`/`sequence` vào seed strategy, ít hoặc không có detector riêng.
   - ML/statistical classifier từ TPO features.
   - External/backtest-first research module sinh report rồi mới promote sang runtime.

2. `### Step 2 — Attribute Mapping`: tạo bảng so sánh các phương án theo ít nhất các tiêu chí: tốc độ thực thi/runtime cost, latency trong signal service Python, maintainability, khả năng tích hợp với `seed_strategies.py`, testability, rủi ro overfit, độ phức tạp rollout, observability/debug reasons. Nêu trade-off rõ ràng, không chỉ chấm điểm.

3. `### Step 3 — Contextual Recommendation`: đưa khuyến nghị cho Aureus hiện tại. Khuyến nghị chính nên là `Feature/context layer + deterministic rule detectors + scorer/strategy bridge`, giữ `TPOSignal` là indicator và emit TPO tags vào strategy engine hiện hữu. Giải thích vì sao phù hợp với signal service Python, strategy seed contract, yêu cầu ổn định và không overfit. Nêu giới hạn: không production nếu chưa backtest/calibration, không dùng shape làm gate duy nhất, không tạo strategy contract riêng ngoài `context_filters` + `sequence` + `trade_execution`.

4. `### Step 4 — Adversarial Mode`: tấn công chính khuyến nghị ở Step 3 với ít nhất 3 fail scenarios/rủi ro kiến trúc bị bỏ qua. Bắt buộc có risk về stale/misaligned multi-timeframe TPO context, detector threshold overfit/false edge, runtime/cache/memory growth hoặc duplicate history, contract drift với seed strategies, và observability/replay không đủ để debug. Với mỗi fail scenario phải có mitigation cụ thể trong tài liệu.

Kết thúc section bằng `### Final Recommendation` nêu lựa chọn tốt nhất: implement theo pipeline đã có, nhưng phải có guardrails từ adversarial mode trước production. Không thay đổi runtime code.
  </action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md')
s = p.read_text(encoding='utf-8')
required = [
    '## Independent Architecture Review',
    '### Step 1 — Neutral Listing',
    '### Step 2 — Attribute Mapping',
    '### Step 3 — Contextual Recommendation',
    '### Step 4 — Adversarial Mode',
    '### Final Recommendation',
    'Feature/context layer',
    'seed_strategies.py',
    'TPOSignal',
    'overfit',
]
missing = [x for x in required if x not in s]
if missing:
    raise SystemExit(f'Missing required content: {missing}')
fail_markers = ['stale', 'multi-timeframe', 'threshold', 'memory', 'contract drift']
missing_fail = [x for x in fail_markers if x.lower() not in s.lower()]
if missing_fail:
    raise SystemExit(f'Missing adversarial risk markers: {missing_fail}')
print('architecture review content ok')
PY</automated>
  </verify>
  <done>TPO implementation plan có section review 4 bước đầy đủ, có bảng trade-off, có contextual recommendation, có adversarial risks kèm mitigation, và có final recommendation rõ ràng.</done>
</task>

<task type="auto">
  <name>Task 2: Đồng bộ yêu cầu thực thi/kiểm thử từ review vào Definition of Done</name>
  <files>.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md</files>
  <action>
Cập nhật các phần yêu cầu hiện hữu nếu cần, đặc biệt `## Definition of Done cho future implementation` và các tiêu chí không overfit, để phản ánh guardrails từ review. Bổ sung các yêu cầu kiểm thử docs-level cho future implementation:
- test contract seed strategy TPO không drift khỏi fields hiện hữu trong `seed_strategies.py`;
- replay/backtest phải deterministic và có split train/validation theo thời gian;
- detector phải có `reasons` đủ debug và không emit trade tag khi conflict long/short hoặc thiếu context bắt buộc;
- history/cache phải giới hạn length, không duplicate cùng timestamp/timeframe, và xử lý stale/misaligned D1/H1/M30;
- nếu future implementation thêm persistence database thì phải có e2e database test theo `CLAUDE.md`.

Giữ phạm vi docs-only: không thêm yêu cầu sửa code ngay trong quick task này, không biến review thành runtime implementation.
  </action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md')
s = p.read_text(encoding='utf-8')
checks = [
    'Definition of Done cho future implementation',
    'contract',
    'deterministic',
    'train/validation',
    'reasons',
    'conflict long/short',
    'duplicate cùng timestamp/timeframe',
    'e2e test với database',
]
missing = [x for x in checks if x not in s]
if missing:
    raise SystemExit(f'Missing DoD/verification requirements: {missing}')
print('DoD guardrails ok')
PY</automated>
  </verify>
  <done>Definition of Done và/hoặc tiêu chí kiểm thử trong plan TPO phản ánh đầy đủ guardrails kiến trúc để executor sau này có cơ sở triển khai và kiểm thử.</done>
</task>

<task type="auto">
  <name>Task 3: Kiểm tra diff chỉ là tài liệu và tạo summary quick task</name>
  <files>.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md, .planning/quick/260425-evw-nghi-n-c-u-tpo-implementation-plan-v-i-t/260425-evw-SUMMARY.md</files>
  <action>
Kiểm tra git diff để xác nhận quick task chỉ sửa tài liệu TPO plan và tạo summary ngắn tại `.planning/quick/260425-evw-nghi-n-c-u-tpo-implementation-plan-v-i-t/260425-evw-SUMMARY.md`. Summary cần nêu: file đã cập nhật, 4 bước review đã thêm, final recommendation, và verification đã chạy. Không commit trừ khi người dùng yêu cầu riêng.
  </action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
summary = Path('D:/Aureus/.planning/quick/260425-evw-nghi-n-c-u-tpo-implementation-plan-v-i-t/260425-evw-SUMMARY.md')
if not summary.exists():
    raise SystemExit('Missing summary file')
s = summary.read_text(encoding='utf-8')
for token in ['Independent Architecture Review', 'Final Recommendation', 'verification']:
    if token not in s:
        raise SystemExit(f'Missing summary token: {token}')
print('summary ok')
PY</automated>
    <automated>git -C D:/Aureus diff --name-only -- .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md .planning/quick/260425-evw-nghi-n-c-u-tpo-implementation-plan-v-i-t/260425-evw-SUMMARY.md</automated>
  </verify>
  <done>Diff chỉ gồm tài liệu liên quan; summary quick task tồn tại và mô tả kết quả review/verification.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| docs→future runtime implementation | Tài liệu tạo ràng buộc cho executor sau này; nếu thiếu guardrails có thể dẫn tới runtime implementation overfit hoặc drift contract. |
| indicator→strategy contract | TPO indicator facts được diễn giải thành signal tags và strategy templates; nếu contract không rõ sẽ tạo coupling sai hoặc trade signal nhiễu. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-evw-01 | Tampering | TPO implementation requirements doc | mitigate | Bắt buộc verify các headings/content markers của review 4 bước bằng script đọc file. |
| T-260425-evw-02 | Information Disclosure | Docs-only review | accept | Không thêm secrets, không đọc/sửa database hoặc runtime config. |
| T-260425-evw-03 | Denial of Service | Future TPO history/cache design | mitigate | Review/DoD phải yêu cầu limit history length, chống duplicate timestamp/timeframe, xử lý stale multi-timeframe context. |
| T-260425-evw-04 | Elevation of Privilege | Future strategy contract | mitigate | Review/DoD phải yêu cầu TPO strategy đi qua `context_filters` + `sequence` + `trade_execution`, không tạo final trade contract riêng. |
</threat_model>

<verification>
Chạy các command trong từng task. Sau khi hoàn tất, đọc lại file TPO plan để xác nhận nội dung review mạch lạc, không mâu thuẫn với nguyên tắc giữ `TPOSignal` là indicator và không yêu cầu sửa runtime code trong quick task này.
</verification>

<success_criteria>
- Tạo/cập nhật đúng tài liệu, không sửa code runtime.
- TPO implementation plan có đủ 4 bước tư vấn kiến trúc và final recommendation.
- Review có ít nhất 3 fail scenarios/rủi ro kiến trúc trong adversarial mode, mỗi rủi ro có mitigation.
- Definition of Done/verification requirements đủ rõ để làm cơ sở thực thi/kiểm thử sau này.
</success_criteria>

<output>
Sau completion, tạo `.planning/quick/260425-evw-nghi-n-c-u-tpo-implementation-plan-v-i-t/260425-evw-SUMMARY.md`.
</output>
