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
- v1.6 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-21 after v1.6 milestone rebaseline*