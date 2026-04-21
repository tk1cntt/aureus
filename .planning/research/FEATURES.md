# Feature Landscape (FEATURES Axis)

**Project:** Aureus (Code Intelligence / Trading Signal Platform)
**Researched:** 2026-04-21
**Scope:** Capability inventory from code + artifacts only (no speculative product claims)

## 1) Feature map by domain

## A. Core flows (business-critical runtime)

| Feature | Domain | Status | MVP/Core? | Evidence trail |
|---|---|---|---|---|
| Ingest market data qua ZMQ/TCP (TICK/CANDLE) | Ingestion | Implemented | Core (P0) | `services/aureus-gateway/main.py:182-199, 263-274` |
| Validate schema message (Pydantic) trước khi ingest | Ingestion quality | Implemented | Core (P0) | `services/aureus-gateway/main.py:34-67, 80-92` |
| Dedup/old-message reject theo timestamp | Stream integrity | Implemented | Core (P0) | `services/aureus-gateway/main.py:100-105` |
| Backfill candle flow (chunk ingest) | Data recovery | Implemented | Core (P0) | `services/aureus-gateway/main.py:129-178` |
| Forward command từ Redis về EA connector | Execution bridge | Implemented | Core (P0) | `services/aureus-gateway/main.py:278-313` |
| Signal engine consume candle stream + evaluate signals/strategies | Signal processing | Implemented | Core (P0) | `services/aureus-signal/engine/live_engine.py:386-507` |
| Strategy hot-reload qua Redis pubsub | Runtime control | Implemented | Core (P0) | `services/aureus-signal/engine/live_engine.py:329-346` |
| Persist tick/candle/swing_point vào TimescaleDB | Persistence | Implemented | Core (P0) | `services/aureus-db-writer/main.py:120-233`, `services/aureus-db-writer/schema.sql:4-43` |
| Persist execution/position/account snapshots/events | Auditability | Implemented | Core (P0) | `services/aureus-db-writer/main.py:235-319`, `schema.sql:94-151` |
| Nautilus live node lifecycle (bootstrap/warmup/live/shutdown) | Execution runtime | Implemented | Core (P0) | `services/aureus-nautilus-node/main.py:34-69` |
| Strict execution risk policy (allowlist, SL/TP required, max notional, trace_id idempotency) | Risk control | Implemented | Core (P0) | `services/aureus-nautilus-node/execution_client.py:117-187` |
| SyncWorker envelope versioning + DLQ | Contract robustness | Implemented | Core (P0) | `services/aureus-nautilus-node/sync_worker.py:67-125` |

## B. User-facing features (Dashboard/UI + public API)

| Feature | Surface | Status | MVP/Core? | Evidence trail |
|---|---|---|---|---|
| Symbol catalog + online/offline enrichment | API + UI selector | Implemented | Core (P0) | `api/main.py:89-136`; UI uses symbol list in multiple pages |
| Live state endpoint per symbol (OB/FVG/swing/signals/orders) | API | Implemented | Core (P0) | `api/main.py:137-158` |
| Chart endpoint hợp nhất DB history + Redis realtime | API | Implemented | Core (P0) | `api/main.py:159-313` |
| Dashboard realtime polling, chart render, settings localStorage | Web | Implemented | Core (P0) | `web/src/app/page.tsx:89-151, 238-246` |
| Force symbol recovery từ UI/API | User recovery action | Implemented | Core (P0) | `web/src/app/page.tsx:74-87, 209-217`; `api/main.py:453-467` |
| Strategy CRUD (template) | API + Web | Implemented | Core (P0) | `api/main.py:315-411`; `web/src/app/strategies/page.tsx:64-143` |
| Strategy assignment/toggle per symbol | API + Web | Implemented | Core (P0) | `api/main.py:413-451`; `web/src/app/strategies/page.tsx:83-92` |
| AI health check + latest/history analysis | API + AI Insights page | Implemented | P1 (value-add) | `api/main.py:469-482, 525-580`; `web/src/app/ai-insights/page.tsx:24-55` |
| Runtime LLM model switching | API + UI model selector | Implemented | P1 | `api/main.py:483-508`; Signal listens at `live_engine.py:349-370` |
| Backtest page UI (run/poll/load history) | Web | **Partial** | P1/P2 | UI exists: `web/src/app/backtest/page.tsx:99-173`; API endpoints `/api/v1/backtest/*` not found in `api/main.py` |

## C. Admin / internal / ops features

| Feature | Status | MVP/Core? | Evidence trail |
|---|---|---|---|
| Prometheus alert rules + rollout gate artifacts | Implemented | P1 (prod ops) | `docs/reports/nautilus-production-handover-2026-03-19.md:17-25` |
| Production hardening plan + test evidence (21 tests pass) | Implemented | P1 | `docs/plans/2026-03-19-nautilus-deep-integration-production-plan.md`, handover report lines `28-38` |
| Versioned contract + DLQ for sync failures | Implemented | Core/P0 for safe scaling | `sync_worker.py:67-125` |
| Global config stream command (LLM model changed) | Implemented | P1 | `api/main.py:503`, `live_engine.py:349-370` |

---

## 2) User journeys hiện có

## Journey 1: Theo dõi live market + SMC state
1. User mở dashboard, chọn symbol.
2. UI gọi `/chart/{symbol}`, `/state/{symbol}`, `/ai/latest/{symbol}` theo polling.
3. API stitch dữ liệu DB + Redis trả về candles/swing_points/OB/state.
4. User xem chart + active monitoring.

**Trace:** `web/src/app/page.tsx:98-151` + `api/main.py:159-313`.

