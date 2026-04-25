# TPO CPU/Stuck Architecture Advisory

Tài liệu này đánh giá độc lập vấn đề TPO gây CPU cao/stuck trong live signal loop và hướng fix vừa áp dụng. Phạm vi chỉ là advisory kiến trúc, không thay đổi source code.

## 1. Neutral Listing

### 1.1. Vấn đề đã quan sát

- Khi bật `AUREUS_ENABLE_TPO_SIGNAL=1`, `aureus-signal-dev` từng bị CPU cao/stuck, signal processing stall, signal stream không tăng hoặc strategy executor chờ signal.
- Khi tắt TPO, signal chạy bình thường, cho thấy nghi vấn nằm trong đường tính toán TPO hoặc phần hậu xử lý sau TPO.
- Không có Python exception ổn định. Triệu chứng chính là latency/CPU trong candle-loop trước khi publish signal và ACK flow hoàn tất.

### 1.2. Facts từ implementation hiện tại

- `TPOSignal.calculate()` tính cả D1, H1, M30 trong mỗi lần chạy và ghi payload vào `state_obj.tpo_profile`.
- `_build_levels_and_counts()` dùng `AUREUS_TPO_MAX_LEVELS`, mặc định `5000`, để giới hạn số price levels; sau đó dùng delta prefix-sum để tính counts.
- `_classify_shape()` scan levels/counts, detect peaks, rồi đánh giá B-shape bằng so sánh peak-pair.
- Fix hiện tại giới hạn B-shape peak-pair candidates ở 64 strongest peaks, sau đó sort lại theo price index trước khi pair scanning.
- `_build_profile_from_counts()` vẫn derive POC/VAH/VAL từ counts.
- `execute_signals_for_candle()` gọi signal calculators đồng bộ trong candle processing. Nếu TPO chậm/stuck thì signal emission, profiling, normalized candle record và ACK flow đều bị trễ.
- `live_engine` có slow log cho TPO khi `signal_name == "tpo"` và elapsed time vượt `AUREUS_TPO_SLOW_SIGNAL_MS`, mặc định `250ms`.
- Indicator snapshot cho Telegram được build sau signals, nên TPO chậm có thể kéo trễ cả phần snapshot downstream.

### 1.3. Evidence đo được

- Synthetic `_classify_shape` với n=5000 trước fix: khoảng `981.95ms`.
- Synthetic `_classify_shape` với n=5000 sau peak-pair cap: khoảng `134.40ms`.
- Live-like `TPOSignal.calculate` với `max_levels=5000` sau fix: average khoảng `67.52ms`, max khoảng `136.88ms`.
- Focused runtime test: `services/aureus-signal/tests/test_tpo_live_integration.py` pass 3 tests.
- Docker runtime với TPO enabled: service recreate thành công, CPU ổn định, memory khoảng 94-96MiB, tất cả symbols Engine ready, không thấy TPO error/slow logs/ERROR/Traceback trong logs gần nhất, BTCUSD/ETHUSD Redis candle consumer lag 0.

### 1.4. Các hướng xử lý trung lập

1. Current applied path: peak-pair cap 64 + existing `AUREUS_TPO_MAX_LEVELS` cap + delta prefix-sum.
2. Lower global `AUREUS_TPO_MAX_LEVELS` từ 5000 xuống một mức thấp hơn.
3. Fully incremental/session-level TPO cache để không rebuild block nhiều lần.
4. Approximate/histogram binning để giảm số bins/levels theo độ phân giải cố định.
5. Background/off-thread TPO computation để tách TPO khỏi synchronous candle-loop.
6. Disabling TPO/live tag kill-switch khi runtime không ổn định.
7. Removing/deferring shape classification để chỉ giữ POC/VAH/VAL hoặc tính shape ngoài hot path.

## 2. Attribute Mapping

