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

- [x] **EVAL-01**: Thiết kế schema DB chuẩn hóa cho dữ liệu đánh giá trade/strategy (score, breakdown, context, score_version, timestamp).
- [x] **EVAL-02**: Pipeline ingestion/compute/persist đảm bảo mỗi trade có evaluation record đầy đủ và truy vết được nguồn dữ liệu.
- [x] **EVAL-03**: Backfill/recompute pipeline cho phép tính lại điểm khi thay đổi scoring weights/version mà không mất lịch sử phiên bản cũ.
- [x] **EVAL-04**: Data quality guards cho evaluation pipeline (idempotency key, uniqueness, null/constraint checks) để tránh duplicate/sai lệch.
- [x] **SIGNAL-SNAPSHOT-01**: Lưu signal snapshot theo mô hình hybrid (JSONB raw + typed hot columns + index theo symbol/timeframe/time-range) để hỗ trợ vừa mở rộng schema vừa query nhanh trên volume lớn; các field dẫn xuất (ví dụ `ema21_above_ema55`) không persist vật lý, tính downstream bằng pandas/SQL expression.
- [x] **EVAL-RUNTIME-01**: Runtime DB schema parity là gate bắt buộc trước khi mark complete phase dữ liệu (bảng/index/constraints phải tồn tại trên DB dev thật, không chỉ trong file migration/test unit).
- [ ] **EVAL-RUNTIME-02**: Migration compatibility phải được thiết kế theo capability của PostgreSQL runtime; không dùng biểu thức CHECK không tương thích version engine.
- [x] **EVAL-RUNTIME-03**: Trường business-critical cho recompute (ví dụ `timeframe`) phải có nguồn chuẩn trong schema lineage; fallback từ JSON chỉ là tạm thời và phải có kế hoạch loại bỏ.
- [x] **EVAL-RUNTIME-04**: Bắt buộc có bằng chứng E2E persistence runtime (row thật mới nhất cho evaluation + signal snapshot) trong checklist nghiệm thu.

### Architecture Decision Note — Phase 55 Runtime Parity

- **ADN-55-01 (Chosen):** Hybrid strategy: (1) migration compatibility theo runtime PG capability + (2) runtime schema gate + (3) migration tiếp theo để chuẩn hóa lineage field `timeframe` tại `aureus_trade_journal`.
- **Rationale:** Giữ tính tương thích vận hành ngắn hạn nhưng vẫn tiến tới data model đúng về dài hạn, tránh false-positive "phase complete".
- **Execution guardrails:**
  - Không chốt phase nếu thiếu `aureus_trade_signal_snapshots` trên runtime DB hoặc bảng evaluations đã xóa vẫn còn tồn tại.
  - Không chốt phase nếu recompute còn phụ thuộc fallback JSON mà chưa có kế hoạch migration lineage.
  - Mọi thay đổi migration phải pass cả test migration + query runtime kiểm chứng.

### Decision-linked Test Addendum

- [ ] **TC-EVAL-RUNTIME-001:** Runtime DB có bảng signal snapshot hiện hành và không còn bảng evaluations đã xóa.
- [ ] **TC-EVAL-RUNTIME-002:** Runtime DB có đủ index/unique chính cho hai bảng phase 55.
- [ ] **TC-EVAL-RUNTIME-003:** Chạy recompute trên window thực, có row snapshot mới (kiểm tra `MAX(created_at)`).
- [ ] **TC-EVAL-RUNTIME-004:** Không còn tình trạng pass test nhưng thiếu schema runtime.
- [ ] **TC-EVAL-RUNTIME-005:** Có ticket follow-up migration để chuẩn hóa nguồn `timeframe` từ schema lineage, không phụ thuộc JSON fallback vĩnh viễn.

### Trade-off Record (for future review)

- Chọn compatibility migration giúp deploy nhanh hơn nhưng tăng chi phí quản trị nhiều biến thể migration.
- Giữ fallback `timeframe` từ snapshot giúp không block runtime ngay, nhưng tăng rủi ro semantic drift nếu kéo dài.
- Chuẩn hóa lineage `timeframe` bằng migration riêng tăng effort ngắn hạn, đổi lại giảm rủi ro dữ liệu sai trong recompute dài hạn.

### Adversarial Risks (must monitor)

- Runtime nâng cấp PostgreSQL/Timescale có thể làm compatibility expression hiện tại không còn tối ưu hoặc sai planner.
- Fallback `timeframe='M1'` có thể tạo dữ liệu đánh giá sai nếu trade thực tế ở TF khác.
- Migration apply thành công nhưng pipeline event không đẩy đủ trường scoring/snapshot vẫn làm bảng rỗng và tạo false confidence.

### Required Runtime Evidence (sign-off)

- `SELECT tablename FROM pg_tables ... IN ('aureus_trade_signal_snapshots') và xác nhận bảng evaluations đã xóa không tồn tại`
- `SELECT indexname FROM pg_indexes ...`
- - `SELECT COUNT(*), MAX(created_at) FROM aureus_trade_signal_snapshots`
- Mẫu 5 rows mới nhất có `trace_id, symbol, timeframe, version` cho snapshot table.