## Journey 2: Quản trị strategy library
1. User vào trang Strategies.
2. Tạo/sửa/xóa strategy template.
3. Gán strategy cho symbol, API publish refresh command.
4. Signal engine nhận `aureus:cmd:refresh_strategies`, reload runtime registry.

**Trace:** `web/src/app/strategies/page.tsx:64-143` + `api/main.py:315-451` + `live_engine.py:329-346`.

## Journey 3: Recovery khi feed lỗi/mất dữ liệu
1. User bấm Force Recovery trên dashboard.
2. API publish `REQUEST_BACKFILL_COUNT` vào `aureus:mt5:commands`.
3. Gateway forward command về active EA connection theo symbol.
4. Gateway nhận backfill candles, push stream để downstream xử lý.

**Trace:** `web/src/app/page.tsx:74-87` + `api/main.py:453-467` + `gateway/main.py:278-313, 129-178`.

## Journey 4: AI observability
1. User mở AI Insights.
2. UI đọc AI health, latest analysis, history.
3. User có thể đổi model (ModelSelector -> API set model).
4. Signal engine nhận command stream và cập nhật model validator runtime.

**Trace:** `web/src/app/ai-insights/page.tsx:24-55` + `api/main.py:469-508, 525-580` + `live_engine.py:349-370`.

## Journey 5: Execution risk gate (internal/trading)
1. ORDER_OPEN đi vào execution stream.
2. Execution client validate trace_id/symbol/side/qty/notional/SLTP.
3. Invalid => reject + metrics; valid => generate ENTRY + SL/TP contingent orders.

**Trace:** `execution_client.py:96-187`.

---

## 3) Missing capabilities (gap from code/artifacts)

## Missing (high impact)
1. **Backtest API endpoints chưa hiện diện trong service API hiện tại**
   - UI gọi `/api/v1/backtest/run`, `/status/{task_id}`, `/runs`, nhưng `services/aureus-dashboard/api/main.py` không có route `@app.*("/api/v1/backtest...")`.
   - **Impact:** Backtest user journey có UI nhưng khó chạy end-to-end trên codebase snapshot này.

2. **AuthN/AuthZ cho dashboard API chưa thấy trong implementation hiện tại**
   - Không có dependency/middleware auth trên các endpoint chính.
   - Architecture doc có nhắc JWT nhưng code route hiện không enforce.
   - **Impact:** Thiếu tenant/user isolation và kiểm soát quyền cho production.

## Missing/Partial (moderate)
3. **Multi-symbol order stream trong execution client còn hardcoded XAUUSD stream**
   - `_poll_loop` mặc định đọc `aureus:stream:XAUUSD:orders`.
   - **Impact:** hạn chế scale execution đa symbol nếu chưa có lớp orchestration khác bù vào.

4. **API schema consistency chưa đồng đều**
   - Response format không thống nhất wrapper status/error như kiến trúc đề xuất; route trả thẳng dict/list.
   - **Impact:** tăng chi phí tích hợp client và handling lỗi.

5. **Một số tính năng non-core đang dựa vào polling (2-3s) thay vì push/subscription**
   - Dashboard + AI Insights polling liên tục.
   - **Impact:** tốn tài nguyên và tăng latency perceived khi scale user dashboard.

---

## 4) Priority suggestions (P0/P1/P2)

## P0 (MVP/Core business - phải chắc trước roadmap release)
1. Ổn định chuỗi core: ingest → signal → persistence → state API.
2. Đảm bảo strict risk controls (SL/TP mandatory, idempotency trace_id, symbol allowlist).
3. Đảm bảo recovery flow hoạt động thật (UI recover → command bridge → backfill ingest).
4. Khóa gap backtest API nếu backtest là requirement MVP; nếu không, tắt/ẩn UI backtest để tránh false promise.

## P1 (quan trọng sau khi P0 ổn)
1. Bổ sung AuthN/AuthZ thực thi cho dashboard API.
2. Hoàn thiện execution multi-symbol stream handling.
3. Chuẩn hóa API response/error contract.
4. Nâng chất lượng observability (SLO dashboards + alert tuning + runbook drills).

## P2 (nice-to-have / optimization)
1. Giảm polling bằng streaming/WebSocket cho dashboard realtime.
2. Nâng cấp UX chiến lược/backtest (reporting sâu hơn, comparison run).
3. Mở rộng admin tooling cho governance model/strategy lifecycle.

---

## MVP vs Nice-to-have classification (explicit)

## MVP/Core business
- Data ingestion + validation + dedup + backfill.
- Signal engine realtime computation + state publication.
- Persistence các bảng thị trường và execution audit cốt lõi.
- Dashboard live chart/state tối thiểu + strategy CRUD + symbol assignment.
- Strict execution risk gates và idempotency.

## Nice-to-have (giai đoạn sau)
- AI model switching UI-driven (không bắt buộc để chạy core signal platform).
- Institutional AI insight nâng cao (history/audit deep view).
- Backtest visual analytics nâng cao (nếu chưa phải product promise chính ngay MVP).

---

## Confidence assessment

- **Overall confidence:** MEDIUM-HIGH.
- **HIGH** cho các feature có code path trực tiếp trong `services/*`.
- **MEDIUM** cho phân loại product priority (vì cần alignment business owner).
- **HIGH** cho gap backtest API (đã kiểm route hiện có và không thấy endpoint backtest trong API service snapshot này).

## Notes
- Kết luận chỉ dựa trên artifacts/code hiện hữu trong worktree này.
- Không xác nhận các service/endpoint có thể nằm ở repo khác hoặc branch khác.