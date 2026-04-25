# Tư vấn kiến trúc độc lập: cải thiện `_classify_shape` / TPO shape

Nguồn chính: `.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md`.

Tài liệu này chỉ là advisory kiến trúc. Không đề xuất triển khai production ngay trong phạm vi quick task này. Mục tiêu là chuyển report hiện trạng thành quyết định có phản biện, đủ rõ để các task sau dùng làm yêu cầu và cơ sở kiểm thử.

## Giả định và phạm vi

- `_classify_shape` hiện là heuristic deterministic nội bộ trong `services/aureus-signal/engine/signals/tpo.py`.
- Output hiện gồm `shape`, `shape_confidence_pct`, `shape_scores_pct` cho bốn dạng `D/B/p/b`.
- Shape hiện đi vào `state_obj.tpo_profile`, `indicator_snapshot`, Telegram SIGNAL ALERT; chưa có bằng chứng shape đã được flatten vào `signal_snapshot` hoặc trực tiếp dùng cho strategy scoring.
- `shape_confidence_pct` hiện là normalized heuristic score, chưa phải xác suất thống kê đã calibrate.
- Hệ thống đã có bối cảnh liên quan tới TPO signal, TPOContextBuilder, detectors, history store và replay/backtest harness trong STATE, nên advisory ưu tiên tận dụng nền tảng đó thay vì mở hướng ML ngay.

## Bước 1: Liệt kê và Phân rã (Neutral Listing)

Phần này chỉ liệt kê trung lập các hướng cải thiện phổ biến/khả thi cho TPO shape classification. Chưa đánh giá tốt/xấu.

### 1. Calibrated deterministic heuristic

Giữ `_classify_shape` theo hướng rule-based deterministic, nhưng thay hoặc bổ sung score hiện tại bằng các metric hình học rõ ràng hơn:

- Symmetry quanh POC.
- Compactness/kurtosis của vùng phân phối.
- Peak separation cho B-shape.
- Valley depth giữa hai peak.
- Upper/lower excess area cho p/b.
- Margin giữa top-1 và top-2 shape score.
- Data-quality factor dựa trên số candle, tổng TPO count, số bin hợp lệ.

Confidence trong hướng này không nên chỉ là tỷ lệ normalized sum, mà nên là điểm tổng hợp từ `score margin + data maturity + profile quality`.

### 2. Maturity/session gating

Bổ sung điều kiện để phân biệt profile đang hình thành với profile đủ dữ liệu:

- H1/M30 current bucket cần minimum elapsed minutes hoặc minimum TPO count.
- D1 cần xác định rõ semantic của ngày: UTC day, broker day, hoặc market session.
- Profile chưa đủ mature có thể bị cap confidence hoặc được đánh dấu là `insufficient_data`/`forming` trong future contract.
- Current bucket và closed bucket có thể có cách diễn giải khác nhau.

### 3. Rule-based hybrid với TPO detectors

Không để shape đơn độc mang toàn bộ narrative. Shape là feature hình học, còn detector/context layer xác nhận ý nghĩa giao dịch:

- VA rejection.
- VA breakout acceptance.
- Trend pullback quanh VA/POC.
- POC/VA shift history.
- Price relation với VAH/VAL/POC.
- Multi-timeframe agreement hoặc conflict giữa D1/H1/M30.

Trong hướng này, shape không nhất thiết trở thành trigger; nó là backdrop/context cho detector và Telegram explanation.

### 4. Offline replay/backtest calibration

Dùng historical M1 OHLCV để replay TPO blocks, đo stability và calibrate threshold/confidence:

- Replay D1/H1/M30 trên nhiều ngày/symbol/regime.
- Đo shape flip rate trong current bucket.
- Đo confidence distribution.
- So sánh before/after trên cùng dữ liệu.
- Nếu sau này dùng cho scoring, chạy A/B backtest có/không có shape hoặc có/không có detector confirmation.

Hướng này không nhất thiết thay thuật toán runtime; nó cung cấp evidence để chỉnh threshold và guardrail.

### 5. Statistical/ML classifier

Xây classifier thống kê hoặc ML dựa trên features từ TPO profile và context:

- Input có thể gồm histogram metrics, POC/VA width, skew, kurtosis, peak/valley metrics, session context, detector outputs.
- Label có thể từ human review, proxy rules, hoặc outcome-based labels.
- Output có thể là class probability hoặc ranking D/B/p/b.
- Cần training/validation split theo thời gian và symbol để tránh overfit.

