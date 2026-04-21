---
phase: 46-strategy-seed-sync
reviewed: 2026-04-19T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - services/aureus-signal/engine/strategies/seed_strategies.py
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/engine/strategy_executor.py
  - services/aureus-signal/tests/test_strategy_seed_sync.py
  - services/aureus-signal/scripts/strategy_seed_sync_dryrun.py
  - services/aureus-signal/scripts/strategy_seed_sync_rollback.py
findings:
  critical: 1
  warning: 3
  info: 0
  total: 4
status: issues_found
---

# Phase 46: Code Review Report

**Reviewed:** 2026-04-19T00:00:00Z  
**Depth:** standard  
**Files Reviewed:** 6  
**Status:** issues_found

## Summary

Đã review toàn bộ phạm vi file được chỉ định cho phase 46, tập trung vào logic đồng bộ seed strategy, dry-run/rollback script, và luồng nạp/thi hành strategy trong engine.

Phát hiện 1 lỗi nghiêm trọng về tính đúng đắn của dry-run transaction (rollback không bao phủ phần seed thực tế), cùng 3 warning về mất dữ liệu rollback trong một số trường hợp và xử lý lỗi chưa an toàn trong engine runtime.

## Critical Issues

### CR-01: Dry-run không thực sự rollback toàn bộ thay đổi seed

**File:** `services/aureus-signal/scripts/strategy_seed_sync_dryrun.py:97`

**Issue:**
Trong dry-run, code mở transaction trên `conn` hiện tại (`tx = conn.transaction()`), nhưng lại gọi `await seed_system_strategies(pool)`. Hàm seed sẽ `pool.acquire()` lại, có thể lấy **connection khác** ngoài transaction đã mở. Khi đó `tx.rollback()` chỉ rollback transaction của connection hiện tại, còn thay đổi ở connection khác vẫn có thể commit, khiến dry-run gây mutate DB thật.

**Fix:**
Gọi seed trên **cùng connection** hoặc sửa `seed_system_strategies` để nhận `conn` tùy chọn và dùng connection hiện tại trong transaction.

```python
# Ví dụ: cho phép truyền conn vào seed
async def seed_system_strategies(pool=None, conn=None):
    if conn is None:
        async with pool.acquire() as conn:
            await _seed_with_conn(conn)
    else:
        await _seed_with_conn(conn)

# dry-run
async with pool.acquire() as conn:
    tx = conn.transaction()
    await tx.start()
    try:
        before = await _fetch_assignments(conn)
        await seed_system_strategies(conn=conn)
        after = await _fetch_assignments(conn)
        raise _DryRunRollback()
    except _DryRunRollback:
        await tx.rollback()
```

## Warnings

### WR-01: Rollback không khôi phục được record bị thiếu

**File:** `services/aureus-signal/scripts/strategy_seed_sync_rollback.py:96-105`

**Issue:**
Rollback chỉ chạy `UPDATE ... WHERE symbol = $1 AND strategy_id = $2`. Nếu row trong snapshot không còn tồn tại trong DB hiện tại, rollback sẽ không tạo lại row đó, dẫn đến trạng thái khôi phục không đầy đủ so với snapshot.

**Fix:**
Dùng UPSERT (`INSERT ... ON CONFLICT DO UPDATE`) để đảm bảo mọi cặp `(symbol, strategy_id)` trong snapshot đều được restore đúng trạng thái `is_active`.

### WR-02: Nuốt exception khi tính signal lúc hydrate state

**File:** `services/aureus-signal/engine/live_engine.py:253-254`

**Issue:**
Trong vòng lặp hydrate delta candles, block `except Exception as e: pass` nuốt hoàn toàn lỗi signal calculation. Điều này che giấu lỗi runtime, làm state sau hydrate có thể sai nhưng không có log để điều tra.

**Fix:**
Ít nhất log warning/error có đủ context `symbol`, `tag`, timestamp để truy vết.

### WR-03: `candle_count` tăng 2 lần cho cùng một candle

**File:** `services/aureus-signal/engine/live_engine.py:469` và `services/aureus-signal/engine/live_engine.py:544`

**Issue:**
Trong nhánh xử lý một `CANDLE`, biến `candle_count` được tăng ở đầu và cuối cùng loop. Điều này làm lệch các điều kiện phụ thuộc đếm (`candle_count % 5`, `% 20`) và log throughput, gây hành vi không đúng kỳ vọng.

**Fix:**
Chỉ tăng một lần cho mỗi candle (thường ở cuối khi xử lý thành công), hoặc tách rõ counter cho “received” và “processed”.

---

_Reviewed: 2026-04-19T00:00:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
