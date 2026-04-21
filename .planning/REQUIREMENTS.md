# Requirements: Aureus

**Defined:** 2026-04-21  
**Milestone:** v1.6 Strategy Evaluation & Insight Delivery  
**Core Value:** Đánh giá strategy đa tiêu chí có thể truy vết, phục vụ quyết định bằng dữ liệu chuẩn hóa.

## v1.6 Requirements

### Scoring Framework (SCOR)

- [ ] **SCOR-01**: Định nghĩa scoring framework đa tiêu chí cho strategy gồm tối thiểu: profit outcome, quality signal, timing quality, volatility/session context.
- [ ] **SCOR-02**: Hỗ trợ cấu hình trọng số tiêu chí (versioned) để tính điểm tổng hợp nhất quán theo từng lần đánh giá.
- [ ] **SCOR-03**: Tính điểm ở 2 cấp: per-trade score và aggregate score (strategy/symbol/timeframe).
- [ ] **SCOR-04**: Lưu score breakdown theo từng tiêu chí (không chỉ final score) để audit và giải thích quyết định.

### Data Model & Pipeline (EVAL)

- [ ] **EVAL-01**: Thiết kế schema DB chuẩn hóa cho dữ liệu đánh giá trade/strategy (score, breakdown, context, score_version, timestamp).
- [ ] **EVAL-02**: Pipeline ingestion/compute/persist đảm bảo mỗi trade có evaluation record đầy đủ và truy vết được nguồn dữ liệu.
- [ ] **EVAL-03**: Backfill/recompute pipeline cho phép tính lại điểm khi thay đổi scoring weights/version mà không mất lịch sử phiên bản cũ.
- [ ] **EVAL-04**: Data quality guards cho evaluation pipeline (idempotency key, uniqueness, null/constraint checks) để tránh duplicate/sai lệch.
- [ ] **SIGNAL-SNAPSHOT-01**: Lưu signal snapshot theo mô hình hybrid (JSONB raw + typed hot columns + index theo symbol/timeframe/time-range) để hỗ trợ vừa mở rộng schema vừa query nhanh trên volume lớn; các field dẫn xuất (ví dụ `ema21_above_ema55`) không persist vật lý, tính downstream bằng pandas/SQL expression.

### Reporting Engine (RPT)

- [ ] **RPT-01**: Report per-trade (drill-down) hiển thị score breakdown + context đầy đủ.
- [ ] **RPT-02**: Report aggregate theo strategy/symbol/timeframe.
- [ ] **RPT-03**: Report lọc theo market session (Asia/London/NY hoặc mapping tương đương theo config hệ thống).
- [ ] **RPT-04**: Report lọc theo volatility regime (low/normal/high hoặc thang đo tương đương theo config).
- [ ] **RPT-05**: Report hỗ trợ tiêu chí mở rộng (extensible dimensions) như signal family, entry type, risk profile mà không phá vỡ schema hiện tại.

### Telegram Insight Delivery (TEL-EVAL)

- [ ] **TEL-EVAL-01**: Telegram output gửi insight đánh giá per-trade với score tổng + breakdown các tiêu chí chính.
- [ ] **TEL-EVAL-02**: Telegram output gửi insight tổng hợp định kỳ theo strategy/symbol/timeframe dựa trên dữ liệu đã chuẩn hóa trong DB.
- [ ] **TEL-EVAL-03**: Nội dung Telegram bắt buộc có ngữ cảnh market session + volatility regime + confidence/quality flags.
- [ ] **TEL-EVAL-04**: Telegram insight phải tham chiếu được evaluation record id/version để đảm bảo traceability.

### Acceptance Focus (ACC)

- [ ] **ACC-01**: Khung chấm điểm strategy được chốt và chạy end-to-end trước các phần mở rộng khác.
- [ ] **ACC-02**: Milestone output bắt buộc có đủ 3 trụ: DB chuẩn hóa + reporting nhiều chiều + Telegram insight.
- [ ] **ACC-03**: Có cả phân tích sâu từng lệnh (per-trade) và phân tích tổng hợp phục vụ quyết định (aggregate).

## Definition of Done Checklist — SIGNAL-SNAPSHOT-01

### 1) Schema & Constraints

- [ ] **TC-SIG-001 (Schema columns)**
  - **Given** migration đã apply
  - **When** inspect schema `aureus_trade_signal_snapshots`
  - **Then** phải có đủ cột lineage: `trade_journal_id`, `trace_id`, `ticket`, `symbol`, `timeframe`, `signal_schema_version`, `created_at`.

- [ ] **TC-SIG-002 (Raw payload JSONB)**
  - **Given** một event signal hợp lệ
  - **When** persist snapshot
  - **Then** cột `signal_snapshot JSONB` lưu full payload tại thời điểm persist.

- [ ] **TC-SIG-003 (Typed hot columns)**
  - **Given** payload có CISD/EMA
  - **When** persist snapshot
  - **Then** typed columns `cisd_direction`, `ema21`, `ema55` được lưu đúng giá trị.

