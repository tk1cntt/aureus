# Quick Task 260425-bnh Summary

## Objective
Phân tích đánh giá thuật toán TPO trong `services/aureus-signal/engine/signals/tpo.py`, trả lời khi có candle mới hệ thống đang tính tiếp hay tính lại từ đầu, và đề xuất hướng tối ưu theo 4 bước tư vấn kiến trúc độc lập.

## Kết luận ngắn
Hiện tại TPO **chưa phải incremental đúng nghĩa**. Khi có candle M1 mới, `execute_signals_for_candle()` gọi `TPOSignal.calculate(df, state)` trên toàn bộ DataFrame window hiện có. Trong `calculate()`:

- `tpo_d1`: lọc lại toàn bộ dữ liệu trong ngày hiện tại rồi rebuild profile từ đầu.
- `tpo_h1` / `tpo_m30`: resample lại M1 sang H1/M30, lấy 6 bucket gần nhất, rồi với từng bucket vẫn slice lại M1 session. Closed bucket có cache POC/VAH/VAL, nhưng code hiện tại vẫn slice session và build lại block để lấy shape/confidence.
- `_build_profile()` và `_build_tpo_block()` đều dựng lại `levels/counts` bằng cách duyệt lại các candle trong session.

Vì vậy câu trả lời là: **phần lớn đang tính lại từ đầu theo window/bucket**, chỉ có cache một phần cho profile POC/VAH/VAL của bucket đã đóng; chưa có rolling update counts theo candle mới.

---

## Evidence từ code

### Runtime candle path
- `services/aureus-signal/engine/live_engine.py`
  - `_process_candle_work_item()` gọi `window_manager.update(symbol, data)` để cập nhật DF/state.
  - Sau đó gọi `execute_signals_for_candle(signals, df, state, symbol, redis_client)`.
  - Trong `execute_signals_for_candle()`, từng signal calculator chạy `signal_calc.calculate(df, state, ...)`.
  - `TPOSignal` được tạo trong `create_signal_set()` với key `"tpo"`.

### TPO implementation hiện tại
- `TPOSignal.calculate()` tạo payload:
  - `tpo_d1 = _compute_d1(df, ts)`
  - `tpo_h1 = _compute_sliding(df, ts, "H1", count=6, cache=state.tpo_cache)`
  - `tpo_m30 = _compute_sliding(df, ts, "M30", count=6, cache=state.tpo_cache)`
- `_compute_d1()` lọc `session = m1_df[(t >= day_start) & (t <= now_ts)]`, rồi `_build_tpo_block(session)`.
- `_compute_sliding()` gọi `resample_to_tf(m1_df, tf)`, lấy `tail(6)`, rồi mỗi bucket slice lại session M1.
- `_build_tpo_block()` gọi `_build_profile(session_df)` rồi lại `_build_levels_and_counts(session_df)` để classify shape.
- `_build_levels_and_counts()` duyệt từng row trong session và cộng counts cho từng price level trong range high-low.

---

# Bước 1: Liệt kê và Phân rã (Neutral Listing)

## Phương án A — Full recompute theo window hiện tại
Đặc điểm kỹ thuật:
- Mỗi candle mới gọi lại TPO trên DataFrame hiện có.
- D1 lọc toàn bộ candle trong ngày.
- H1/M30 resample từ M1 rồi tính lại bucket/session liên quan.
- Không cần state phức tạp ngoài cache phụ.
- Kết quả phụ thuộc trực tiếp vào dữ liệu hiện có trong DataFrame.

## Phương án B — Cache closed bucket + recompute current bucket
Đặc điểm kỹ thuật:
- Bucket đã đóng lưu cache kết quả final.
- Bucket hiện tại vẫn tính lại từ các candle thuộc bucket.
- Khi candle mới thuộc cùng bucket, chỉ current bucket thay đổi.
- Khi qua bucket mới, bucket cũ được freeze vào cache.
- D1 có thể vẫn recompute trong ngày hoặc cache riêng.

## Phương án C — Incremental histogram/counts theo bucket
Đặc điểm kỹ thuật:
- Mỗi TPO profile lưu `levels/counts` hoặc histogram state theo timeframe/bucket.
- Candle mới chỉ add contribution của candle đó vào histogram hiện tại.
- POC/VAH/VAL/shape được derive từ histogram cập nhật.
- Khi bucket đóng, serialize/cache histogram hoặc kết quả final.
- Cần xử lý candle correction/duplicate/out-of-order bằng version hoặc rebuild fallback.

