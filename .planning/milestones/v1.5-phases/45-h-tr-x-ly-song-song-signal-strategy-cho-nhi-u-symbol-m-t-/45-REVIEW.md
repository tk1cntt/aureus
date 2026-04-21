---
phase: 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
reviewed: 2026-04-18T12:18:53Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/tests/test_multi_symbol.py
  - services/aureus-signal/unittest/test_orders_events.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 45: Code Review Report

**Reviewed:** 2026-04-18T12:18:53Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Đã review ở mức `standard` cho các file source có thể truy cập trong scope phase 45. Có 3 vấn đề mức Warning trong `live_engine.py` liên quan tới tính đúng đắn và độ tin cậy runtime (đếm sai nhịp xử lý, xử lý queue task chưa an toàn khi exception, nuốt exception trong khối tính signal hồi phục trạng thái). Ngoài ra có 1 Info về artifact debug trong test.

Lưu ý: Các file sau được yêu cầu nhưng không tồn tại trong worktree hiện tại nên không thể review nội dung: 
- `services/aureus-signal/engine/strategy_executor.py`
- `services/aureus-signal/engine/symbol_runtime.py`
- `services/aureus-signal/tests/test_circuit_breaker.py`
- `services/aureus-signal/tests/test_live_engine_shadow_mode.py`
- `services/aureus-signal/tests/test_out_of_order_drop_policy.py`
- `services/aureus-signal/tests/test_per_symbol_worker_runtime.py`
- `services/aureus-signal/tests/test_strategy_trigger_lifecycle.py`
- `services/aureus-signal/tests/test_symbol_slo_rollback.py`

## Warnings

### WR-01: `candle_count` bị tăng 2 lần cho mỗi CANDLE

**File:** `services/aureus-signal/engine/live_engine.py:469,544`
**Issue:** `candle_count` được increment ở cả line 469 và 544 trong cùng flow xử lý một candle. Điều này làm lệch các điều kiện dựa trên modulo (`candle_count % 5`, `% 20`), gây sync/snapshot/log theo chu kỳ không đúng tần suất kỳ vọng.
**Fix:** Chỉ tăng 1 lần tại một vị trí thống nhất sau khi xử lý candle thành công.

```python
# Giữ lại duy nhất 1 chỗ increment, ví dụ cuối flow success
# ... xử lý xong
candle_count += 1

if sync_mode == "ALWAYS" or has_event or (candle_count % 5 == 0):
    ...
```

### WR-02: `brain_worker` không `task_done()` khi task ném exception

**File:** `services/aureus-signal/engine/live_engine.py:582-593`
**Issue:** `queue.task_done()` chỉ được gọi ở nhánh thành công. Nếu `execute_pulse`/`execute_audit` ném exception, task sẽ không được mark done, có thể gây treo các logic dùng `queue.join()` và làm sai trạng thái hàng đợi.
**Fix:** Đưa `task_done()` vào `finally` sau khi lấy task ra khỏi queue.

```python
while True:
    priority = _counter = task_type = payload = None
    try:
        priority, _counter, task_type, payload = await queue.get()
        if task_type == 'PULSE':
            await execute_pulse(payload, r, db_pool, validator)
        elif task_type == 'AUDIT':
            await execute_audit(payload, r, db_pool, validator, manager)
    except Exception as e:
        logger.error(f"[GLOBAL] [brain_worker] Error: Brain Worker Error: {e}")
        await asyncio.sleep(1)
    finally:
        if task_type is not None:
            queue.task_done()
```

### WR-03: Nuốt exception trong vòng lặp tính signal khi hydrate delta

**File:** `services/aureus-signal/engine/live_engine.py:245-254`
**Issue:** Khối `except Exception as e: pass` làm mất hoàn toàn thông tin lỗi khi signal calculation thất bại trong giai đoạn catch-up. Điều này làm khó phát hiện lỗi logic và có thể gây state thiếu tín hiệu mà không có dấu vết.
**Fix:** Ghi log tối thiểu với symbol/tag/timestamp; nếu muốn tránh noisy, dùng `logger.debug` có throttle.

```python
except Exception as e:
    logger.warning(
        f"[{symbol}] hydrate-delta signal error tag={tag} t={candle_data.get('t')}: {e}"
    )
```

## Info

### IN-01: Debug/CLI artifact trong test unit

**File:** `services/aureus-signal/tests/test_multi_symbol.py:40,46,58,79`
**Issue:** Test có nhiều `print(...)` phục vụ chạy tay. Không phải lỗi correctness, nhưng làm output test runner nhiễu và khó đọc khi CI chạy nhiều test.
**Fix:** Ưu tiên assert-based test, chỉ giữ output khi thật cần thiết hoặc dùng logging có mức độ.

---

_Reviewed: 2026-04-18T12:18:53Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
