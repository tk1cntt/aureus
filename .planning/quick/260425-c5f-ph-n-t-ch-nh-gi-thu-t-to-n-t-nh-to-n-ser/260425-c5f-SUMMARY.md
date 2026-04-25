# Quick Task 260425-c5f Summary

## Objective
Phân tích đánh giá thuật toán/tính toán trong `services/aureus-trader/journal.py`, xác định hệ thống hiện xử lý trade journal như thế nào, các điểm tối ưu cần cải thiện, và đưa ra khuyến nghị kiến trúc theo quy trình 4 bước.

## Kết luận ngắn
`journal.py` không phải module tính indicator/strategy score theo nghĩa signal engine, mà là **trade lifecycle persistence + normalization pipeline**:

1. `on_strategy_match()` tạo entry `TRIGGERED` khi có strategy match.
2. `on_order_opened()` update entry sang `EXECUTED`, insert evaluation snapshot và signal snapshot canonical columns.
3. `on_order_closed()` update entry sang `CLOSED`, tính duration/result/pnl_pips cơ bản.
4. Helper functions normalize/extract dữ liệu từ event, active_signals, context_filters, MT5 timestamps.

Điểm cần tối ưu chính không nằm ở thuật toán tính toán nặng, mà nằm ở **tính nhất quán lifecycle, giảm round-trip DB, tách nhỏ trách nhiệm, idempotency/schema conflict rõ ràng, và tránh fire-and-forget làm mất lỗi**.

---

## Evidence từ code

### Runtime flow
- `services/aureus-trader/main.py`
  - `run_trader()` subscribe Redis strategy channel.
  - Khi nhận `STRATEGY_MATCH`: validate → `build_order_command()` → idempotency → enqueue dispatcher.
  - Khởi tạo `TradeJournalManager(db_pool)` rồi inject vào `OrderDispatcher`.

- `services/aureus-trader/dispatcher.py`
  - Trong `dispatch_order()`, khi MT5 trả `ORDER_OPENED`:
    - gọi `journal.on_strategy_match(strategy_payload)` trước.
    - inject/fallback `trace_id`, `signal_snapshot`, scoring fields.
    - gọi `journal.on_order_opened(final)`.
  - Trong `event_listener()`, khi có `ORDER_CLOSED`/`ORDER_CLOSED_PARTIAL`:
    - normalize time.
    - gọi `asyncio.create_task(self.journal.on_order_closed(event))` fire-and-forget.

### journal.py functions
- `_strip_excluded_signal_states()` loại bỏ state tags không muốn persist.
- `_to_float_or_none()` normalize numeric field.
- `_first_present()` ưu tiên snapshot rồi event.
- `_extract_active_signal_fields()` scan `active_signals` list để extract supported indicator fields.
- `_build_signal_snapshot_columns()` merge snapshot/event/context filters thành canonical signal snapshot columns.
- `_normalize_session_code()` map session text/number sang code 1/2/3.
- `_normalize_polarity_code()` map bullish/bearish sang 1/-1.
- `on_strategy_match()` validate `trace_id/strategy_name/direction/symbol`, normalize `active_signals/context_filters/origin_timestamp`, insert `aureus_trade_journal` với `ON CONFLICT DO NOTHING`.
- `on_order_opened()` validate MT5 ticket/price/time, update journal `TRIGGERED → EXECUTED`, fetch journal row, insert `aureus_trade_evaluations` nếu đủ scoring core, insert `aureus_trade_signal_snapshots`.
- `on_order_closed()` lookup row, normalize close time/reason, tính duration/result/pnl_pips, update journal `CLOSED`.

---

# Bước 1: Liệt kê và Phân rã (Neutral Listing)

## Phương án A — Giữ monolithic TradeJournalManager hiện tại
Đặc điểm kỹ thuật:
- Một class xử lý toàn bộ lifecycle persistence.
- Validation, normalization, SQL, evaluation insert, signal snapshot insert nằm cùng `journal.py`.
- Mỗi event gọi trực tiếp DB qua asyncpg pool.
- Dùng `ON CONFLICT DO NOTHING` cho idempotency DB cấp insert.