## Phương án D — Rolling window materialized TPO state trong Redis/DB
Đặc điểm kỹ thuật:
- TPO state không chỉ nằm trong process memory mà lưu vào Redis/TimescaleDB.
- Mỗi symbol/timeframe/bucket có record state riêng.
- Runtime đọc/update state theo candle mới.
- Có thể phục hồi sau restart mà không cần warmup dài.
- Cần schema/versioning/TTL/cleanup.

## Phương án E — Vectorized batch recompute tối ưu bằng NumPy/Pandas
Đặc điểm kỹ thuật:
- Vẫn recompute nhưng giảm vòng lặp Python thuần.
- Dùng vectorization/bucketization để dựng counts nhanh hơn.
- Không thay đổi kiến trúc state nhiều.
- Phù hợp khi window vừa phải và cần cải thiện CPU nhanh.

## Phương án F — Hybrid incremental + periodic reconciliation
Đặc điểm kỹ thuật:
- Runtime dùng incremental histogram cho latency thấp.
- Định kỳ hoặc khi phát hiện drift thì recompute full từ source-of-truth để đối soát.
- Có tolerance threshold cho POC/VAH/VAL/shape.
- Cần metric drift và cơ chế fallback.

---

# Bước 2: Phân tích theo Tiêu chí (Attribute Mapping)

## Mạnh nhất về hiệu năng runtime
1. **Phương án C — Incremental histogram/counts**: ít work nhất trên mỗi candle mới, thường chỉ update histogram của candle mới.
2. **Phương án F — Hybrid incremental + reconciliation**: runtime nhanh gần như C, nhưng thêm chi phí kiểm tra định kỳ.
3. **Phương án D — Materialized state**: nhanh nếu state I/O được thiết kế tốt, nhưng có overhead Redis/DB.
4. **Phương án E — Vectorized batch**: nhanh hơn Python loop nhưng vẫn recompute.
5. **Phương án B — Cache closed + recompute current**: giảm work ở bucket cũ, current bucket vẫn recompute.
6. **Phương án A — Full recompute**: đơn giản nhưng tốn nhất.

## Mạnh nhất về độ đúng/dễ kiểm chứng
1. **Phương án A — Full recompute**: dễ kiểm chứng vì kết quả luôn từ source window hiện tại.
2. **Phương án E — Vectorized batch**: vẫn recompute từ source, chỉ đổi implementation.
3. **Phương án B — Cache closed + recompute current**: đúng nếu cache closed bucket không bị stale.
4. **Phương án F — Hybrid**: đúng nếu reconciliation tốt.
5. **Phương án C/D**: cần kiểm soát drift, duplicate, correction, restart.

## Mạnh nhất về maintainability
1. **Phương án B**: thay đổi vừa phải, dễ đọc, ít state hơn incremental hoàn chỉnh.
2. **Phương án E**: nếu vector hóa gọn, ít thay đổi kiến trúc.
3. **Phương án A**: đơn giản nhưng khó mở rộng performance.
4. **Phương án F**: maintainability trung bình vì có 2 path incremental và full reconcile.
5. **Phương án C/D**: state machine phức tạp hơn.

## Trade-off chính

### Chọn A thay vì C/F
Mất:
- Latency thấp theo candle mới.
- Khả năng scale nhiều symbol/timeframe.
- CPU headroom cho thêm indicator khác.

Được:
- Ít bug state drift.
- Debug dễ.
- Kết quả deterministic theo DataFrame.

### Chọn C thay vì B/E
Mất:
- Simplicity.
- Dễ kiểm thử bằng so sánh trực tiếp hơn.
- Khả năng xử lý correction/out-of-order đơn giản.

Được:
- Hiệu năng tốt nhất cho candle mới.
- Có nền tảng để mở rộng nhiều timeframe/window.

### Chọn D thay vì C in-memory
Mất:
- Độ đơn giản vận hành.
- Phải quản lý state persistence/version/TTL.
- Thêm dependency latency Redis/DB.

Được:
- Restart-safe.
- Có thể inspect state ngoài process.
- Hỗ trợ multi-worker tốt hơn.

### Chọn E thay vì C
Mất:
- Không đạt true incremental.
- CPU vẫn tăng theo window/session.