- [ ] **TC-SIG-004 (Derived field policy)**
  - **Given** schema snapshot
  - **When** kiểm tra cấu trúc cột
  - **Then** không có cột vật lý `ema21_above_ema55`; field này chỉ tính downstream bằng pandas/SQL expression.

- [ ] **TC-SIG-005 (Uniqueness/idempotency)**
  - **Given** đã có row `(trade_journal_id=A, signal_schema_version=V1)`
  - **When** insert lại cùng key
  - **Then** bị chặn bởi `UNIQUE (trade_journal_id, signal_schema_version)` hoặc no-op theo `ON CONFLICT`.

- [ ] **TC-SIG-006 (FK lineage)**
  - **Given** `trade_journal_id` không tồn tại trong `aureus_trade_journal`
  - **When** insert snapshot
  - **Then** bị reject bởi FK `aureus_trade_journal(id)`.

- [ ] **TC-SIG-007 (JSON quality check)**
  - **Given** payload `signal_snapshot` không phải object hoặc rỗng
  - **When** insert snapshot
  - **Then** bị reject bởi CHECK constraint.

### 2) Index & Performance (Large Volume)

- [ ] **TC-SIG-008 (Index presence)**
  - **Given** migration hoàn tất
  - **When** inspect index metadata
  - **Then** có đủ index:
    - BTREE `(symbol, timeframe, created_at DESC)`
    - BTREE `(symbol, timeframe, cisd_direction, created_at DESC)`
    - BRIN `(created_at)`.

- [ ] **TC-SIG-009 (Hot query index usage)**
  - **Given** dataset lớn (time-range rộng)
  - **When** chạy EXPLAIN/ANALYZE cho truy vấn hot theo `symbol/timeframe/cisd/time-range`
  - **Then** planner sử dụng đúng index mục tiêu (không full table scan ở case truy vấn nóng).

### 3) Runtime Pipeline Boundary

- [ ] **TC-SIG-010 (Boundary guard)**
  - **Given** event trước `ORDER_OPENED` (ví dụ `STRATEGY_MATCH`)
  - **When** pipeline chạy
  - **Then** không tạo signal snapshot row.

- [ ] **TC-SIG-011 (Persist on ORDER_OPENED)**
  - **Given** `ORDER_OPENED` thành công, có lineage đầy đủ
  - **When** `on_order_opened` được gọi
  - **Then** tạo đúng 1 row snapshot với `trade_journal_id/trace_id/ticket` hợp lệ.

### 4) Recompute/Backfill

- [ ] **TC-SIG-012 (Append-only recompute)**
  - **Given** trade đã có snapshot `signal_schema_version=V1`
  - **When** recompute với `signal_schema_version=V2`
  - **Then** tạo row mới V2, không overwrite row V1.

- [ ] **TC-SIG-013 (Recompute idempotency)**
  - **Given** đã recompute xong version V2
  - **When** rerun lại cùng version V2
  - **Then** không tạo duplicate rows.

### 5) Mandatory Test Suite (Green)

- [ ] **TC-SIG-014 (Migration tests pass)**
  - `services/aureus-trader/tests/test_signal_snapshot_migration.py` = green.

- [ ] **TC-SIG-015 (Pipeline tests pass)**
  - `services/aureus-trader/tests/test_signal_snapshot_pipeline.py` = green.

- [ ] **TC-SIG-016 (Recompute tests pass)**
  - `services/aureus-trader/tests/test_signal_snapshot_recompute.py` = green.

- [ ] **TC-SIG-017 (Integrated subset pass)**
  - Chạy full subset signal snapshot + evaluation liên quan và tất cả đều green.

### 6) Execution Evidence

- [ ] Có log command verify + exit code 0 cho toàn bộ test case trên.
- [ ] Có artifact EXPLAIN/ANALYZE cho truy vấn hot để chứng minh readiness thực thi production-scale.


## Non-Goals (v1.6)

- Không mở rộng sang execution optimization ngoài phạm vi evaluation/reporting.
- Không thay đổi broker/exchange integration scope hiện tại.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCOR-01 | Phase 54 | Planned |
| SCOR-02 | Phase 54 | Planned |
| SCOR-03 | Phase 54 | Planned |
| SCOR-04 | Phase 54 | Planned |
| EVAL-01 | Phase 55 | Planned |
| EVAL-02 | Phase 55 | Planned |
| EVAL-03 | Phase 55 | Planned |
| EVAL-04 | Phase 55 | Planned |
| SIGNAL-SNAPSHOT-01 | Phase 55 | Planned |
| RPT-01 | Phase 56 | Planned |
| RPT-02 | Phase 56 | Planned |
| RPT-03 | Phase 56 | Planned |
| RPT-04 | Phase 56 | Planned |
| RPT-05 | Phase 56 | Planned |
| TEL-EVAL-01 | Phase 57 | Planned |
| TEL-EVAL-02 | Phase 57 | Planned |
| TEL-EVAL-03 | Phase 57 | Planned |
| TEL-EVAL-04 | Phase 57 | Planned |
| ACC-01 | Phase 54 | Planned |
| ACC-02 | Phase 57 | Planned |
| ACC-03 | Phase 56 | Planned |

**Coverage:**
- v1.6 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-21 after v1.6 milestone rebaseline*