| Option | Latency impact | Correctness/semantic impact | Operational complexity | Failure containment | Fit với evidence hiện tại |
|---|---|---|---|---|---|
| Peak-pair cap 64 + max-level cap + delta prefix-sum | Giảm trực tiếp hotspot O(P^2); evidence n=5000 từ 981.95ms còn 134.40ms, live-like avg 67.52ms | Có thể bỏ qua peak yếu, ảnh hưởng một số weak B-shape | Thấp, surgical trong classifier | Tốt, giữ TPO trong same path nhưng dưới slow threshold | Cao; đúng root cause đã xác nhận |
| Lower global `AUREUS_TPO_MAX_LEVELS` | Giảm toàn bộ scan/profile/classifier cost | Làm giảm resolution POC/VAH/VAL và shape trên symbol có range rộng | Thấp | Trung bình; giới hạn tổng chi phí | Hữu ích như tuning, nhưng không nhắm đúng peak-pair explosion bằng cap 64 |
| Fully incremental/session-level TPO cache | Có thể giảm rebuild D1/H1/M30 đáng kể | Nếu cache invalidation sai sẽ tạo TPO stale/sai | Cao hơn; cần quản lý bucket/session state | Tốt nếu implement đúng | Chưa cần ngay vì current evidence đã dưới 250ms |
| Approximate/histogram binning | Giảm bins và ổn định runtime | Approximation có thể đổi POC/VAH/VAL/shape, cần calibration | Trung bình | Tốt với extreme ranges | Nên là fallback nếu max_levels vẫn quá tốn trên symbol/range đặc biệt |
| Background/off-thread TPO computation | Candle-loop không bị block bởi TPO | Snapshot có thể dùng TPO cũ hơn một candle; cần consistency semantics | Cao; cần queue/state/versioning | Rất tốt cho isolation | Chỉ nên escalate nếu synchronous path vượt ngưỡng runtime lặp lại |
| Disable TPO/live tag kill-switch | Khôi phục ổn định nhanh | Mất TPO output/live tags | Thấp | Rất tốt như emergency control | Phù hợp làm rollback/ops guard, không phải fix chính |
| Remove/defer shape classification | Loại bỏ hotspot shape | Mất D/B/p/b và confidence; giảm giá trị Telegram/strategy context | Thấp đến trung bình | Tốt | Không cần vì cap hiện tại đã giữ shape với runtime chấp nhận được |

### Mapping theo thuộc tính quyết định

- Nếu mục tiêu là khôi phục live stability nhanh mà vẫn giữ semantics TPO: current applied path là hợp lý nhất.
- Nếu mục tiêu là latency thấp nhất bằng mọi giá: remove/defer shape hoặc lower max levels sẽ nhanh hơn nhưng làm giảm business value.
- Nếu mục tiêu là kiến trúc dài hạn cho throughput lớn: incremental cache hoặc background computation mạnh hơn nhưng là thay đổi cấu trúc, cần requirement/test riêng.
- Nếu mục tiêu là operational safety: kill-switch và monitoring hiện có phải được giữ như guardrail.

## 3. Contextual Recommendation

### 3.1. Khuyến nghị theo ngữ cảnh hiện tại

Khuyến nghị giữ current applied path làm fix chính: peak-pair cap 64 trong `_classify_shape()`, tiếp tục dùng existing `AUREUS_TPO_MAX_LEVELS` cap và delta prefix-sum. Lý do là evidence chỉ ra root cause cụ thể nằm ở unbounded nested peak-pair comparison; fix đã giảm synthetic n=5000 từ 981.95ms xuống 134.40ms và live-like `TPOSignal.calculate` về average 67.52ms/max 136.88ms, dưới default slow threshold 250ms.

Hướng này có tỷ lệ lợi ích/rủi ro tốt vì:

- Chạm đúng hotspot đã được benchmark.
- Không thay đổi public payload TPO: POC, VAH, VAL, shape, confidence, scores vẫn tồn tại.
- Không yêu cầu đổi live pipeline đồng bộ hiện tại.
- Không thêm state/cache invalidation phức tạp.
- Docker/runtime verification đã cho thấy CPU ổn định, Engine ready, không có TPO slow/error logs, consumer lag 0.