Được:
- Ít thay đổi kiến trúc.
- Rủi ro thấp hơn.
- Có thể ship nhanh.

---

# Bước 3: Đề xuất dựa trên Context (Contextual Recommendation)

## Context thực tế của Aureus
- Service hiện tại là Python, signal engine chạy theo candle M1 cho nhiều symbol.
- TPO hiện đã nằm trong `services/aureus-signal`, được gọi cùng các signal khác qua `execute_signals_for_candle()`.
- TPO output đã được đưa vào Indicator Snapshot và Telegram SIGNAL ALERT.
- Đã có `state.tpo_cache`, nhưng hiện cache chỉ một phần và chưa lưu histogram/counts.
- Đã có daily GC/recalculate flow trong `live_engine.py`, tức hệ thống chấp nhận có cơ chế recalculation định kỳ.
- Ưu tiên hiện tại: ổn định runtime, dễ kiểm thử, không phá luồng signal/Telegram.

## Recommendation tối ưu
**Chọn Phương án F theo lộ trình 2 giai đoạn: Hybrid incremental + periodic reconciliation**, nhưng triển khai bước đầu bằng **B+E**.

### Giai đoạn 1 — B+E: Cache closed bucket đúng nghĩa + giảm duplicate recompute
Nên làm trước vì rủi ro thấp:
1. `_build_tpo_block()` hiện gọi `_build_profile()` rồi lại `_build_levels_and_counts()`, tức đang build counts 2 lần. Cần refactor để build `levels/counts` 1 lần rồi derive POC/VAH/VAL/shape cùng lúc.
2. `state.tpo_cache` hiện cache tuple `(poc, vah, val)`, nhưng shape/confidence vẫn buộc rebuild session. Cần cache cả block đầy đủ hoặc cache `levels/counts` của closed bucket.
3. `_compute_sliding()` hiện vẫn slice session trước cả khi cache hit. Nên check cache trước, nếu closed bucket đã cached full block thì return/use luôn, không slice lại M1.
4. D1 today-only vẫn có thể recompute trong ngày, nhưng nên tách cache theo `D1:<day_start>` và update current day hợp lý.

### Giai đoạn 2 — C/F: Incremental histogram + reconciliation
Sau khi Giai đoạn 1 ổn định:
1. Duy trì `state.tpo_histograms[(tf,bucket_start)] = {levels/counts/meta}`.
2. Candle mới chỉ add contribution vào D1/H1/M30 current histogram.
3. Khi bucket đóng, freeze result + histogram summary vào cache.
4. Mỗi N candles hoặc daily GC chạy full recompute so sánh POC/VAH/VAL/shape để detect drift.

## Vì sao không nhảy thẳng sang full incremental?
Vì TPO có nhiều rủi ro data correctness:
- Candle correction/out-of-order từ gateway.
- Restart/warmup không đủ history.
- Tick size/point theo symbol có thể đổi hoặc khác nhau.
- Shape confidence mới thêm sẽ rất nhạy với histogram lỗi.

Do đó, bước an toàn nhất là **tối ưu cache/recompute duplicate trước**, sau đó mới incremental hóa.

---

# Bước 4: Chế độ Phản biện Nghịch đảo (Adversarial Mode)

Giả sử chọn khuyến nghị F theo lộ trình B+E → C/F. Các kịch bản thất bại:

## Fail scenario 1 — Histogram incremental bị drift do candle correction/out-of-order
Nếu candle M1 đã add vào histogram rồi sau đó nhận correction cùng timestamp, incremental add-only sẽ double count hoặc giữ count cũ sai.

Rủi ro kiến trúc bị bỏ qua:
- Redis Stream hoặc gateway có thể replay/duplicate event.
- WindowManager có thể thay candle hiện tại thay vì append thuần.
- Nếu không có `last_processed_t` + candle hash/version, histogram sẽ sai âm thầm.

Mitigation:
- Chỉ incremental khi candle timestamp strictly increasing và không bị correction.
- Nếu phát hiện duplicate/correction/out-of-order → rebuild bucket từ DF.

## Fail scenario 2 — Cache closed bucket stale sau restart hoặc thay đổi config
Nếu `tpo_tick_size`, `value_area_pct`, symbol `point/digits`, hoặc code classify shape thay đổi nhưng cache không versioned, output TPO có thể sai.

