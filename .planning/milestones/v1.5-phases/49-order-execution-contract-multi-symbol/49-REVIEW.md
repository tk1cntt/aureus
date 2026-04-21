---
phase: 49-order-execution-contract-multi-symbol
reviewed: 2026-04-20T16:07:03Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - services/aureus-nautilus-node/execution_client.py
  - services/aureus-nautilus-node/settings.py
  - services/aureus-nautilus-node/tests/test_execution_client.py
  - services/aureus-nautilus-node/tests/test_execution_risk_controls.py
  - services/aureus-nautilus-bridge/mapper.py
  - services/aureus-nautilus-bridge/main.py
  - services/aureus-nautilus-bridge/tests/test_mapper.py
findings:
  critical: 1
  warning: 3
  info: 0
  total: 4
status: issues_found
---

# Phase 49: Code Review Report

**Reviewed:** 2026-04-20T16:07:03Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Đã review các file source Python có tồn tại trong phạm vi được truyền vào. Phát hiện 1 lỗi mức Critical và 3 lỗi mức Warning liên quan trực tiếp đến contract thực thi lệnh: sai mapping khối lượng lệnh (`qty` vs `quantity`), polling stream chưa hỗ trợ multi-symbol theo whitelist, kiểm soát notional chưa đúng khi thiếu trường `notional`, và thiếu xử lý lỗi parse `sl/tp`.

Lưu ý: 4 file trong danh sách đầu vào không tồn tại trong worktree hiện tại nên không thể review nội dung các file đó:
- `services/aureus-nautilus-node/tests/test_execution_client_policy.py`
- `services/aureus-nautilus-node/tests/test_execution_multi_symbol_contract.py`
- `services/aureus-nautilus-bridge/tests/test_bridge_lineage.py`
- `services/aureus-nautilus-bridge/tests/test_order_payload_qty_alias.py`

## Critical Issues

### CR-01: Sai contract trường khối lượng lệnh làm gửi sai size

**File:** `services/aureus-nautilus-bridge/mapper.py:98`
**Issue:** `map_order_intent()` chỉ đọc `quantity` và mặc định `1.0` khi thiếu field này. Trong khi payload upstream/order intent ở node dùng `qty`. Kết quả là lệnh có thể bị thực thi sai khối lượng (ví dụ payload có `qty=5` nhưng bridge gửi `quantity=1.0`), đây là lỗi nghiệp vụ nghiêm trọng.
**Fix:** Hỗ trợ alias `qty` trước khi fallback mặc định, và reject khi cả hai đều thiếu/không hợp lệ.
```python
raw_qty = order_payload.get("quantity", order_payload.get("qty"))
if raw_qty is None:
    raise ValueError("Missing required fields: quantity")
quantity = float(raw_qty)
if quantity <= 0:
    raise ValueError("quantity must be > 0")
```

## Warnings

### WR-01: Polling order stream bị hardcode XAUUSD, không theo symbol whitelist

**File:** `services/aureus-nautilus-node/execution_client.py:74-82`
**Issue:** `_poll_loop()` và `_poll_orders_once()` luôn dùng stream `aureus:stream:XAUUSD:orders`, bỏ qua `symbol_whitelist` đã cấu hình. Điều này làm node không consume được lệnh của các symbol khác trong multi-symbol contract.
**Fix:** Khởi tạo `streams` dựa trên toàn bộ `self._symbol_whitelist`.
```python
streams = {
    f"aureus:stream:{symbol}:orders": self._last_ids.get(f"aureus:stream:{symbol}:orders", "0-0")
    for symbol in self._symbol_whitelist
}
```

### WR-02: Kiểm tra notional fallback về qty làm yếu risk control

**File:** `services/aureus-nautilus-node/execution_client.py:148-157`
**Issue:** Khi payload không có `notional`, code dùng `qty` làm notional để so sánh `max_order_notional`. Điều này có thể cho phép lệnh vượt giới hạn thực (ví dụ qty nhỏ nhưng giá rất lớn) mà không bị chặn.
**Fix:** Nếu không có `notional`, tính từ `qty * entry_price` (hoặc reject nếu thiếu dữ liệu giá theo policy rõ ràng).
```python
if data.get("notional") is not None:
    notional = float(data["notional"])
elif data.get("entry_price") is not None:
    notional = float(qty) * float(data["entry_price"])
else:
    return False, "INVALID_NOTIONAL", []
```

### WR-03: Parse `sl/tp` không được guard, có thể throw exception ngoài luồng validate

**File:** `services/aureus-nautilus-node/execution_client.py:165-168`
**Issue:** `sl = float(sl)` / `tp = float(tp)` không có `try/except`. Payload sai định dạng (`"sl": "abc"`) sẽ ném exception, làm hỏng vòng xử lý message thay vì reject có kiểm soát.
**Fix:** Bọc parse trong validate branch và trả về lỗi nghiệp vụ rõ ràng.
```python
try:
    sl = float(sl) if sl is not None else None
    tp = float(tp) if tp is not None else None
except (TypeError, ValueError):
    return False, "INVALID_SL_TP", []
```

---

_Reviewed: 2026-04-20T16:07:03Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
