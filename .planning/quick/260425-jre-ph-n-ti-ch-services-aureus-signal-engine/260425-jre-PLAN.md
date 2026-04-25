---
phase: 260425-jre-ph-n-ti-ch-services-aureus-signal-engine
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md
autonomous: true
requirements:
  - QUICK-JRE-01
must_haves:
  truths:
    - "Báo cáo giải thích được vì sao logic trend hiện tại dùng EMA 200 + OB count bị delay hoặc neutral quá nhiều."
    - "Báo cáo so sánh các phương án trend khả thi dựa trên signal hiện có, không yêu cầu thêm dependency mới."
    - "Báo cáo có SWOT và khuyến nghị rõ ràng để user chọn hướng POC sau này."
  artifacts:
    - path: ".planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md"
      provides: "Analysis-only report về tối ưu trend detection"
      contains: "SWOT"
  key_links:
    - from: "services/aureus-signal/engine/signals/trend.py"
      to: ".planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md"
      via: "source-code analysis only, no implementation"
      pattern: "TrendSignal|EMA 200|POC Shift|SWOT"
---

<objective>
Phân tích `services/aureus-signal/engine/signals/trend.py` để đề xuất cách phát hiện trend tốt hơn khi EMA 200 bị delay quá chậm.

Purpose: Tạo báo cáo ra quyết định cho hướng POC/thiết kế tiếp theo, không sửa code.
Output: `.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md` có phân tích hiện trạng, SWOT, so sánh phương án và recommendation.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-signal/engine/signals/trend.py
@D:/Aureus/services/aureus-signal/engine/signals/ema.py
@D:/Aureus/services/aureus-signal/engine/signals/pivots.py
@D:/Aureus/services/aureus-signal/engine/signals/structure.py
@D:/Aureus/services/aureus-signal/engine/signals/sweep.py

<interfaces>
Các contract quan trọng executor cần dùng để phân tích, không sửa:

From `services/aureus-signal/engine/signals/trend.py`:
```python
class TrendSignal(BaseSignal):
    def __init__(self, ema_period: int = 200)
    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]
```
- Current output tag: `htf_trend`
- Current state field: `state_obj.htf_trend`
- Current regime values: `TREND_UP`, `TREND_DN`, `SIDEWAYS`
- Current directional values: `BULLISH`, `BEARISH`, `NEUTRAL`
- Current gate: price relative to `ema_{ema_period}` plus unmitigated OB delta >= 2.

From existing signals:
- `EMASignal` already stores `state_obj.emas[period] = {current, prev, slope}` and emits `ema_{period}_up/down` plus `cross` metadata.
- `PivotSignal` maintains `state_obj.swing_points` with HH/LL/LH/HL labels from confirmed non-repainting pivots.
- `StructureSignal` emits CHOCH/OB events and maintains `state_obj.obs` plus OB metadata.
- `SweepSignal` emits `sweep`, `stop_hunt`, `clean_breakout`, and related OB-state transition tags.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Lập bản đồ logic trend hiện tại và các signal có thể tận dụng</name>
  <files>.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md</files>
  <action>Đọc các file context đã liệt kê và viết phần đầu report: tóm tắt logic `TrendSignal` hiện tại, chỉ ra nguyên nhân EMA 200 gây lag, nguyên nhân OB count gate dễ trả NEUTRAL/SIDEWAYS, và inventory các signal sẵn có có thể dùng để trend detection gồm EMA slope/cross, pivot HH/HL/LL/LH, CHOCH/OB, sweep/stop_hunt/clean_breakout. Không đề xuất sửa code và không tạo task implement.</action>
  <verify>
    <automated>test -f "D:/Aureus/.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md" && grep -E "TrendSignal|EMA 200|NEUTRAL|swing_points|CHOCH|sweep" "D:/Aureus/.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md"</automated>
  </verify>
  <done>Report có section hiện trạng và inventory signal, có dẫn chiếu file/logic cụ thể, không có code diff implementation.</done>
</task>

<task type="auto">
  <name>Task 2: Phân tích SWOT các phương án trend detection khả thi</name>
  <files>.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md</files>
  <action>Bổ sung SWOT cho ít nhất 5 phương án: (1) POC Shift dựa trên pivot/market structure, (2) EMA stack/slope nhanh hơn EMA200, ví dụ EMA21/55 + slope, (3) CHOCH + OB regime, (4) sweep/stop-hunt confirmation, (5) hybrid scoring/voting giữa structure + EMA + OB/sweep. Với mỗi phương án ghi rõ input signal hiện có, điểm mạnh, điểm yếu, cơ hội, rủi ro, mức lag kỳ vọng, độ ổn định/non-repaint, và phù hợp timeframe nào. Nhấn mạnh đây là đề xuất phân tích, không implement.</action>
  <verify>
    <automated>grep -E "POC Shift|EMA stack|CHOCH|stop[- ]hunt|hybrid|SWOT|Strength|Weakness|Opportunity|Threat" "D:/Aureus/.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md"</automated>
  </verify>
  <done>Report có SWOT đầy đủ cho các phương án, có so sánh lag/ổn định/rủi ro false signal.</done>
</task>

<task type="auto">
  <name>Task 3: Đưa recommendation và hướng POC không-implementation</name>
  <files>.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md</files>
  <action>Kết luận bằng recommendation ưu tiên: đề xuất phương án nên POC trước, phương án backup, và phương án không nên chọn ngay. Nêu tiêu chí đánh giá POC sau này như detection latency so với EMA200, giảm NEUTRAL sai, false flip rate, non-repaint behavior, compatibility với `state_obj.htf_trend`. Không viết code, không tạo patch, không thay đổi source.</action>
  <verify>
    <automated>grep -E "Recommendation|Khuyến nghị|POC|latency|false flip|non-repaint|không implement" "D:/Aureus/.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md"</automated>
  </verify>
  <done>Report kết luận rõ hướng POC được khuyến nghị và tiêu chí đo, không có file source nào bị sửa.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Source code -> analysis report | Executor chỉ đọc source và tạo report nội bộ; không chạy live trading, không sửa signal runtime. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-jre-01 | T | Report artifact | mitigate | Không sửa `services/aureus-signal/**`; chỉ tạo `260425-jre-REPORT.md` dưới quick directory. |
| T-260425-jre-02 | I | Trading logic assumptions | mitigate | Report phải phân biệt rõ observation từ code hiện tại với giả thuyết/khuyến nghị; không trình bày đề xuất như fact đã kiểm chứng backtest. |
| T-260425-jre-03 | D | Scope creep | mitigate | Không thêm research phase, không benchmark, không implement; chỉ analysis/SWOT/recommendation. |
</threat_model>

<verification>
- Chạy các lệnh grep trong từng task verify.
- Chạy `git status --short` và xác nhận chỉ có plan/report/summary trong quick directory được tạo hoặc sửa; không có file `services/aureus-signal/**` thay đổi.
</verification>

<success_criteria>
- `.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-REPORT.md` tồn tại.
- Report có hiện trạng `TrendSignal`, SWOT ít nhất 5 phương án, recommendation ưu tiên, tiêu chí POC.
- Không có implementation plan trong report; không sửa source code.
</success_criteria>

<output>
After completion, create `.planning/quick/260425-jre-ph-n-ti-ch-services-aureus-signal-engine/260425-jre-SUMMARY.md`
</output>