## Phương án B — Extract service functions theo lifecycle stage
Đặc điểm kỹ thuật:
- Tách logic thành các module/function nhỏ:
  - `strategy_match_journal.py`
  - `order_opened_journal.py`
  - `order_closed_journal.py`
  - `signal_snapshot_mapper.py`
  - `evaluation_persistence.py`
- `TradeJournalManager` chỉ orchestrate các service functions.
- SQL có thể vẫn inline hoặc chuyển sang constants/repository.

## Phương án C — Repository/Data Mapper layer
Đặc điểm kỹ thuật:
- Tạo repository chuyên trách DB operations:
  - `TradeJournalRepository`
  - `TradeEvaluationRepository`
  - `TradeSignalSnapshotRepository`
- Manager build domain DTO/canonical payload, repository execute SQL.
- Có boundary rõ giữa business normalization và persistence.

## Phương án D — Transactional lifecycle unit-of-work
Đặc điểm kỹ thuật:
- Các DB writes liên quan cùng event được chạy trong transaction.
- `on_order_opened()` update journal + insert evaluation + insert snapshot trong một transaction.
- Có thể lock row hoặc dùng `UPDATE ... RETURNING` để tránh fetch lại.
- Conflict/idempotency được define theo unique keys và affected rows.

## Phương án E — Async durable journal queue
Đặc điểm kỹ thuật:
- Dispatcher không gọi DB trực tiếp trong hot path.
- Journal events được publish vào Redis Stream/Kafka/Postgres queue.
- Worker riêng consume và persist theo retry/backoff/dead-letter.
- Cho phép backpressure, replay, monitoring lag.

## Phương án F — Event-sourced trade journal
Đặc điểm kỹ thuật:
- Lưu raw immutable lifecycle events trước: `STRATEGY_MATCH`, `ORDER_OPENED`, `ORDER_CLOSED`.
- Projection job build/update `aureus_trade_journal`, evaluations, snapshots.
- Cho phép replay khi mapping/schema thay đổi.
- Cần event schema version và projection version.

## Phương án G — Stored procedure / DB-side upsert pipeline
Đặc điểm kỹ thuật:
- Đẩy một phần lifecycle transition vào PostgreSQL function.
- App truyền JSON/event canonical vào DB function.
- DB function validate/update/insert related rows.
- Giảm round-trip nhưng tăng logic ở DB.

---

# Bước 2: Phân tích theo Tiêu chí (Attribute Mapping)

## Mạnh nhất về runtime latency hot path
1. **Phương án E — Async durable queue**: dispatcher chỉ enqueue journal event, DB write chạy ngoài hot path.
2. **Phương án G — Stored procedure**: ít round-trip DB, một call có thể làm nhiều writes.
3. **Phương án D — Transactional unit-of-work tối ưu SQL**: giảm acquire/fetch/update rời rạc, nhưng vẫn synchronous DB.
4. **Phương án C/B**: latency gần hiện tại nếu chưa đổi SQL/I/O.
5. **Phương án A**: dễ tăng latency khi `on_order_opened()` làm nhiều thao tác DB tuần tự.
6. **Phương án F**: append event nhanh nếu chỉ append raw, nhưng projection end-to-end latency phụ thuộc worker.

## Mạnh nhất về correctness/consistency lifecycle
1. **Phương án D — Transactional unit-of-work**: update journal + evaluation + snapshot có cùng boundary transaction.
2. **Phương án F — Event-sourced**: raw event không mất, có thể replay và audit đầy đủ.
3. **Phương án E — Durable queue**: nếu queue durable + retry/dead-letter tốt, ít mất event hơn fire-and-forget.
4. **Phương án C — Repository layer**: consistency tăng nhờ boundary rõ, nhưng cần transaction policy.
5. **Phương án B**: tốt hơn monolith về testability nhưng chưa tự đảm bảo atomicity.
6. **Phương án A**: hiện có rủi ro partial write và khó thấy lỗi `on_order_closed()` fire-and-forget.
7. **Phương án G**: consistency mạnh trong DB, nhưng correctness phụ thuộc stored procedure khó review/test bằng Python.

