---
quick: 260425-fcx-implement-tpocontextbuilder-foundation-f
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/signals/tpo_context.py
  - services/aureus-signal/tests/test_tpo_context.py
autonomous: true
requirements:
  - TPO-CONTEXT-FOUNDATION
must_haves:
  truths:
    - "TPOSignal vẫn là SignalType.INDICATOR và không phát trade signal/tag production mới."
    - "TPOContextBuilder diễn giải được vị trí giá so với POC/VAH/VAL cho D1/H1/M30 khi block tồn tại."
    - "TPOContextBuilder tính va_width bằng VAH - VAL cho từng timeframe có dữ liệu."
    - "TPOContextBuilder không crash khi thiếu một hoặc nhiều block timeframe D1/H1/M30."
    - "Không có thay đổi database/schema, seed strategies, detectors, hoặc production trade-signal emission."
  artifacts:
    - path: "services/aureus-signal/engine/signals/tpo_context.py"
      provides: "TPOContextBuilder context-only feature layer"
      contains: "class TPOContextBuilder"
    - path: "services/aureus-signal/tests/test_tpo_context.py"
      provides: "Targeted tests for price_location, va_width, missing timeframe blocks, and no trade signal emission"
      contains: "test_tpo_context"
  key_links:
    - from: "services/aureus-signal/engine/signals/tpo_context.py"
      to: "TPOSignal output value keys tpo_d1/tpo_h1/tpo_m30"
      via: "builder accepts existing TPO indicator payload without changing TPOSignal"
      pattern: "tpo_d1|tpo_h1|tpo_m30"
    - from: "services/aureus-signal/tests/test_tpo_context.py"
      to: "services/aureus-signal/engine/signals/tpo.py"
      via: "assert TPOSignal.signal_type remains SignalType.INDICATOR"
      pattern: "SignalType\.INDICATOR"
---

<objective>
Tạo foundation context layer cho TPO theo Slice 1 trong kế hoạch `260425-ekl-TPO-IMPLEMENTATION-PLAN.md`: thêm `TPOContextBuilder` để chuẩn hóa output indicator hiện tại thành context facts, không thêm detector, strategy tag, seed strategy, database/schema hoặc production trade signal emission.

Purpose: giữ `TPOSignal` là indicator gốc, tách semantic context ra lớp riêng để các slice sau có thể test độc lập.
Output: `tpo_context.py` mới và test targeted cho price location, `va_width`, missing timeframe blocks, và invariant không phát trade signal.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-IMPLEMENTATION-PLAN.md
@D:/Aureus/services/aureus-signal/engine/signals/tpo.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py

<interfaces>
TPOSignal hiện tại:
```python
class TPOSignal(BaseSignal):
    signal_type = SignalType.INDICATOR

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        return {
            "tag": "tpo",
            "value": {
                "tpo_d1": {"POC": ..., "VAH": ..., "VAL": ..., "shape": ..., "shape_confidence_pct": ..., "shape_scores_pct": ...},
                "tpo_h1": {"POC": ..., "VAH": ..., "VAL": ..., "shape": ..., "shape_confidence_pct": ..., "shape_scores_pct": ...},
                "tpo_m30": {"POC": ..., "VAH": ..., "VAL": ..., "shape": ..., "shape_confidence_pct": ..., "shape_scores_pct": ...},
            },
            "t": ts,
        }
```

Context layer contract cần tạo trong plan này:
```python
class TPOContextBuilder:
    def __init__(self, tick_size: float = 0.1, near_poc_ticks: float = 2.0): ...
    def build(self, tpo_value: dict, close: float) -> dict: ...
```