### 3.2. Acceptance thresholds đề xuất

Các ngưỡng dưới đây nên trở thành requirement/test để tránh tái diễn candle-loop stall:

- Focused live-like benchmark: `TPOSignal.calculate` với `AUREUS_TPO_MAX_LEVELS=5000` nên giữ average dưới `100ms` và max dưới `200ms` trên fixture live-like tương tự debug evidence.
- Slow-log guard: trong runtime docker, không xuất hiện repeated `[execute_signals_for_candle] slow TPO calc` vượt `AUREUS_TPO_SLOW_SIGNAL_MS=250` trong cửa sổ quan sát bình thường.
- Docker runtime observation: khi `AUREUS_ENABLE_TPO_SIGNAL=1`, service phải đạt Engine ready cho symbols, không có TPO calc error/Traceback, Redis candle consumer lag giữ `0` hoặc không tăng bền vững.
- Regression test: focused `test_tpo_live_integration.py` tiếp tục pass.
- Shape correctness guard: test fixture B-shape mạnh phải vẫn classify được B; fixture weak B-shape cần ghi rõ expected tolerance vì peak-pair cap có thể bỏ qua peak yếu.

### 3.3. Khi nào escalate khỏi current fix

Chỉ nên chuyển sang incremental cache/background computation nếu một trong các điều kiện sau lặp lại trên dữ liệu thật:

- TPO live-like benchmark max vượt `200ms` thường xuyên dù peak-pair cap còn hiệu lực.
- Runtime logs có repeated slow TPO calc vượt `AUREUS_TPO_SLOW_SIGNAL_MS` và đi kèm Redis consumer lag tăng.
- CPU spike/stall tái diễn với TPO enabled nhưng biến mất khi dùng kill-switch.
- Nhu cầu business yêu cầu nhiều timeframe/symbol hơn khiến D1/H1/M30 rebuild đồng bộ không còn đủ headroom.

Nếu escalate, thứ tự nên là:

1. Tuning `AUREUS_TPO_MAX_LEVELS` theo benchmark và symbol range.
2. Incremental/session-level cache cho block đã đóng hoặc session đang update.
3. Background/off-thread computation nếu vẫn cần isolate khỏi candle-loop.

## 4. Adversarial Mode

### 4.1. Luận điểm phản biện current fix

- Cap 64 strongest peaks không tương đương full pair scan. Một weak B-shape có hai peak không nằm trong top 64 có thể bị giảm hoặc mất B evidence.
- `_classify_shape()` vẫn scan toàn bộ levels/counts, nên n=5000 vẫn còn 134.40ms trong synthetic case; nếu D1/H1/M30 cùng rơi vào worst case thì headroom vẫn cần theo dõi.
- Evidence docker runtime được quan sát trong cửa sổ ngắn; consumer lag 0 và CPU ổn định là tín hiệu tốt nhưng không chứng minh mọi market regime đều an toàn.
- Fix không giải quyết chi phí resample/rebuild block trong `_compute_sliding()`, chỉ giải quyết hotspot pair comparison.
- Nếu future thay đổi tăng `max_levels`, tick_size, hoặc thêm timeframe, current margin có thể bị ăn hết.

### 4.2. Luận điểm phản biện các alternatives

- Lower `AUREUS_TPO_MAX_LEVELS`: dễ làm nhưng có thể che giấu vấn đề classifier và làm giảm độ phân giải TPO cho cả POC/VAH/VAL.
- Incremental cache: đúng hướng dài hạn nhưng tăng rủi ro stale data, invalidation lỗi, và test surface lớn hơn.
- Histogram binning: ổn định runtime nhưng biến đổi semantics; cần calibration với expected trading interpretation.
- Background computation: giảm blocking nhưng thêm consistency problem; Telegram/signal có thể đọc TPO cũ nếu không versioning rõ.
- Kill-switch: cần cho ops nhưng nếu dùng như giải pháp chính thì mất toàn bộ giá trị TPO.
- Remove/defer shape classification: an toàn performance nhưng đi ngược requirement đã thêm D/B/p/b và confidence vào indicator snapshot/Telegram.

