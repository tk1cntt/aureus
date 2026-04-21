# Research Summary: Aureus (Stack / Features / Architecture / Pitfalls)

**Generated:** 2026-04-21  
**Purpose:** Bản hợp nhất dùng trực tiếp cho `REQUIREMENTS.md` và `ROADMAP.md`

## 1) Executive summary

Aureus đang có nền tảng kỹ thuật tốt cho giai đoạn mở rộng gần hạn: pipeline event-driven rõ ràng (Gateway → Signal → Execution → DB Writer → Dashboard), stack hiện đại (FastAPI/Next.js/Redis/TimescaleDB), và đã có một phần quality gate thực tế.

Tuy nhiên, rủi ro lớn nhất hiện tại không nằm ở “thiếu tính năng”, mà nằm ở **độ tin cậy liên service và chuẩn hóa vận hành**:
- Drift runtime/dependency/CI giữa các service.
- Một số lỗi có thể gây sai lệch dữ liệu hoặc mất message theo kiểu silent.
- Security baseline và observability contract chưa đồng đều.

=> Hướng roadmap khuyến nghị: **Stabilize trước, scale sau**.

---

## 2) Consolidated findings

### A. Stack (hiện trạng + mức sẵn sàng)

**Hiện trạng chính**
- Backend: Python microservices (gateway, signal, db-writer, nautilus-node/bridge, dashboard-api).
- Frontend: Next.js 16 + React 19 + TypeScript + Tailwind.
- Data/Event: Redis Streams + TimescaleDB.
- Runtime/Deploy: Docker Compose (dev/prod).
- Observability: Prometheus + Grafana + exporters.

**Điểm mạnh**
- Kiến trúc service tách vai trò tương đối rõ.
- Redis + Timescale phù hợp workload realtime + time-series.
- Có nền monitoring và test ở một số vùng trọng yếu.

**Khoảng trống**
- Python runtime đang trộn 3.11/3.12.
- Dependency pinning và quality gate chưa đồng đều toàn hệ.
- Dùng image tag `latest` ở vài thành phần làm giảm reproducibility.

### B. Features (mức hoàn thiện)

**Implemented (core flow mạnh):**
- Ingestion ZMQ/TCP + validate + dedup + backfill.
- Signal compute + strategy hot-reload.
- Persistence tick/candle/execution/position/account.
- Dashboard state/chart + strategy CRUD/assignment.
- Risk gate execution (idempotency, allowlist, SL/TP policy).

**Partial/Missing đáng chú ý:**
- Backtest UI có nhưng endpoint backend `/api/v1/backtest/*` chưa thấy trong API service hiện tại.
- AuthN/AuthZ chưa được enforce rõ ràng ở API chính.
- Một số path execution còn dấu hiệu hardcode stream theo symbol cụ thể.

### C. Architecture (điểm nghẽn và khả năng tiến hóa)

**Hiện trạng kiến trúc:** event-driven microservices, Redis là backbone.

**Coupling/Bottleneck chính:**
- Contract-by-key giữa service qua Redis stream fields.
- Redis đóng vai trò rất trung tâm (nguy cơ SPOF logic).
- Signal engine đang gánh nhiều trách nhiệm trong cùng process.
- DB writer đơn khối xử lý nhiều stream type.

**Khả năng mở rộng sẵn có:**
- Per-symbol stream partitioning.
- Consumer groups.
- Execution modes/adapter path có nền để mở rộng.

### D. Pitfalls/Risks (ưu tiên xử lý)

**Rủi ro P0/P1 nổi bật:**
1. ACK-on-failure trong bridge có thể gây silent loss (Critical).
2. Duplicate insert path ở db-writer gây rủi ro integrity (High).
3. Insecure/default credentials và fallback password (Critical/High).
4. API/control surface chưa harden đầy đủ (High).
5. `except ...: pass` ở runtime làm khó vận hành sự cố (High).
6. Observability doc/rule/config có điểm lệch + nguy cơ trộn dev/prod telemetry.

