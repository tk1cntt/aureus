---
phase: quick-260503-pae
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/orders.py
  - services/aureus-signal/tests/test_pivot_sl.py
autonomous: true
requirements:
  - QUICK-260503-PAE
must_haves:
  truths:
    - "PIVOT_POINT SL chọn pivot theo giá sau khi lọc 5 nến, không chọn theo thứ tự thời gian/reversed list."
    - "BUY dùng pivot LL hợp lệ cao nhất để đặt SL gần nhất dưới entry."
    - "SELL dùng pivot HH hợp lệ thấp nhất để đặt SL gần nhất trên entry."
    - "pivot_index vẫn hoạt động sau khi sắp xếp pivot theo rule BUY/Sell."
  artifacts:
    - path: "services/aureus-signal/engine/orders.py"
      provides: "PIVOT_POINT pivot sort/selection trong SimulatedTradeManager._calculate_sl_tp"
      contains: "valid_pivots.sort"
    - path: "services/aureus-signal/tests/test_pivot_sl.py"
      provides: "Unit tests khóa rule BUY highest LL và SELL lowest HH"
      contains: "test_pivot_point_buy_sorts_valid_pivots_descending_by_price"
  key_links:
    - from: "services/aureus-signal/engine/orders.py"
      to: "services/aureus-signal/tests/test_pivot_sl.py"
      via: "SimulatedTradeManager._calculate_sl_tp PIVOT_POINT branch"
      pattern: "PIVOT_POINT"
---

<objective>
Fix TODO trong `services/aureus-signal/engine/orders.py`: PIVOT_POINT SL phải sắp xếp pivot hợp lệ theo giá trước khi chọn.

Purpose: tránh limit/market order dùng pivot xa hơn hoặc sai thứ tự do `_find_pivot_for_sl_candidates()` trả về theo thời gian đảo ngược.
Output: TODO được thay bằng logic rõ ràng, tests khóa hành vi BUY/Sell.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md
@D:/Aureus/services/aureus-signal/engine/orders.py
@D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py

Assumptions:
- Scope chỉ `orders.py` và test liên quan.
- TODO hiện tại nằm trong `SimulatedTradeManager._calculate_sl_tp`, PIVOT_POINT branch.
- Không có thay đổi database; không cần DB E2E.
- GitNexus MCP có thể không có trong agent toolset này; executor phải dùng nếu có, nếu không ghi rõ limitation trong summary.

Existing relevant code:
- `SimulatedTradeManager._find_pivot_for_sl_candidates(side, state_obj)` trả list pivot LL/HH hợp lệ theo thứ tự reversed swing_points.
- `_calculate_sl_tp()` lọc pivot theo 5 nến gần nhất rồi đang chọn `valid_pivots[pivot_index - 1]`.
- TODO yêu cầu: "sắp xếp lại pivot theo thứ tự và lấy pivot nhỏ nhất với SELL và lớn nhất với BUY".
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add pivot sort regression tests</name>
  <files>services/aureus-signal/tests/test_pivot_sl.py</files>
  <behavior>
    - BUY: khi valid LL có giá 1980, 1990, 2000 nhưng thứ tự swing_points làm reversed list không theo giá, `pivot_index=1` phải chọn 2000.
    - SELL: khi valid HH có giá 2020, 2030, 2040 nhưng thứ tự swing_points làm reversed list không theo giá, `pivot_index=1` phải chọn 2020.
    - pivot_index=2 giữ nghĩa "candidate thứ hai sau sort", không theo thời gian.
  </behavior>
  <action>Thêm tests vào `TestCalculateSlTpPivotPoint` trong `services/aureus-signal/tests/test_pivot_sl.py`. Không sửa tests cũ ngoài kỳ vọng nào thực sự bị rule mới thay đổi. Tests phải fail trước khi sửa `orders.py` nếu TODO chưa implemented.</action>
  <verify>
    <automated>cd /d/Aureus && python -m pytest services/aureus-signal/tests/test_pivot_sl.py -q</automated>
  </verify>
  <done>Tests mới mô tả BUY highest valid LL, SELL lowest valid HH, và pivot_index sau sort.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement PIVOT_POINT price-order selection</name>
  <files>services/aureus-signal/engine/orders.py</files>
  <behavior>
    - Trong `_calculate_sl_tp`, sau 5-candle filter, sort `valid_pivots` trước khi áp dụng `pivot_index`.
    - BUY sort descending để pivot lớn nhất đứng đầu.
    - SELL sort ascending để pivot nhỏ nhất đứng đầu.
    - Giữ nguyên rejection khi không đủ valid pivot; giữ nguyên offset SL và TP RR logic.
  </behavior>
  <action>Trước khi edit symbol, chạy GitNexus impact nếu tool có: `gitnexus_impact({target: "SimulatedTradeManager._calculate_sl_tp", direction: "upstream"})`, báo blast radius trong summary. Nếu GitNexus tool không có, ghi limitation. Thay TODO bằng logic sort tối thiểu: `valid_pivots.sort(reverse=('BUY' in side))` trước block `if len(valid_pivots) >= pivot_index`. Không refactor các nhánh SL/TP khác, không đổi `_find_pivot_for_sl_candidates`, không discard existing working-tree change ngoài TODO.</action>
  <verify>
    <automated>cd /d/Aureus && python -m pytest services/aureus-signal/tests/test_pivot_sl.py -q</automated>
  </verify>
  <done>`orders.py` không còn TODO này; PIVOT_POINT chọn pivot theo giá đúng rule BUY/Sell; toàn bộ `test_pivot_sl.py` pass.</done>