Hướng này yêu cầu quy trình dữ liệu, labeling, monitoring drift và giải thích output nếu dùng trong Telegram hoặc scoring.

## Bước 2: Phân tích theo Tiêu chí (Attribute Mapping)

### Bảng mapping tổng quan

| Phương án | Runtime/determinism | Giải thích trên Telegram | Tốc độ triển khai | Giảm false confidence/sparse noise | Giá trị replay/backtest | Độ phức tạp bảo trì |
|---|---|---|---|---|---|---|
| Calibrated deterministic heuristic | Cao, ít phụ thuộc external state | Cao nếu metric được đặt tên rõ | Nhanh | Tốt nếu có margin/data-quality | Cần replay để calibrate | Thấp đến trung bình |
| Maturity/session gating | Cao nếu rule rõ | Cao, dễ giải thích `forming/confirmed` | Nhanh đến trung bình | Rất tốt cho current bucket sparse | Replay đo flip rate rất hữu ích | Thấp nếu không đổi D1 semantics; cao hơn nếu đổi session |
| Rule-based hybrid với detectors | Cao nếu detector deterministic | Cao vì có context VA/POC cụ thể | Trung bình | Tốt, giảm diễn giải shape đơn độc | Rất hữu ích để đo false positives | Trung bình đến cao |
| Offline replay/backtest calibration | Không nằm trực tiếp runtime | Gián tiếp giúp giải thích confidence | Trung bình | Tốt sau khi threshold được hiệu chỉnh | Rất cao | Trung bình |
| Statistical/ML classifier | Phụ thuộc model/version/data pipeline | Thấp hơn nếu không có explainability | Chậm | Có thể tốt nếu data đủ, nhưng rủi ro overfit | Bắt buộc | Cao |

### Trade-off nếu chọn calibrated heuristic/hybrid thay vì ML

Lợi ích:

- Phù hợp với trạng thái hiện tại: shape chủ yếu là hiển thị/giải thích trong Telegram, chưa nên coi là scoring signal.
- Deterministic, dễ debug khi một alert hiển thị `Shape:D (70%)`.
- Có thể kiểm thử bằng synthetic fixtures cho D/B/p/b, sparse, outlier, tick_size.
- Ít rủi ro vận hành vì không cần model lifecycle, drift monitoring, retraining hoặc labeling process.
- Tận dụng được TPO detectors/replay harness đã xuất hiện trong context dự án.

Đánh đổi:

- Vẫn có nguy cơ threshold/magic-number nếu metric không được định nghĩa và calibrate bằng replay.
- Không tự học được các pattern phức tạp vượt ngoài rule đã thiết kế.
- Nếu muốn biến confidence thành xác suất thật, heuristic phải được kiểm chứng bằng calibration dataset, không thể chỉ đổi công thức.

### Trade-off nếu chọn ML/statistical classifier sớm

Lợi ích:

- Có thể học non-linear interactions giữa histogram, context, session và outcome.
- Có khả năng output probability nếu được calibrate đúng.
- Hữu ích về dài hạn nếu shape trở thành feature scoring quan trọng với nhiều symbol/regime.

Đánh đổi:

- Cần label rõ cho D/B/p/b; proxy label dễ encode bias của heuristic cũ.
- Chi phí vận hành cao hơn: data pipeline, model versioning, drift, explainability, rollback.
- Telegram explanation khó hơn nếu model chỉ trả class/probability mà không nêu peak separation, valley depth, data quality.
- Không phù hợp khi report nguồn chưa chứng minh shape đang tạo edge cho scoring.

### Tiêu chí quan trọng nhất trong context hiện tại

1. **Determinism và explainability** quan trọng hơn model complexity, vì shape đang hiện trực tiếp trong SIGNAL ALERT.
2. **Giảm false confidence** quan trọng hơn tăng độ tinh vi, vì confidence hiện dễ bị hiểu nhầm là xác suất.
3. **Maturity gating** là yêu cầu nền vì current H1/M30 bucket sparse là rủi ro trực tiếp.
4. **Replay/backtest calibration** là điều kiện trước khi shape được đưa vào strategy scoring.
5. **Bảo trì đơn giản** quan trọng vì TPO đã có nhiều layer: signal, context builder, detector, history, replay, Telegram.