### 4.3. Adversarial checks nên có

- Benchmark worst-case counts có nhiều local peaks để xác nhận pair cap luôn bounded.
- Fixture B-shape mạnh, weak B-shape, D-shape symmetric, p-shape, b-shape để detect semantic drift.
- Docker smoke với `AUREUS_ENABLE_TPO_SIGNAL=1`, kiểm tra slow logs, profiling stream/logs, và Redis consumer lag.
- Test rằng cap chọn 64 strongest peaks nhưng sort lại theo price index trước pair scanning, tránh pair order sai.
- Theo dõi `AUREUS_TPO_SLOW_SIGNAL_MS`, profiling stream/logs và Redis consumer lag như monitoring hooks chính.

## Concrete Recommendation

Khuyến nghị cuối cùng: giữ fix hiện tại làm baseline production path, không chuyển ngay sang incremental cache/background computation.

Rationale ngắn:

- Root cause đã được định danh rõ: unbounded nested peak-pair comparison trong `_classify_shape()`.
- Fix hiện tại đúng vào root cause, giảm synthetic n=5000 từ 981.95ms xuống 134.40ms.
- Live-like `TPOSignal.calculate` đạt average 67.52ms/max 136.88ms, còn dưới `AUREUS_TPO_SLOW_SIGNAL_MS=250ms`.
- Docker runtime với TPO enabled không còn biểu hiện stuck/high CPU, không thấy TPO slow/error logs, consumer lag 0.
- Alternatives mạnh hơn như incremental cache/background computation có chi phí kiến trúc lớn hơn và chưa cần thiết theo evidence hiện tại.

Nên xem current fix là “bounded synchronous TPO” với guardrails. Không nên coi nó là kết thúc vĩnh viễn cho mọi scale; nếu monitoring cho thấy slow logs/consumer lag quay lại thì mới escalate theo thứ tự tuning max levels → incremental cache → background computation.

## Requirements & Test Implications

### Requirements đề xuất

1. TPO shape classification phải bounded: B-shape peak-pair comparison không được tăng theo toàn bộ số peaks khi peaks vượt cap 64.
2. `TPOSignal.calculate` với `AUREUS_TPO_MAX_LEVELS=5000` trên live-like fixture phải giữ average dưới 100ms và max dưới 200ms trong benchmark cục bộ.
3. Runtime docker với TPO enabled phải không tạo repeated slow TPO logs vượt `AUREUS_TPO_SLOW_SIGNAL_MS=250ms` trong cửa sổ quan sát smoke.
4. Redis candle consumer lag phải giữ 0 hoặc không tăng bền vững khi TPO enabled.
5. TPO payload vẫn phải giữ POC/VAH/VAL/shape/shape_confidence_pct/shape_scores_pct cho D1/H1/M30 khi data hợp lệ.
6. Monitoring hooks hiện có gồm `AUREUS_TPO_SLOW_SIGNAL_MS`, profiling stream/logs và Redis consumer lag phải được dùng trong verification khi thay đổi TPO runtime.
7. Kill-switch TPO/live tags nên được giữ như operational rollback, nhưng không được thay thế regression test performance.

### Test implications

- Thêm hoặc duy trì focused TPO live integration test cho path TPO enabled.
- Thêm microbenchmark hoặc performance assertion có tolerance cho `_classify_shape()` worst-case n=5000.
- Thêm test semantic cho B-shape mạnh để đảm bảo cap 64 không làm mất detection chính.
- Thêm test/document tolerance cho weak B-shape: peak-pair cap có thể giảm confidence hoặc đổi classification nếu evidence quá yếu.
- Thêm docker smoke checklist: Engine ready, no TPO calc error, no repeated slow TPO logs, profiling stream/logs có timing hợp lý, Redis consumer lag 0.
- Nếu sau này implement incremental/background path, cần requirement riêng cho freshness/versioning của `state_obj.tpo_profile` để tránh Telegram/signal dùng dữ liệu stale mà không biết.
