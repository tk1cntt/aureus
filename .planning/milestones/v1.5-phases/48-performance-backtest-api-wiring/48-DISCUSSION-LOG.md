# Phase 48: performance-backtest-api-wiring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 48-performance-backtest-api-wiring
**Areas discussed:** Contract data, Filter semantics, Pagination & ordering, Freshness & caching

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Contract data | Chốt schema response chuẩn cho metrics/trades/equity-curve (field bắt buộc, nullability, units/precision) để web và API không lệch format. | ✓ |
| Filter semantics | Chốt rule filter theo symbol/strategy/timeframe/date-range: default values, validation, và cách API/web đồng bộ query params. | ✓ |
| Pagination & ordering | Chốt page/page_size/sort cho trades list: stable ordering, total count contract, và behavior khi page vượt range. | ✓ |
| Freshness & caching | Chốt nhất quán dữ liệu giữa 3 endpoint (metrics/trades/equity): TTL cache, staleness chấp nhận được, và fallback khi data source thiếu. | ✓ |

**User's choice:** Chọn cả 4 vùng quyết định để đưa vào context phase.
**Notes:** Không mở rộng scope ngoài boundary phase 48; tập trung khôi phục wiring E2E dashboard/api.

---

## Claude's Discretion

- Naming nội bộ cho parsing/normalization layers
- Cách tối ưu thay đổi tối thiểu trong API/web để đạt consistency

## Deferred Ideas

- Capability analytics mới ngoài PERF-01..08
- Gaps thuộc order execution multi-symbol để phase 49 xử lý