## Bước 3: Đề xuất dựa trên Context (Contextual Recommendation)

### Context cụ thể từ report và STATE

- `_classify_shape` hiện được gọi trong `_build_tpo_block` sau khi có levels/counts/POC.
- Shape được hiển thị trong Telegram SIGNAL ALERT qua indicator snapshot.
- Chưa có bằng chứng shape đã được flatten vào `signal_snapshot` hoặc dùng trực tiếp cho strategy scoring.
- Confidence hiện chưa calibrate và không nên được diễn giải như xác suất.
- Các rủi ro lớn nhất là threshold brittle, dual peak thiếu separation/valley, sparse current bucket, tick_size/binning sensitivity, outlier/wick sensitivity, UTC D1 semantic và thiếu unknown/insufficient state.
- STATE cho thấy hệ thống đã có các quick liên quan tới TPOContextBuilder, TPO history store, TPO detectors, strategy tag bridge và replay/backtest harness.

### Khuyến nghị tối ưu

Lựa chọn tối ưu là **calibrated deterministic heuristic + maturity/data-quality gating trước, sau đó dùng detector context và replay/backtest calibration làm lớp xác nhận**.

Cụ thể:

1. Ngắn hạn, cải thiện `_classify_shape` theo hướng deterministic có metric rõ:
   - Peak separation và valley depth cho B-shape.
   - Symmetry/compactness quanh POC cho D-shape.
   - Upper/lower excess area cho p/b.
   - Confidence dựa trên top-1/top-2 margin và data-quality, không chỉ normalized sum.
2. Thêm maturity/data-quality gate:
   - Current H1/M30 bucket không nên hiển thị confidence mạnh khi dữ liệu chưa đủ.
   - Empty/sparse/outlier profile phải có hành vi an toàn: confidence thấp, capped confidence, hoặc future state `insufficient_data` nếu contract được mở rộng sau này.
3. Dùng TPO detectors như confirmation layer:
   - Shape là geometry backdrop.
   - Detector/context quyết định narrative vận hành: rejection, acceptance, VA shift, POC relation.
4. Chỉ cân nhắc đưa shape vào scoring sau replay/backtest:
   - Đo flip rate, confidence distribution, A/B strategy outcome.
   - Không dùng `shape_confidence_pct` như xác suất thật trước khi có calibration evidence.

### Vì sao không chọn ML ngay

ML không phải lựa chọn tốt nhất ở thời điểm này vì vấn đề hiện tại chưa phải thiếu capacity model, mà là thiếu calibration, maturity gate và evidence. Nếu chuyển sang ML ngay, hệ thống sẽ nhận thêm rủi ro data/label/model lifecycle trong khi shape hiện chủ yếu phục vụ giải thích. Một heuristic có metric rõ, được replay calibrate, sẽ mang lại giá trị nhanh hơn và ít rủi ro hơn.

### Vì sao không chỉ chỉnh threshold hiện tại

Chỉ đổi các ngưỡng như `0.35/0.45` không giải quyết gốc rễ:

- B-shape vẫn thiếu peak separation/valley depth.
- Sparse bucket vẫn có thể tạo confidence nhìn chắc chắn.
- Confidence vẫn không phải xác suất.
- Tick_size/outlier vẫn có thể làm profile méo.

Do đó thay đổi cần tập trung vào metric definition và validation, không chỉ tuning threshold.

## Bước 4: Chế độ Phản biện Nghịch đảo (Adversarial Mode)

Giả sử chọn calibrated deterministic heuristic + maturity gating + detector/replay confirmation. Phần này chủ động tấn công lựa chọn đó.

### THẤT BẠI 1: Heuristic mới trở thành tập magic numbers phức tạp hơn

Rủi ro: thay vì vài threshold hiện tại, hệ thống có thêm nhiều ngưỡng mới như minimum separation, valley ratio, compactness threshold, maturity minutes, confidence margin. Nếu không được định nghĩa và validate, thuật toán chỉ chuyển brittleness sang nơi khác.

Guardrail:

- Mỗi metric phải có định nghĩa rõ trong requirement/test.
- Threshold phải có replay evidence hoặc fixture boundary test.
- Không chấp nhận thay đổi chỉ dựa trên cảm giác nhìn chart.