## Mạnh nhất về maintainability/testability
1. **Phương án C — Repository/Data Mapper layer**: dễ unit test mapper riêng, repository riêng.
2. **Phương án B — Extract service functions**: thay đổi vừa phải, giảm kích thước `journal.py` nhanh.
3. **Phương án D**: tốt nếu đi kèm repository, nhưng transaction orchestration phức tạp hơn.
4. **Phương án A**: ít file nhưng class đang ôm quá nhiều trách nhiệm.
5. **Phương án E/F**: maintainability vận hành thấp hơn vì thêm queue/projection/retry semantics.
6. **Phương án G**: Python tests khó bao phủ DB logic nếu không có E2E DB.

## Mạnh nhất về khả năng replay/backfill khi schema đổi
1. **Phương án F — Event-sourced**: replay raw events theo projection version là native.
2. **Phương án E — Durable queue/stream**: có thể replay nếu retention đủ và event schema ổn.
3. **Phương án C/D**: replay phải dựa vào existing tables hoặc external logs.
4. **Phương án A/B/G**: không tự tạo nền tảng replay tốt nếu raw event không được lưu.

## Trade-off chính

### Chọn E thay vì D/C
Mất:
- Simplicity trong codebase hiện tại.
- Debug trực tiếp theo stack trace đơn giản.
- Immediate DB consistency ngay trong call path.
- Cần vận hành queue lag, retry, DLQ.

Được:
- Dispatcher hot path ít bị DB latency ảnh hưởng.
- Có backpressure/retry rõ hơn fire-and-forget.
- Có khả năng hấp thụ burst ORDER_CLOSED/ORDER_OPENED tốt hơn.

### Chọn D thay vì A
Mất:
- Code transaction/SQL phức tạp hơn một chút.
- Cần test E2E DB kỹ hơn khi đổi schema/constraint.

Được:
- Giảm partial-write inconsistency.
- Dễ định nghĩa idempotency bằng affected rows/unique keys.
- Có thể gom `UPDATE ... RETURNING` để giảm query.

### Chọn C/B thay vì E/F
Mất:
- Không giải quyết triệt để replay/durable async pipeline.
- Hot path vẫn có thể bị DB latency nếu giữ synchronous writes.

Được:
- Thay đổi nhỏ, rủi ro thấp.
- Test dễ hơn, ít dependency vận hành.
- Phù hợp với giai đoạn cần ổn định schema và mapping.

### Chọn F thay vì C/D
Mất:
- Độ đơn giản và tốc độ ship.
- Phải thiết kế event schema/projection version/retention.
- Cần xử lý duplicate/order-of-events nghiêm ngặt.

Được:
- Audit trail mạnh nhất.
- Replay/backfill tốt nhất khi signal/evaluation schema thay đổi.
- Tách raw facts khỏi derived projections.

---

# Bước 3: Đề xuất dựa trên Context (Contextual Recommendation)

## Context thực tế của Aureus
- `journal.py` đang nằm trong service Python `aureus-trader`, dùng asyncpg và Redis events.
- Hệ thống vừa có nhiều quick task sửa signal snapshot/evaluation mapping, cho thấy schema journal/snapshot đang thay đổi nhanh.
- Có yêu cầu cao về correctness với MT5 timestamps: entry/exit time phải lấy từ MT5, không fallback tùy tiện.
- Có nhiều bảng liên quan cùng lifecycle event: `aureus_trade_journal`, `aureus_trade_evaluations`, `aureus_trade_signal_snapshots`.
- `on_order_opened()` hiện khá lớn, trộn validate/update/evaluation/snapshot mapping/SQL/logging.
- `ORDER_CLOSED` đang được persist bằng `asyncio.create_task(...)`, tức không block event listener nhưng lỗi/backlog khó kiểm soát.
- Project đã có test rộng cho journal, signal snapshot, recompute; khi sửa database phải test E2E DB.

## Recommendation tối ưu
**Chọn lộ trình B + C + D trước, chưa nhảy ngay sang E/F.**

Cụ thể:
1. **B — Extract mapper/service functions** để giảm kích thước `journal.py`:
   - `build_strategy_match_record(event)`
   - `build_order_opened_record(event, journal_row)`
   - `build_signal_snapshot_columns(...)` giữ nhưng có typed boundary rõ hơn
   - `build_order_closed_record(event, journal_row)`
