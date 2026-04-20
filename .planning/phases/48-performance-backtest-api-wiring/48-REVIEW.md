---
phase: 48-performance-backtest-api-wiring
reviewed: 2026-04-20T12:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - services/aureus-dashboard/api/main.py
  - services/aureus-dashboard/api/tests/conftest.py
  - services/aureus-dashboard/api/tests/test_performance_contract.py
  - services/aureus-dashboard/web/package.json
  - services/aureus-dashboard/web/vitest.config.ts
  - services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx
  - services/aureus-dashboard/web/src/app/performance/page.tsx
  - services/aureus-dashboard/web/src/app/performance/components/EquityChart.tsx
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-04-20T12:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Đã review các file API và UI cho performance dashboard ở mức `standard` (đọc full file theo ngữ cảnh). Có 2 vấn đề chính: 1 lỗi nghiêm trọng có thể làm crash runtime ở API (Redis client async/sync dùng sai kiểu), và 1 lỗi contract giữa frontend/backend khiến thông báo lỗi filter không hiển thị đúng theo API thực tế.

## Critical Issues

### CR-01: Await trên Redis sync client gây lỗi runtime

**File:** `services/aureus-dashboard/api/main.py:63, 168, 204, 318, 449, 470, 502, 509, 525, 550, 564, 566, 579, 582, 634`
**Issue:** Biến `r` được khởi tạo từ `redis_sync.Redis(...)` (sync client) nhưng lại được gọi bằng `await` ở nhiều endpoint (`await r.scan`, `await r.get`, `await r.publish`, ...). Điều này gây `TypeError` tại runtime vì sync method không awaitable.
**Fix:** Đồng bộ hóa cách dùng client: hoặc chuyển `r` sang async client, hoặc bỏ `await` và chạy sync call theo cách phù hợp. Cách an toàn nhất cho code hiện tại là dùng async client cho `r`.

```python
# main.py
import redis.asyncio as redis_async

# dùng async client cho toàn bộ endpoint async
r = redis_async.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# (tuỳ chọn) giữ redis_client làm alias nếu muốn
redis_client = r
```

## Warnings

### WR-01: Frontend parse sai format error envelope của backend

**File:** `services/aureus-dashboard/web/src/app/performance/page.tsx:91-117`
**Issue:** `parseErrorMessage` đang đọc lỗi theo dạng `body.error.code` / `body.error.message`, nhưng backend trả envelope top-level dạng `{ error: string, code: string, details: {...} }` (xem `_error_envelope` ở API). Kết quả là UI có thể hiển thị `Unknown error` hoặc không map đúng lỗi filter.
**Fix:** Parse theo đúng contract top-level, đồng thời fallback cho cả 2 format để tương thích ngược.

```ts
interface ApiErrorEnvelope {
  code?: string;
  error?: string;
  details?: Record<string, unknown>;
  message?: string;
}

const parseErrorMessage = (status: number, body: ApiErrorEnvelope): string => {
  const code = body.code;
  const message = body.error || body.message || "Unknown error";
  if (code?.startsWith("INVALID_")) {
    return `Invalid filter: ${message}`;
  }
  return `API error (${status}): ${message}`;
};
```

---

_Reviewed: 2026-04-20T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