### Follow-up Constraint

- Không merge milestone v1.6 nếu chưa có phase follow-up chuẩn hóa `timeframe` lineage trong `aureus_trade_journal`.

**Last architectural review update:** 2026-04-22


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


## Architecture Addendum — Strategy-aware MT5 Position Management

**Recorded:** 2026-05-01
**Scope:** `mql5/AureusProvider_v2.mq5` position management after order execution.
**Goal:** Quản lý lệnh theo strategy đầu vào thay vì dùng một bộ rule cố định cho mọi `symbol + magic + direction`.

### Requirements

- [ ] **STRAT-MGMT-01**: Position management phải giữ group identity tối thiểu là `symbol + magic + direction` để không trộn lệnh giữa symbol, strategy hoặc hướng giao dịch khác nhau.
- [ ] **STRAT-MGMT-02**: Provider phải resolve được management profile từ `magic` hoặc strategy identity; nếu không match thì dùng default profile an toàn.
- [ ] **STRAT-MGMT-03**: Mỗi profile phải tách rõ điều kiện và action quản lý lệnh, ví dụ: hold, move SL to breakeven, tighten SL, close single, close basket.
- [ ] **STRAT-MGMT-04**: Không được dùng rule global “single profitable age > 30m thì close” cho mọi strategy; rule này chỉ được bật trong profile cụ thể nếu strategy đó cần time-stop.
- [ ] **STRAT-MGMT-05**: Mọi quyết định quản lý lệnh phải log đủ: `symbol`, `magic`, `direction`, `profile`, `action`, `reason`, `positions_count`, `net_profit`, `age_seconds` và ticket/action target nếu có.
- [ ] **STRAT-MGMT-06**: Phase đầu chỉ hỗ trợ built-in profiles trong MQL5 để giảm rủi ro runtime; external config/file chỉ là phase sau khi metrics chứng minh cần thiết.
- [ ] **STRAT-MGMT-07**: Các profile ban đầu nên giới hạn ở nhóm tối thiểu: `trend_runner`, `breakout_protect`, `basket_escape`; các profile khác chỉ thêm khi có strategy cụ thể cần.
- [ ] **STRAT-MGMT-08**: Close action phải conservative by default; ưu tiên move SL/breakeven/trailing trước khi auto-close, trừ khi profile có rule rõ ràng.

### Suggested Initial Profiles

| Profile | Mục tiêu | Rule trọng tâm | Không nên làm |
|---|---|---|---|
| `trend_runner` | Giữ lệnh thắng để chạy trend | BE/trailing theo profit hoặc structure | Không close lệnh lời chỉ vì quá 30 phút |
| `breakout_protect` | Bảo vệ breakout fail nhanh | Time-stop hoặc tighten SL nếu không đi đúng hướng sau N phút | Không giữ lệnh fail quá lâu chỉ vì chưa chạm SL |
| `basket_escape` | Thoát basket/DCA khi recover | Close basket khi net positive hoặc đạt ngưỡng recover | Không áp dụng cho single trend entry |

### Acceptance Tests

- [ ] **TC-STRAT-MGMT-001**: Hai lệnh cùng symbol nhưng khác magic dùng hai profile khác nhau và sinh decision khác nhau theo rule profile.
- [ ] **TC-STRAT-MGMT-002**: `trend_runner` không auto-close single profitable position chỉ vì age > 30 phút.
- [ ] **TC-STRAT-MGMT-003**: `basket_escape` vẫn có thể close group nhiều position khi net profit/recovery đạt điều kiện.
- [ ] **TC-STRAT-MGMT-004**: Magic không có mapping dùng default profile và log rõ fallback.
- [ ] **TC-STRAT-MGMT-005**: Decision log chứa đủ field bắt buộc để audit vì sao lệnh bị move SL/close/hold.
- [ ] **TC-STRAT-MGMT-006**: Compile `AureusProvider_v2.mq5` bằng MetaEditor đạt `0 errors, 0 warnings`.

### Architecture Decision

- **Chosen direction:** Built-in strategy profile engine trong provider, mapping `magic -> profile` bằng input string ngắn gọn ở phase đầu.
- **Deferred:** External JSON/file config, runtime hot-reload, expression DSL cho rule động.
- **Rationale:** MQL5 không phù hợp để bắt đầu bằng config engine phức tạp; built-in profiles đủ để gỡ rule global sai, dễ compile/test, ít surface lỗi hơn.

### Adversarial Risks

- Mapping sai magic có thể áp dụng nhầm policy và close/move SL sai strategy.
- Quá nhiều profile ngay từ đầu sẽ biến provider thành rule engine khó debug.
- Nếu chỉ log action mà không log `reason/profile/state`, về sau vẫn khó truy nguyên vì sao lệnh bị cắt.
- Nếu external config được đưa vào quá sớm, lỗi parse/config có thể làm provider fail trong runtime MT5.

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