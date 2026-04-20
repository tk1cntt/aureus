---
phase: 48-performance-backtest-api-wiring
reviewed: 2026-04-20T13:10:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - services/aureus-dashboard/api/main.py
  - services/aureus-dashboard/api/tests/conftest.py
  - services/aureus-dashboard/api/tests/test_performance_contract.py
  - services/aureus-dashboard/web/src/app/performance/page.tsx
  - services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-04-20T13:10:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Đã review đúng 5 file trong phạm vi phase 48 ở mức `standard` (đọc toàn bộ nội dung từng file). Có 1 lỗi nghiêm trọng ở API có thể gây lỗi runtime khi gọi Redis trong endpoint async. Ngoài ra có 2 cảnh báo về logic lọc tham số và hợp đồng API ở frontend, cùng 1 vấn đề chất lượng mã trong API.

## Critical Issues

### CR-01: Dùng Redis sync client nhưng gọi bằng `await` trong async endpoint

**File:** `services/aureus-dashboard/api/main.py:63, 168, 204, 318, 449, 470, 502, 509, 525, 550, 564, 566, 579, 582, 634`
**Issue:** Biến `r` được khởi tạo từ `redis_sync.Redis(...)` (client đồng bộ) nhưng lại được gọi bằng `await` ở nhiều endpoint (`await r.get(...)`, `await r.scan(...)`, `await r.publish(...)`, ...). Các method sync không awaitable, có thể gây `TypeError` và làm endpoint trả 500.
**Fix:** Chuẩn hóa toàn bộ endpoint async dùng Redis async client.

```python
# Thay sync client
# r = redis_sync.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Bằng async client
r = redis_async.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# (Tuỳ chọn) dùng một biến duy nhất để tránh nhầm lẫn
redis_client = r
```

## Warnings

### WR-01: Mất filter `strategy_id=0` do kiểm tra truthy thay vì null-check

**File:** `services/aureus-dashboard/web/src/app/performance/page.tsx:198, 261`
**Issue:** Khi build query string đang dùng `if (strategyId)` và `if (filters.strategyId)`. Nếu `strategy_id=0` là giá trị hợp lệ theo backend/domain, tham số sẽ bị bỏ khỏi request vì `0` là falsy, dẫn đến sai kết quả lọc.
**Fix:** Dùng kiểm tra tường minh `!== null` (hoặc `!= null`) thay cho truthy check.

```ts
if (strategyId !== null) sharedParams.set("strategy_id", String(strategyId));

// ...
if (filters.strategyId !== null) {
  params.set("strategy_id", String(filters.strategyId));
}
```

### WR-02: Frontend xử lý lỗi giả định JSON luôn parse được

**File:** `services/aureus-dashboard/web/src/app/performance/page.tsx:217-219`
**Issue:** Khi response lỗi (`!ok`), code gọi thẳng `await firstFailed.json()`. Nếu backend/proxy trả body không phải JSON (HTML lỗi, text lỗi gateway), đoạn này sẽ ném exception parse JSON và che mất lỗi gốc, làm message hiển thị không chính xác.
**Fix:** Bọc parse bằng `try/catch` và fallback message khi không parse được JSON.

```ts
let errorBody: ApiErrorEnvelope = {};
try {
  errorBody = (await firstFailed.json()) as ApiErrorEnvelope;
} catch {
  throw new Error(`API error (${firstFailed.status})`);
}
throw new Error(parseErrorMessage(firstFailed.status, errorBody));
```

## Info

### IN-01: Import trùng lặp làm giảm độ rõ ràng mã nguồn

**File:** `services/aureus-dashboard/api/main.py:8, 15`
**Issue:** `import os` được khai báo 2 lần. Không gây lỗi runtime nhưng làm tăng nhiễu và dễ tạo nhầm lẫn khi review.
**Fix:** Giữ một import duy nhất.

---

_Reviewed: 2026-04-20T13:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