Rủi ro kiến trúc bị bỏ qua:
- Cache key hiện chỉ dạng `H1:<bucket_start>`/`M30:<bucket_start>`.
- Không có version trong cache key.
- Không phân biệt thuật toán POC/VAH/VAL/shape version.

Mitigation:
- Cache key cần gồm `algo_version`, `tick_size`, `value_area_pct`, symbol.
- Khi config đổi, clear cache hoặc miss cache tự nhiên.

## Fail scenario 3 — D1 current-day incremental không reset đúng ranh giới ngày/session
Nếu reset D1 theo UTC nhưng trading session thực tế theo broker/GMT+7 hoặc symbol-specific session, D1 TPO sẽ lệch ngày.

Rủi ro kiến trúc bị bỏ qua:
- `_compute_d1()` hiện dùng `day_start = now_ts - (now_ts % 86400)` tức UTC day.
- Nếu TPO “daily” cần theo broker/session local, current logic đã có semantic mismatch.

Mitigation:
- Chốt rõ D1 TPO dùng UTC day hay trading session day.
- Đưa session boundary vào config/test.

## Fail scenario 4 — Full block cache làm mất khả năng debug shape drift
Nếu chỉ cache result cuối (`POC/VAH/VAL/shape/confidence`) mà không lưu counts/features, khi shape sai sẽ khó phân tích vì mất source histogram.

Mitigation:
- Với closed bucket nên cache thêm `counts_checksum`, `levels_count`, `total_tpo`, hoặc feature summary.
- Không nhất thiết lưu toàn bộ levels/counts vào Telegram payload, chỉ lưu runtime cache/debug.

## Fail scenario 5 — Tối ưu quá sớm làm Telegram hiển thị shape tự tin giả
Shape classifier hiện là heuristic. Nếu tối ưu incremental nhưng classifier chưa được validate bằng ground truth, `% confidence` có thể tạo cảm giác chắc chắn quá mức.

Mitigation:
- Gọi là `shape_confidence_pct` nội bộ nhưng UI có thể hiển thị `Match`/`Fit` thay vì xác suất thống kê.
- Thu thập labeled samples để calibrate threshold.

---

# Suggest lựa chọn tốt nhất

## Lựa chọn tốt nhất hiện tại
**Triển khai Giai đoạn 1: “Full-block cache + single-pass profile build” trước.**

Cụ thể nên làm trong task kế tiếp:
1. Refactor `_build_profile()` + `_build_tpo_block()` thành 1 pipeline single-pass:
   - `_build_levels_and_counts()` chạy 1 lần.
   - derive POC/VAH/VAL từ counts.
   - derive shape/confidence từ cùng counts.
2. Đổi `state.tpo_cache` để cache full block cho closed H1/M30 bucket:
   - `{POC, VAH, VAL, shape, shape_confidence_pct, shape_scores_pct}`
3. Trong `_compute_sliding()`:
   - Nếu bucket closed và cache hit → dùng cache ngay, không slice/rebuild.
   - Nếu current bucket hoặc cache miss → build block.
4. Thêm unit test chứng minh:
   - closed bucket cache hit không gọi rebuild.
   - current bucket vẫn cập nhật khi candle mới đến.
   - output Telegram không đổi contract cũ.

## Sau đó mới làm Giai đoạn 2
Chỉ triển khai incremental histogram khi có benchmark cho thấy TPO là bottleneck CPU thực sự hoặc khi tăng số symbol/timeframe làm latency candle loop vượt ngưỡng.

## Acceptance criteria đề xuất cho task thực thi sau này
- TPO output giữ đủ `POC/VAH/VAL/shape/shape_confidence_pct/shape_scores_pct`.
- `_build_levels_and_counts()` không bị gọi 2 lần cho cùng một block.
- Closed H1/M30 bucket cache hit không rebuild session.
- Current H1/M30 bucket vẫn update theo candle mới.
- D1 semantic được ghi rõ là UTC day hoặc đổi sang configured session day.
- Tests pass cho `test_tpo_signal.py`, `test_formatters.py`, `test_indicator_snapshot.py`.

## Không thay đổi code runtime trong task này
Task này là phân tích/tư vấn và cập nhật tài liệu yêu cầu làm cơ sở thực thi + kiểm thử sau này. Không thay đổi thuật toán runtime trong source code ở bước này.