---

## 3) Requirements implications (đề xuất đưa vào REQUIREMENTS)

### Functional requirements (ưu tiên)
- FR-1: Core pipeline ingest→signal→execution/persist phải hoạt động ổn định cho multi-symbol.
- FR-2: Recovery flow (request backfill) phải chạy end-to-end và có xác nhận kết quả.
- FR-3: Backtest capability phải được quyết định rõ:
  - hoặc implement backend endpoint đầy đủ,
  - hoặc de-scope/ẩn UI để tránh false capability.

### Non-functional requirements (bắt buộc)
- NFR-1: Reliability semantics rõ cho stream processing (ACK success-only, DLQ, retry/replay policy).
- NFR-2: Data integrity guardrails (idempotency/uniqueness cho tick/execution writes).
- NFR-3: Security baseline (không default secret, AuthN/AuthZ, CORS strict, harden control channels).
- NFR-4: Cross-service quality gates đồng đều (test/lint/type/build).
- NFR-5: Observability contract nhất quán (metric, labels env, alert rules, runbook).

---

## 4) Roadmap recommendation (phase-oriented)

### Phase 1 — Reliability & Security Baseline (P0)
- Sửa ACK-on-failure, thiết lập DLQ/retry tối thiểu.
- Sửa duplicate insert path + regression tests.
- Remove insecure defaults/fallback secrets; enforce prod secret policy.
- Thêm AuthN/AuthZ tối thiểu cho API/control endpoints nhạy cảm.

**Outcome:** giảm rủi ro mất dữ liệu/sai dữ liệu/sự cố bảo mật ngay lập tức.

### Phase 2 — Standardization & Contract Governance (P0/P1)
- Chuẩn hóa Python version + dependency pin policy.
- Chuẩn hóa image version pinning.
- Thiết lập schema/version hóa contract cho stream payload.
- Mở rộng CI quality gates cho toàn bộ service.

**Outcome:** tăng reproducibility, giảm regression liên service.

### Phase 3 — Architecture Decoupling for Scale (P1)
- Tách bớt trách nhiệm khỏi signal engine (đặc biệt AI path).
- Cân nhắc tách writer theo domain nóng.
- Hoàn thiện multi-symbol execution flow.

**Outcome:** cải thiện throughput và khả năng scale theo symbol.

### Phase 4 — Product Completeness (P1/P2)
- Chốt hướng backtest (build đủ backend hoặc de-scope UI).
- Chuẩn hóa API response contract và nâng UX realtime.
- Nâng cấp observability E2E latency và vận hành release gate.

**Outcome:** trải nghiệm sản phẩm đồng bộ với năng lực backend thực tế.

---

## 5) Priority matrix (gợi ý nhanh)

- **P0 ngay:** reliability semantics + data integrity + security baseline.
- **P1 kế tiếp:** cross-service standardization + contract governance + execution completeness.
- **P2 sau ổn định:** UX/performance optimizations và advanced product capabilities.

---

## 6) Decision checkpoints cho chủ sản phẩm

1. Backtest có phải cam kết MVP không?  
2. Mức bắt buộc cho AuthN/AuthZ ở giai đoạn hiện tại?  
3. Chuẩn runtime mục tiêu (Python 3.12 toàn hệ) có chốt ngay phase kế tiếp không?  
4. Ưu tiên tốc độ feature hay ưu tiên ổn định vận hành trong 1-2 sprint tới?

---

## 7) Suggested immediate next action

Dùng summary này để cập nhật:
1. `REQUIREMENTS.md`: thêm FR/NFR theo mục 3.  
2. `ROADMAP.md`: tạo/điều chỉnh phase theo mục 4 (ưu tiên Phase 1 trước).  
3. `MILESTONES.md`: gắn tiêu chí nghiệm thu đo được cho từng phase reliability/security.