Output context tối thiểu:
```python
{
    "timeframes": {
        "D1": {"price_location": "above_vah" | "below_val" | "near_poc" | "inside_value_area", "va_width": float, ...} | None,
        "H1": {...} | None,
        "M30": {...} | None,
    },
    "bias": {"d1": "bullish" | "bearish" | "neutral"}
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Viết test đỏ cho TPOContextBuilder foundation</name>
  <files>services/aureus-signal/tests/test_tpo_context.py</files>
  <behavior>
    - close lớn hơn VAH trả `price_location == "above_vah"`.
    - close nhỏ hơn VAL trả `price_location == "below_val"`.
    - close gần POC trong ngưỡng `near_poc_ticks * tick_size` trả `price_location == "near_poc"`.
    - `va_width` bằng chính xác `VAH - VAL` cho timeframe có block.
    - Khi `tpo_d1`, `tpo_h1`, hoặc `tpo_m30` là `None`, builder vẫn trả đủ key `D1/H1/M30` với value `None`, không crash.
    - Test invariant: `TPOSignal.signal_type == SignalType.INDICATOR`, builder output không chứa trade tags như `tpo_va_rejection_bull`, `tpo_va_rejection_bear`, `tpo_va_breakout_bull`, `tpo_va_breakout_bear`, `tpo_trend_pullback_bull`, `tpo_trend_pullback_bear`.
  </behavior>
  <action>Trước khi sửa/tạo code, dùng GitNexus theo CLAUDE.md: chạy impact analysis cho symbol sẽ động chạm (`TPOSignal` nếu test import/assert trực tiếp, và `TPOContextBuilder` nếu index đã biết symbol; nếu symbol mới chưa có trong index thì ghi rõ là symbol mới, không có callers). Tạo test file mới `test_tpo_context.py` theo style pytest hiện có, import từ `engine.signals.tpo_context` và `engine.signals.tpo`. Không sửa `test_tpo_signal.py` nếu không cần. Không thêm detector/strategy/DB test.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_context.py -q</automated>
  </verify>
  <done>Test file tồn tại, mô tả đầy đủ behavior trên; lần chạy đầu có thể fail vì chưa có `tpo_context.py`, nhưng không fail vì syntax/import path sai ngoài module chưa implement.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement context-only TPOContextBuilder</name>
  <files>services/aureus-signal/engine/signals/tpo_context.py</files>
  <behavior>
    - Builder nhận `tpo_value` theo output `res["value"]` của `TPOSignal.calculate`, không gọi lại indicator và không mutate input.
    - Map key `tpo_d1/tpo_h1/tpo_m30` sang `D1/H1/M30`.
    - Mỗi block hợp lệ trả các facts tối thiểu: `poc`, `vah`, `val`, `shape`, `shape_confidence_pct`, `price_location`, `distance_to_poc_ticks`, `distance_to_vah_ticks`, `distance_to_val_ticks`, `va_width`.
    - Missing/None block trả `None` tại timeframe tương ứng.
    - `bias.d1` dùng context đơn giản từ close so với D1 POC/VAH/VAL: above VAH hoặc above POC = bullish, below VAL hoặc below POC = bearish, missing D1 = neutral. Không dùng shape làm trigger.
  </behavior>
  <action>Tạo file mới `tpo_context.py` với class nhỏ, không dependency ngoài stdlib typing. Giữ implementation surgical: helper private cho location/distance nếu cần, không chỉnh `TPOSignal`, không đăng ký signal, không emit tag, không thêm seed strategy. Price location precedence: nếu abs(close - POC) <= near_poc_ticks * tick_size thì `near_poc`; elif close > VAH thì `above_vah`; elif close < VAL thì `below_val`; else `inside_value_area`. Validate numeric nhẹ bằng float conversion cho POC/VAH/VAL; nếu thiếu field cốt lõi thì trả None cho block đó thay vì raise.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_context.py -q</automated>
  </verify>
  <done>Targeted test `test_tpo_context.py` pass; `tpo_context.py` chỉ chứa context facts, không chứa strategy tags, detector class, database access, hoặc schema logic.</done>
</task>

<task type="auto">
  <name>Task 3: Chạy regression guardrails và kiểm tra phạm vi thay đổi</name>
  <files>services/aureus-signal/engine/signals/tpo_context.py, services/aureus-signal/tests/test_tpo_context.py</files>
  <action>Chạy targeted regression cho TPO indicator hiện hữu để đảm bảo `TPOSignal` vẫn là indicator và profile tests không bị ảnh hưởng. Sau đó chạy `gitnexus_detect_changes()` theo CLAUDE.md trước khi kết thúc/commit để xác nhận chỉ có `tpo_context.py` và `test_tpo_context.py` bị ảnh hưởng. Không sửa database/schema/migrations, `seed_strategies.py`, detector/scorer files, hoặc production signal registry.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_context.py tests/test_tpo_signal.py -q</automated>
    <automated>git diff --name-only -- services/aureus-signal/engine/signals/tpo_context.py services/aureus-signal/tests/test_tpo_context.py services/aureus-signal/engine/signals/tpo.py services/aureus-signal/engine/strategies/seed_strategies.py db prisma migrations</automated>
  </verify>
  <done>Targeted tests pass; GitNexus change detection đã chạy; diff không có DB/schema/migration/seed strategy changes; `services/aureus-signal/engine/signals/tpo.py` không bị sửa hoặc nếu có thì chỉ là thay đổi được giải thích và vẫn giữ `SignalType.INDICATOR`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| TPO indicator payload → context builder | Builder nhận dict runtime có thể thiếu block/key hoặc có value không numeric. |
| Context builder → future detectors/strategy | Output context có thể bị hiểu nhầm thành trade signal nếu chứa tags/side/setup. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-fcx-01 | T | TPOContextBuilder.build | mitigate | Không mutate input; convert POC/VAH/VAL sang float; missing core fields trả None cho timeframe thay vì raise. |
| T-260425-fcx-02 | I | tpo_context.py output contract | mitigate | Không include strategy tags, detector setup, side, entry, SL/TP, hoặc trade_execution trong output context. |
| T-260425-fcx-03 | D | Missing timeframe blocks | mitigate | Test D1/H1/M30 None blocks; builder luôn trả đủ keys và không crash. |
| T-260425-fcx-04 | E | Production strategy path | mitigate | Không sửa seed strategies, registry, database/schema, hoặc `TPOSignal.signal_type`; regression assert indicator invariant. |
</threat_model>

<verification>
Chạy các lệnh targeted dưới đây từ repo/service:

```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_context.py -q
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_tpo_context.py tests/test_tpo_signal.py -q
```

Trước khi kết thúc/commit, bắt buộc chạy GitNexus theo CLAUDE.md:
- `gitnexus_impact({target: "TPOSignal", direction: "upstream"})` trước khi bất kỳ thay đổi nào có thể chạm/import/assert symbol này; báo blast radius cho user.
- Với `TPOContextBuilder`, nếu GitNexus báo symbol mới chưa có index thì ghi rõ là symbol mới; nếu đã có index thì chạy impact trước edit.
- `gitnexus_detect_changes()` để xác nhận scope chỉ gồm context/test mong muốn.
</verification>

<success_criteria>
- `services/aureus-signal/engine/signals/tpo_context.py` tồn tại với `TPOContextBuilder` context-only.
- `services/aureus-signal/tests/test_tpo_context.py` cover price location, `va_width`, missing timeframe blocks, và invariant no trade signal emission.
- `TPOSignal` vẫn là `SignalType.INDICATOR`; không đổi tag output production từ `"tpo"` thành trade tag.
- Không có thay đổi trong database/schema/migrations.
- Không có thay đổi trong `services/aureus-signal/engine/strategies/seed_strategies.py`.
- Không tạo detector/scorer/strategy tag production trong quick này.
</success_criteria>

<output>
Sau khi hoàn tất, tạo `D:/Aureus/.planning/quick/260425-fcx-implement-tpocontextbuilder-foundation-f/260425-fcx-SUMMARY.md`.
</output>
