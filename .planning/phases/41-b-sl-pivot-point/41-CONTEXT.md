# Phase 41: Bổ sung cơ chế SL theo điểm pivot point HH/LL gần nhất cho strategy - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning
**Source:** Discuss-phase (Phase 41 decisions locked)

<domain>
## Phase Boundary

Phase 41 bổ sung cơ chế Stop Loss mới `PIVOT_POINT` vào hệ thống, cho phép strategy đặt SL dựa trên swing point (HH cho SELL, LL cho BUY) thay vì FIXED_PIPS. Đây là cơ chế BỔ SUNG — FIXED_PIPS vẫn giữ nguyên, không thay thế.

**Phạm vi:**
- Thêm branch `PIVOT_POINT` vào `_calculate_sl_tp()` trong `engine/orders.py`
- Method mới `_find_pivot_for_sl()` trong `SimulatedTradeManager` để tìm swing point hợp lệ
- Cập nhật seed_strategies.py: 1-2 strategy demo dùng PIVOT_POINT (giữ nguyên các strategy còn lại FIXED_PIPS)
- Tests cho logic tìm pivot, offset, reject khi không có pivot

**Không phạm vi:**
- Không thay đổi cơ chế TP (TP vẫn dùng RR_RATIO như cũ)
- Không thay đổi cơ chế trailing stop
- Không thay đổi cơ chế SIGNAL_LOW/SIGNAL_HIGH hiện có

</domain>

<decisions>
## Implementation Decisions

### GA-1: Config format cho PIVOT_POINT
- **Chốt:** `{"type": "PIVOT_POINT", "offset_pips": 5}`
- `offset_pips` là optional, default = 0 nếu không ghi
- offset dùng để cộng thêm buffer vào giá pivot, tránh SL quá sát entry
- BUY: SL = pivot_price - (offset_pips * point_size)
- SELL: SL = pivot_price + (offset_pips * point_size)

### GA-2: Fallback khi không tìm thấy pivot
- **Chốt:** KHÔNG fallback về FIXED_PIPS
- Nếu không tìm thấy swing point hợp lệ → `return None, None` → trade bị reject ở `process_triggers()`
- Signal bị loại luôn nếu không đủ điều kiện
- Lý do: strategy đã chọn PIVOT_POINT = muốn SL dựa trên structure, dùng FIXED_PIPS thay thế là sai intent

### GA-3: "Gần nhất" — tiêu chí tìm swing point
- **Chốt:** Loại cụ thể HH/LL (strict SMC)
- BUY → tìm swing point `is_high=False` và `type="LL"` (Lower Low)
- SELL → tìm swing point `is_high=True` và `type="HH"` (Higher High)
- Duyệt ngược từ gần nhất về thời gian (reversed list)
- Ưu tiên pivot chưa broken (`broken != true`), nếu pivot gần nhất đã broken → lùi về pivot trước cùng loại
- Nếu không tìm được bất kỳ pivot nào cùng loại → reject trade

### Backward Compatibility
- FIXED_PIPS không thay đổi gì
- SIGNAL_LOW/SIGNAL_HIGH không thay đổi gì
- Chiến lược cũ vẫn hoạt động bình thường
- Chỉ strategy nào config `"type": "PIVOT_POINT"` mới dùng cơ chế mới

### Claude's Discretion
- Tên method, vị trí chính xác trong code
- Chi tiết test cases
- Lựa chọn strategy nào trong seed_strategies.py để demo PIVOT_POINT

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Logic
- `services/aureus-signal/engine/orders.py` — `_calculate_sl_tp()` (line 409-504), nơi thêm branch PIVOT_POINT
- `services/aureus-signal/engine/state.py` — `swing_points` structure (line 98), list of dicts với keys: t, price, is_high, type, broken
- `services/aureus-signal/engine/signals/pivots.py` — nơi swing_points được tạo và cập nhật

### Strategy Config
- `services/aureus-signal/engine/strategies/seed_strategies.py` — 8 seed strategies, tất cả đang dùng FIXED_PIPS
- `services/aureus-signal/engine/strategies/template.py` — `build_order_plan()` (line 934-985)
- `services/aureus-signal/engine/snapshot_utils.py` — REQUIRED_ORDER_PLAN_KEYS, VALID_ENTRY_TYPES, VALID_SIZE_MODES

### Data Flow
- `services/aureus-signal/engine/symbols.json` — point size cho từng symbol, dùng để tính offset_distance

</canonical_refs>

<specifics>
## Specific Ideas

### Swing point structure (từ pivots.py):
```python
{
    "t": unix_timestamp,
    "price": float,
    "is_high": bool,
    "type": "HH" | "LL" | "LH" | "HL",
    "broken": bool (optional),
    "is_choch": bool (optional),
    "ob": dict (optional),
    ...
}
```

### _calculate_sl_tp() hiện tại hỗ trợ:
- `FIXED_PIPS` — value * point_size
- `SIGNAL_LOW` / `SIGNAL_HIGH` — lấy giá từ signal hoặc swing_points

### Cần thêm:
- `PIVOT_POINT` — tìm swing point hợp lệ, áp dụng offset

### Ví dụ config strategy sau khi cập nhật:
```json
// PIVOT_POINT SL
"sl": {"type": "PIVOT_POINT", "offset_pips": 5}

// FIXED_PIPS (giữ nguyên)
"sl": {"type": "FIXED_PIPS"}
```

</specifics>

<deferred>
## Deferred Ideas

- None — phase scope đầy đủ, không có ý tưởng deferred

</deferred>

---

*Phase: 41-b-sl-pivot-point*
*Context gathered: 2026-04-14 via discuss-phase*