2. **C — Repository layer tối thiểu** cho SQL:
   - `update_opened_and_fetch_context(trace_id, opened_record)` dùng `UPDATE ... RETURNING` thay vì `UPDATE` rồi `SELECT`.
   - `insert_evaluation(...)`
   - `insert_signal_snapshot(...)`
   - `close_trade(...)`
3. **D — Transactional unit-of-work cho `on_order_opened()`**:
   - Journal update + evaluation insert + signal snapshot insert nên cùng transaction.
   - Nếu evaluation core missing thì snapshot vẫn insert, nhưng decision này được log/return rõ trong transaction.

## Vì sao chưa chọn E/F ngay?
- Hiện bottleneck rõ nhất là maintainability/consistency trong `journal.py`, không phải throughput chứng minh bằng benchmark.
- Async durable queue/event sourcing sẽ thêm vận hành phức tạp khi schema snapshot/evaluation vẫn đang biến động.
- Nếu thêm queue trước khi canonical mapping ổn định, rủi ro là queue chỉ làm lỗi khó debug hơn.

## Lựa chọn tốt nhất hiện tại
**Giai đoạn 1: “Journal Unit-of-Work + Repository Extraction”**.

Nên làm trong task thực thi kế tiếp:
1. Tách pure mapping/normalization khỏi DB write để unit test dễ hơn.
2. Đổi `on_order_opened()` sang một transaction duy nhất.
3. Dùng `UPDATE aureus_trade_journal ... RETURNING id, strategy_name, symbol, active_signals, context_filters, timeframe` để bỏ query `SELECT` thứ hai.
4. Chuẩn hóa conflict key của snapshot:
   - hiện `ON CONFLICT (trade_journal_id) DO NOTHING`, trong khi các task gần đây từng dùng `(trade_journal_id, signal_schema_version)` ở recompute. Cần chốt semantic một snapshot/trade hay một snapshot/schema version.
5. Không để `ORDER_CLOSED` fire-and-forget vô hạn:
   - bước nhẹ: wrap task callback log exception.
   - bước tốt hơn: bounded async journal queue trong process.

---

# Bước 4: Chế độ Phản biện Nghịch đảo (Adversarial Mode)

Giả sử chọn recommendation Giai đoạn 1: “Journal Unit-of-Work + Repository Extraction”. Các fail scenarios:

## Fail scenario 1 — Transaction làm tăng latency ORDER_OPENED hot path
Nếu `dispatch_order()` chờ `journal.on_order_opened(final)` hoàn tất trước khi return, việc gom nhiều DB write vào transaction có thể làm result processing chậm hơn khi DB latency tăng.

Rủi ro kiến trúc bị bỏ qua:
- MT5 ACK/result path đang synchronous theo order.
- Pool hiện trong `main.py` chỉ `max_size=3`.
- Nếu nhiều order mở cùng lúc, journal transaction có thể cạnh tranh connection.

Mitigation:
- Benchmark p95/p99 `on_order_opened()` trước/sau.
- Tăng pool hoặc dùng queue nếu latency vượt ngưỡng.
- Log duration theo stage: update journal, insert evaluation, insert snapshot.

## Fail scenario 2 — Repository extraction tạo abstraction nửa vời
Nếu chỉ chuyển SQL sang repository nhưng vẫn truyền dict lỏng lẻo và JSON raw khắp nơi, code sẽ nhiều file hơn nhưng không rõ hơn.

Rủi ro kiến trúc bị bỏ qua:
- Python dynamic dict dễ làm typed boundary giả.
- Test có thể chỉ mock repository mà bỏ sót SQL arg order/schema mismatch.

Mitigation:
- Dùng dataclass/TypedDict nhỏ cho record boundary.
- Giữ E2E DB tests cho các path database quan trọng.
- Không over-abstract: chỉ extract nơi có nhiều SQL hoặc mapping phức tạp.

## Fail scenario 3 — Transaction rollback làm mất snapshot khi evaluation lỗi
Nếu implementation transaction quá cứng, lỗi evaluation insert có thể rollback cả journal update/signal snapshot, trong khi business rule hiện tại là missing evaluation core thì vẫn persist snapshot.