</task>

<task type="auto">
  <name>Task 3: Run focused validation and change-scope check</name>
  <files>services/aureus-signal/engine/orders.py, services/aureus-signal/tests/test_pivot_sl.py</files>
  <action>Chạy focused tests. Trước commit hoặc trước khi kết thúc, chạy `gitnexus_detect_changes()` nếu GitNexus tool có để xác nhận chỉ ảnh hưởng symbol mong đợi; nếu không có tool, ghi limitation trong summary. Không stage/commit `mql5/AureusProvider_v2.ex5`, `stable/`, hoặc bất kỳ file ngoài scope.</action>
  <verify>
    <automated>cd /d/Aureus && python -m pytest services/aureus-signal/tests/test_pivot_sl.py services/aureus-signal/tests/test_entry_price_methods.py -q</automated>
  </verify>
  <done>Focused tests pass; change scope chỉ gồm `orders.py` và test pivot nếu test được thêm; GitNexus detect_changes chạy hoặc limitation được ghi rõ.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| strategy config → order engine | Strategy `sl`/`tp` config và swing state đi vào order price calculation. |
| order engine → MT5/order stream | Calculated SL/TP đi tới order command/Redis stream. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-PAE-01 | Tampering | `_calculate_sl_tp` PIVOT_POINT selection | mitigate | Sort only filtered numeric pivots already parsed from swing points; keep existing invalid value skip/reject behavior. |
| T-260503-PAE-02 | Denial of Service | pivot filtering/sorting | accept | List length bounded by in-memory swing points; sort cost small versus candle processing. |
| T-260503-PAE-03 | Repudiation | order decision auditability | mitigate | Keep existing warning/info logs and rejection path unchanged; tests verify deterministic selection. |
</threat_model>

<verification>
- `python -m pytest services/aureus-signal/tests/test_pivot_sl.py -q`
- `python -m pytest services/aureus-signal/tests/test_pivot_sl.py services/aureus-signal/tests/test_entry_price_methods.py -q`
- GitNexus impact before edit and detect_changes before finish if available.
</verification>

<success_criteria>
- TODO in `orders.py` removed only after implemented.
- BUY PIVOT_POINT chooses highest valid LL before `pivot_index`.
- SELL PIVOT_POINT chooses lowest valid HH before `pivot_index`.
- Existing PIVOT_POINT rejection, offset, and RR TP behavior unchanged.
- No database behavior touched; no DB E2E required.
- Unrelated untracked files `mql5/AureusProvider_v2.ex5` and `stable/` untouched/uncommitted.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-pae-th-c-hi-n-fix-todo-services-aureus-signa/260503-pae-SUMMARY.md`.
</output>
