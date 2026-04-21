# Phase 48: performance-backtest-api-wiring - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Khôi phục luồng E2E Performance Dashboard bằng cách chuẩn hóa và wire đầy đủ contract giữa web `/performance` và API `/api/v1/performance/*` (metrics, trades, equity-curve), bao gồm dữ liệu trả về, semantics filter, pagination/ordering, và freshness/caching để web render ổn định theo cùng một tập điều kiện lọc.

</domain>

<decisions>
## Implementation Decisions

### Data Contract (API ↔ Web)
- **D-01:** Chuẩn hóa response contract cho 3 endpoint performance theo hướng backward-compatible: chỉ bổ sung/chuẩn hóa field cần thiết, không phá field cũ đã được web sử dụng.
- **D-02:** Mọi field số liên quan hiệu năng (PnL, drawdown, win rate, RR, equity values) phải có kiểu dữ liệu nhất quán giữa API và web; nullability phải explicit để web không cần suy đoán.
- **D-03:** `metrics`, `trades`, `equity-curve` phải cùng phản ánh một bộ filter input để tránh lệch số liệu giữa cards/table/chart.

### Filter Semantics
- **D-04:** Chuẩn hóa bộ query params dùng chung cho 3 endpoint (symbol, strategy, timeframe, date-range) với default thống nhất và validation rõ ràng ở API.
- **D-05:** Khi filter không hợp lệ, API trả lỗi có cấu trúc ổn định (không silent fallback), web hiển thị trạng thái lỗi thay vì render số liệu sai.

### Pagination & Ordering
- **D-06:** Trades endpoint dùng pagination ổn định (`page`, `page_size`, `total`) và deterministic ordering để tránh nhảy bản ghi giữa các lần fetch.
- **D-07:** Rule sort mặc định phải cố định và được dùng xuyên suốt (không phụ thuộc ngầm vào storage order).

### Freshness & Caching
- **D-08:** Caching phải được áp dụng có chủ đích (TTL ngắn cho metrics) nhưng không tạo split-brain giữa metrics/trades/equity khi cùng filter.
- **D-09:** Ưu tiên correctness contract trước tối ưu hiệu năng; nếu cache khiến lệch dữ liệu cross-widget thì phải giảm/điều chỉnh cache policy để đảm bảo E2E consistency.

### Claude's Discretion
- Cách đặt tên field trung gian nội bộ trong API/service layer.
- Mức refactor tối thiểu cần thiết để gom logic filter validation mà vẫn giữ thay đổi surgical.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` (Phase 48 section) — định nghĩa goal, dependency, gap closure phạm vi phase.
- `.planning/REQUIREMENTS.md` — PERF-01..PERF-08 mapping và traceability status.

### Prior verification artifacts (phase 47 backfill)
- `.planning/phases/32-trade-performance-api/32-VERIFICATION.md` — trạng thái verification PERF-01..PERF-07 và ghi chú deferred integration.
- `.planning/phases/33-performance-dashboard-ui/33-VERIFICATION.md` — wiring `/performance` với API endpoints và manual gate E2E.
- `.planning/phases/47-verification-backfill-v1-5/47-02-SUMMARY.md` — baseline limitations và deferred integration notes từ đợt backfill.

### Runtime/API code paths
- `services/aureus-dashboard/api/main.py` — `/api/v1/performance/trades`, `/metrics`, `/equity-curve` implementation path.
- `services/aureus-dashboard/web/src/app/performance/page.tsx` — web consumer contract gọi 3 endpoint performance.
- `services/aureus-dashboard/web/src/components/Sidebar.tsx` — navigation entry `/performance`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/aureus-dashboard/api/main.py`: đã có sẵn performance endpoints, có thể chỉnh sửa trực tiếp để chuẩn hóa contract/filter thay vì tạo module mới.
- `services/aureus-dashboard/web/src/app/performance/page.tsx`: đã có flow fetch song song cho metrics/trades/equity, có thể giữ kiến trúc hiện tại và sửa mapping/params tối thiểu.

### Established Patterns
- Web dùng query string để đồng bộ filter với route `/performance`.
- API đã có pattern endpoint tách riêng theo resource (`/metrics`, `/trades`, `/equity-curve`) và có caching path cho metrics.

### Integration Points
- Điểm nối chính là contract response + query params giữa `page.tsx` và `api/main.py`.
- Mọi thay đổi phase 48 nên tập trung ở API performance handlers + parser/render trong performance page/components.

</code_context>

<specifics>
## Specific Ideas

- Ưu tiên “minimum-change wiring”: sửa đúng các đoạn contract/filter/pagination gây lệch E2E, tránh mở rộng scope sang analytics mới hoặc redesign UI.
- Kiểm chứng thành công phase bằng E2E consistency: cùng filter => cards/table/chart phản ánh cùng tập dữ liệu.

</specifics>

<deferred>
## Deferred Ideas

- Bổ sung capability analytics mới ngoài PERF-01..08 (ví dụ Sharpe/export nâng cao) giữ cho phase sau theo roadmap.
- Mọi chỉnh sửa liên quan order execution multi-symbol contract để phase 49 xử lý.

</deferred>

---

*Phase: 48-performance-backtest-api-wiring*
*Context gathered: 2026-04-20*