### THẤT BẠI 2: Maturity gate làm mất thông tin sớm mà trader cần

Rủi ro: nếu gate quá chặt, Telegram có thể mất shape trong giai đoạn đầu H1/M30, trong khi một số trader muốn biết profile đang hình thành.

Guardrail:

- Phân biệt `forming` và `confirmed` thay vì im lặng hoàn toàn nếu future contract cho phép.
- Nếu chưa đổi contract, cap confidence ở sparse bucket thay vì render như confirmed.
- Replay phải đo trade-off: giảm false confidence so với mất tín hiệu sớm.

### THẤT BẠI 3: Detector confirmation che giấu lỗi shape hoặc khuếch đại lỗi context

Rủi ro: detector layer có thể khiến người dùng tin hơn vào một shape sai nếu detector cũng bị lệch do VA/POC bị outlier kéo méo. Khi shape + detector cùng sai, narrative Telegram sẽ có vẻ rất thuyết phục nhưng không đúng.

Guardrail:

- Detector chỉ là confirmation/context, không phải bằng chứng tuyệt đối.
- Test outlier/wick phải bao phủ cả shape và detector context.
- Telegram/explanation cần tránh ngôn ngữ xác suất khi chưa calibrate.

### THẤT BẠI 4: Replay/backtest bị overfit theo symbol/regime hiện có

Rủi ro: threshold calibrate trên một giai đoạn hoặc một symbol có thể giảm noise trong sample đó nhưng kém ổn định ở volatility regime khác.

Guardrail:

- Split validation theo thời gian, không random shuffle thuần túy.
- Đo theo symbol/timeframe/session riêng, không chỉ aggregate.
- Báo cáo confidence distribution và flip rate theo regime.

### THẤT BẠI 5: D1 session semantic bị bỏ qua quá lâu

Rủi ro: nếu D1 vẫn là UTC day nhưng người dùng hiểu theo market session/broker day, shape có thể đúng theo code nhưng sai theo kỳ vọng trading.

Guardrail:

- Không đổi D1 session trong quick cải thiện shape nếu chưa có quyết định semantic riêng.
- Requirements phải ghi rõ UTC D1 là hiện trạng và là out-of-scope nếu chưa quyết định.
- Nếu future task cần đổi session, phải có migration về expectation/test riêng.

## Suggested best choice

Lựa chọn tốt nhất: **triển khai lộ trình hybrid thận trọng: calibrated deterministic heuristic + maturity/data-quality gate là bước đầu; detector context và replay/backtest calibration là điều kiện xác nhận trước khi dùng shape cho scoring**.

### Phạm vi nên làm trước

- Định nghĩa metric rõ cho D/B/p/b:
  - D: symmetry/compactness quanh POC.
  - B: two separated peaks + valley depth.
  - p/b: upper/lower excess area và skew có kiểm soát outlier.
- Confidence dựa trên:
  - Top-1/top-2 margin.
  - Data maturity.
  - Profile quality.
- Gate hoặc cap confidence cho sparse/current buckets.
- Unit fixtures và edge tests trước khi thay đổi runtime behavior.
- Replay đo flip rate và confidence distribution trước khi coi confidence là đáng tin.

### Điều kiện không nên làm

- Không dùng ML ngay khi chưa có labeled/replay dataset và explainability plan.
- Không đưa `shape_confidence_pct` vào strategy scoring như xác suất thật.
- Không chỉ chỉnh threshold cũ mà không thêm metric/test/replay.
- Không đổi D1 session semantic trong cùng phạm vi nếu chưa có quyết định riêng.
- Không mở rộng DB/persistence contract cho TPO shape nếu chưa trace schema/journal path riêng.

### Guardrail bắt buộc

- Tất cả acceptance criteria phải trace được về `260425-kwd-REPORT.md` và advisory này.
- Mỗi thay đổi shape classification trong future implementation phải có unit fixture D/B/p/b và edge cases sparse/outlier/tick_size.
- Nếu output Telegram giữ dạng phần trăm, tài liệu/test phải xác định rõ đó là heuristic confidence, không phải xác suất thống kê.
- Replay/backtest là bắt buộc trước khi shape ảnh hưởng strategy scoring.
- Bất kỳ thay đổi session semantics nào phải được tách thành quyết định kiến trúc riêng.
