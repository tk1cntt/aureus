---
phase: 260425-ekl-tpo-signal-plan
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md
  - .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md
autonomous: true
requirements:
  - QUICK-260425-EKL
must_haves:
  truths:
    - "Có report tiếng Việt đối chiếu yêu cầu trong tpo_indi.txt với trạng thái TPO hiện tại, không sửa runtime source."
    - "Có implementation plan tương lai cho signal TPO theo hướng indicator → feature layer → rule engine → signal → backtest → production."
    - "Plan nêu rõ bước nào cần test trước khi implement, đặc biệt các feature TPO state/history/detector/scorer."
  artifacts:
    - path: ".planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md"
      provides: "Kế hoạch triển khai signal TPO trong tương lai"
    - path: ".planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md"
      provides: "Báo cáo phân tích khoảng trống và rủi ro từ tpo_indi.txt"
  key_links:
    - from: "tpo_indi.txt"
      to: "260425-ekl-TPO-IMPLEMENTATION-PLAN.md"
      via: "Trích xuất yêu cầu/phase/signal đề xuất"
      pattern: "TPOContextBuilder|VARejectionDetector|TPOStrategySignal"
    - from: "services/aureus-signal/engine/signals/tpo.py"
      to: "260425-ekl-REPORT.md"
      via: "Đối chiếu output TPOSignal hiện tại với feature còn thiếu"
      pattern: "POC|VAH|VAL|shape|shape_confidence_pct"
---

<objective>
Tạo bộ tài liệu kế hoạch/report cho việc triển khai signal TPO dựa trên `tpo_indi.txt`, chỉ phân tích và lập kế hoạch, chưa implement.

Purpose: Người dùng cần roadmap cụ thể để biến TPO indicator hiện tại thành signal thực chiến mà không nhảy thẳng vào code.
Output: Hai artifact trong quick directory: `260425-ekl-TPO-IMPLEMENTATION-PLAN.md` và `260425-ekl-REPORT.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/tpo_indi.txt
@D:/Aureus/services/aureus-signal/engine/signals/tpo.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py

<interfaces>
Current TPO indicator shape from `services/aureus-signal/engine/signals/tpo.py`:
```python
class TPOSignal(BaseSignal):
    signal_type = SignalType.INDICATOR
    _TFS = ("D1", "H1", "M30")

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        ...
        payload = {
            "tpo_d1": self._compute_d1(df, ts),
            "tpo_h1": self._compute_sliding(df, ts, tf="H1", count=6, cache=state_obj.tpo_cache),
            "tpo_m30": self._compute_sliding(df, ts, tf="M30", count=6, cache=state_obj.tpo_cache),
        }
        state_obj.tpo_profile = payload
        return {"tag": "tpo", "value": payload, "t": ts}
```

Current block fields verified by tests:
```python
{"POC", "VAH", "VAL", "shape", "shape_confidence_pct", "shape_scores_pct"}
```

Important constraint from user: `Chưa implement`. Do not edit production source, tests, migrations, runtime config, or database schema. Only create planning/report artifacts in this quick directory.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Phân tích spec TPO và hiện trạng code</name>
  <files>.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md</files>
  <action>Đọc kỹ `D:/Aureus/tpo_indi.txt`, `D:/Aureus/services/aureus-signal/engine/signals/tpo.py`, và `D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py`. Tạo report tiếng Việt mô tả: (1) TPO hiện tại đã có gì: D1/H1/M30, POC/VAH/VAL, shape/confidence/scores, cache closed bucket; (2) khoảng trống để thành signal: price relation, va_width, POC/VA shift history, acceptance/rejection, detector, scorer, backtest; (3) rủi ro theo tpo_indi.txt: overfit shape, nhầm indicator với trigger, session definition, thiếu history. Không sửa bất kỳ file source/test nào.</action>
  <verify>
    <automated>test -f "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md" && grep -q "POC" "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md" && grep -q "rủi ro" "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md"</automated>
  </verify>
  <done>Report tồn tại, viết bằng tiếng Việt, nêu rõ hiện trạng, khoảng trống, rủi ro, và không yêu cầu executor implement code.</done>
</task>

<task type="auto">
  <name>Task 2: Tạo implementation plan tương lai cho signal TPO</name>
  <files>.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md</files>
  <action>Tạo kế hoạch triển khai tương lai bằng tiếng Việt, bám sát `tpo_indi.txt` theo kiến trúc: giữ `TPOSignal` là indicator gốc, thêm `TPOContextBuilder`, thêm 3 detector đầu tiên (`VARejectionDetector`, `VABreakoutAcceptanceDetector`, `TrendPullbackDetector`), thêm `TPOStrategySignal`, rồi backtest/calibration. Mỗi giai đoạn phải có mục tiêu, file dự kiến sẽ sửa/tạo trong tương lai, test dự kiến, output contract, và tiêu chí không overfit. Nhấn mạnh đây là kế hoạch cho future implementation, không phải thay đổi code trong quick này.</action>
  <verify>
    <automated>test -f "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md" && grep -q "TPOContextBuilder" "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md" && grep -q "VARejectionDetector" "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md" && grep -q "Backtest" "D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md"</automated>
  </verify>
  <done>Implementation plan có phase/slice rõ ràng, có test plan cho từng slice, có output contract signal cuối, và không chứa chỉ dẫn chỉnh code ngay trong quick task này.</done>
</task>

<task type="auto">
  <name>Task 3: Kiểm tra phạm vi chỉ gồm tài liệu quick</name>
  <files>.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-REPORT.md, .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md</files>
  <action>Chạy kiểm tra git diff để xác nhận executor chỉ tạo/sửa các artifact planning/report trong quick directory và không thay đổi `services/aureus-signal/**`, tests, migrations, hoặc runtime config. Nếu phát hiện source/test bị sửa, revert phần đó trước khi hoàn tất quick task.</action>
  <verify>
    <automated>git -C "D:/Aureus" diff --name-only | grep -E "^\.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-(PLAN|REPORT|TPO-IMPLEMENTATION-PLAN)\.md$"</automated>
  </verify>
  <done>Git diff chỉ chứa quick planning/report artifacts liên quan; source runtime không đổi.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| planning-docs-only | Quick này chỉ tạo tài liệu planning/report, không nhận untrusted runtime input và không thay đổi code thực thi. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-ekl-01 | T | Planning artifacts | mitigate | Executor phải đối chiếu `git diff --name-only` để đảm bảo không sửa source/test/migration ngoài quick artifacts. |
| T-260425-ekl-02 | I | Report content | accept | Tài liệu chỉ chứa phân tích kỹ thuật nội bộ từ repo và tpo_indi.txt, không thêm secrets/env values. |
</threat_model>

<verification>
- `260425-ekl-REPORT.md` tồn tại và có phân tích hiện trạng/khoảng trống/rủi ro.
- `260425-ekl-TPO-IMPLEMENTATION-PLAN.md` tồn tại và có roadmap triển khai future implementation.
- Không có thay đổi runtime source/test/migration.
</verification>

<success_criteria>
Quick task hoàn tất khi người dùng có đủ report và implementation plan để quyết định phase implement signal TPO tiếp theo, nhưng repo runtime vẫn chưa bị thay đổi.
</success_criteria>

<output>
Sau khi hoàn tất, tạo summary tại `D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-SUMMARY.md`.
</output>