Rủi ro kiến trúc bị bỏ qua:
- Evaluation và signal snapshot có mức criticality khác nhau.
- Một số payload ORDER_OPENED thiếu scoring fields vẫn là trade hợp lệ.

Mitigation:
- Define rõ severity:
  - journal EXECUTED update: critical
  - signal snapshot: important
  - evaluation insert: optional nếu missing core fields
- Catch/skip evaluation missing-core trước insert, không để exception rollback các phần bắt buộc.

## Fail scenario 4 — Conflict semantic snapshot bị chọn sai
Nếu đổi conflict từ `(trade_journal_id)` sang `(trade_journal_id, signal_schema_version)` mà DB unique index chưa đúng hoặc downstream giả định 1 snapshot/trade, có thể tạo duplicate snapshots làm report sai.

Rủi ro kiến trúc bị bỏ qua:
- Recompute và live insert có thể đang dùng conflict semantic khác nhau.
- Reporting có thể join snapshot theo `trade_journal_id` và nhận nhiều rows.

Mitigation:
- Audit schema/index hiện tại trước khi đổi.
- Chốt contract: live journal lưu one canonical snapshot per trade, recompute dùng versioned snapshot hay không.
- Nếu cần versioned, downstream query phải chọn latest/target schema version rõ ràng.

## Fail scenario 5 — Bounded in-process queue vẫn mất event khi process crash
Nếu thay fire-and-forget bằng in-process queue, event có backpressure tốt hơn nhưng chưa durable; crash trước khi flush vẫn mất ORDER_CLOSED.

Rủi ro kiến trúc bị bỏ qua:
- In-process queue không thay thế Redis Stream/Kafka durable queue.
- ORDER_CLOSED là lifecycle-critical; mất close event làm journal treo EXECUTED.

Mitigation:
- Giai đoạn nhẹ chỉ thêm exception logging/backpressure, không quảng bá là durable.
- Nếu cần guarantee, chuyển ORDER_CLOSED journal events sang Redis Stream consumer group.

---

# Suggest lựa chọn tốt nhất

## Lựa chọn tốt nhất hiện tại
**Triển khai “Journal Unit-of-Work + Repository Extraction” theo lộ trình nhỏ, không làm queue/event-sourcing ngay.**

Thứ tự đề xuất:
1. **Instrument trước**
   - Log duration cho `on_strategy_match`, `on_order_opened`, `on_order_closed`.
   - Log DB affected rows và skip reasons có cấu trúc.
2. **Refactor pure mapping trước**
   - Extract mapping functions/dataclasses nhưng giữ behavior output y hệt.
   - Tests hiện có phải pass không đổi semantic.
3. **Tối ưu `on_order_opened()` transaction + SQL**
   - Dùng `UPDATE ... RETURNING` để giảm round-trip.
   - Transaction bao journal update + optional evaluation + snapshot insert.
4. **Chốt snapshot conflict semantic**
   - Audit unique index và downstream queries trước khi đổi.
5. **Cải thiện ORDER_CLOSED async handling**
   - Trước mắt add callback log exception cho `asyncio.create_task`.
   - Sau khi có metric mất event/backlog, cân nhắc Redis Stream durable journal worker.

## Acceptance criteria đề xuất cho task thực thi sau này
- `on_order_opened()` giảm ít nhất 1 DB round-trip so với hiện tại trong happy path.
- Journal update + signal snapshot insert có transaction boundary rõ ràng.
- Missing evaluation core fields không làm fail journal update/snapshot insert.
- ORDER_CLOSED async task lỗi phải được log rõ, không silent.
- Snapshot conflict semantic được document trong PLAN/SUMMARY và test.
- Unit tests `services/aureus-trader/tests/test_journal.py`, `test_signal_snapshot_pipeline.py`, `test_evaluation_pipeline.py` pass.
- Nếu sửa schema/index database: bắt buộc chạy E2E DB theo rule project.

## Không thay đổi code runtime trong task này
Task này chỉ phân tích/tư vấn và cập nhật tài liệu yêu cầu làm cơ sở thực thi + kiểm thử sau này. Không thay đổi thuật toán runtime/source code trong bước này.
