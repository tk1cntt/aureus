# _classify_shape Analysis Report

## Executive Summary

Báo cáo này chỉ phân tích, không implement production code. Hàm `_classify_shape` nằm trong `services/aureus-signal/engine/signals/tpo.py` và là phần bổ sung semantic cho TPO block sau khi profile đã có `POC/VAH/VAL`. Output của nó gồm `shape`, `shape_confidence_pct`, `shape_scores_pct` cho 4 dạng `D/B/p/b`.

Kết luận chính:

1. `_classify_shape` hiện là heuristic nội bộ, được gọi trực tiếp từ `_build_tpo_block` sau khi `_build_profile_from_counts` xác định POC/VAH/VAL.
2. Shape được đưa vào `state_obj.tpo_profile`, sau đó đi vào `indicator_snapshot` và được render trong Telegram SIGNAL ALERT qua section TPO.
3. Strategy context hiện có nhận `indicator_snapshot`, nhưng `signal_snapshot` phái sinh trong `signal_event_publisher.py` chưa flatten các trường TPO shape vào `signal_snapshot`; vì vậy shape chủ yếu có tác động hiển thị/giải thích, chưa thấy bằng chứng trực tiếp rằng nó đang là điều kiện scoring strategy.
4. Thuật toán hiện tại có điểm mạnh là đơn giản, deterministic, ít phụ thuộc external state; nhưng yếu ở calibration, sparse profile, ambiguity, session/timeframe semantics, outlier/binning sensitivity và chưa có backtest/labeled replay để chứng minh confidence có ý nghĩa xác suất.

Khuyến nghị: không nên thay bằng ML ngay. Nên đi theo hướng hybrid theo thứ tự: (1) chuẩn hóa heuristic bằng metrics phân phối rõ hơn và confidence calibration, (2) thêm context multi-session/timeframe, (3) kết hợp detector outputs TPO đã có/đang xây theo hướng rule-based hybrid, (4) dùng offline replay/backtest để hiệu chỉnh threshold và validate operational impact.

## Current Implementation

### Vị trí và chữ ký hàm

Nguồn chính:

- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:122-170`

Chữ ký:

```python
def _classify_shape(self, levels: List[float], counts: List[int], poc_idx: int) -> Tuple[str, float, Dict[str, float]]:
```

Input:

- `levels`: các price level tạo từ `low_min`, `tick_size` trong `_build_levels_and_counts`.
- `counts`: số lần mỗi price level được cover bởi high-low range của từng M1 candle trong session.
- `poc_idx`: index của POC được tính trong `_build_profile_from_counts`.

Output:

- `shape`: một trong `D`, `B`, `p`, `b`.
- `confidence_pct`: score đã normalize của shape thắng, đơn vị phần trăm.
- `shape_scores_pct`: dict phần trăm cho đủ 4 shape.

### Call chain trong TPO

1. `TPOSignal.calculate` kiểm tra DataFrame, lấy timestamp hiện tại, tạo `state_obj.tpo_profile`/`state_obj.tpo_cache`, rồi tính:
   - `tpo_d1`: `_compute_d1(df, ts)`
   - `tpo_h1`: `_compute_sliding(df, ts, tf="H1", count=6, cache=...)`
   - `tpo_m30`: `_compute_sliding(df, ts, tf="M30", count=6, cache=...)`
   Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:25-51`.
2. `_compute_d1` lấy session từ đầu ngày UTC tới `now_ts`, sau đó gọi `_build_tpo_block`.
   Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:53-59`.
3. `_compute_sliding` resample M1 sang H1/M30, duyệt các bucket gần nhất, dùng cache cho bucket đã đóng và gọi `_build_tpo_block` cho bucket chưa cache/current.
   Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:61-98`.
4. `_build_tpo_block` gọi `_build_levels_and_counts`, `_build_profile_from_counts`, rồi `_classify_shape`.
   Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:100-120`.

### Logic scoring hiện tại

Trong `_classify_shape`:

- Nếu không có count hoặc total <= epsilon: trả về `D`, confidence `0.0`, score 0 cho mọi shape.
  Evidence: `tpo.py:123-129`.
- Tính `upper_mass`, `lower_mass`, `skew` quanh `poc_idx`.
  Evidence: `tpo.py:131-133`.
- Tìm local peaks bằng điều kiện `c >= left and c >= right`, sort giảm dần, lấy `dual_peak_ratio = p2 / p1`.
  Evidence: `tpo.py:135-145`.
- Tính tail mean 20% dưới/trên profile bằng `n // 5`.
  Evidence: `tpo.py:147-150`.
- Score:
  - `D`: cao khi skew nhỏ và dual peak không vượt mạnh ngưỡng 0.45.
  - `B`: cao khi dual peak ratio lớn hơn 0.35 và skew nhỏ.
  - `p`: cao khi skew dương hoặc lower tail mean > upper tail mean.
  - `b`: cao khi skew âm hoặc upper tail mean > lower tail mean.
  Evidence: `tpo.py:152-157`.
- Normalize score thành phần trăm, chọn shape có score cao nhất.
  Evidence: `tpo.py:159-170`.

### Profile/count construction có liên quan

`_build_levels_and_counts` tạo histogram theo price level với `tick_size`, rồi với mỗi M1 candle tăng count cho mọi level nằm trong `[low, high]`.
Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:172-196`.

`_build_profile_from_counts` chọn POC bằng max count, tie-break theo khoảng cách tới midpoint và index, sau đó expand VAH/VAL đến khi đạt `value_area_pct`.
Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:210-262`.

Điểm quan trọng: shape không dùng volume, close location, sequence/time ordering bên trong session, hay historical shift; nó chỉ nhìn histogram counts theo range coverage.

## Role in TPO System

### Indicator snapshot và Telegram SIGNAL ALERT

Sau khi `TPOSignal.calculate` chạy, payload được lưu vào `state_obj.tpo_profile`.
Evidence: `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:39-45`.

`build_indicator_snapshot_for_telegram` đọc `state.tpo_profile` và expose:

- `tpo_d1`
- `tpo_h1`
- `tpo_m30`

Evidence: `D:/Aureus/services/aureus-signal/engine/indicator_snapshot.py:123-139`.

Live engine đưa `indicator_snapshot` vào `signal_payload` và publish stream; khi có transient signals, payload này cũng đi vào `publish_signal_event` cho SIGNAL_EVENT.
Evidence: `D:/Aureus/services/aureus-signal/engine/live_engine.py:827-859`.

Notifier render TPO block trong `_format_indicator_section`. Nếu block có `POC/VAH/VAL` thì render base; nếu `shape` thuộc `D/B/p/b` và `shape_confidence_pct` là số thì thêm `Shape:<shape> (<confidence>%)`.
Evidence: `D:/Aureus/services/aureus-notifier/formatters.py:87-107`.

Vì vậy shape ảnh hưởng trực tiếp tới SIGNAL ALERT Telegram như một phần giải thích trạng thái TPO.

### Strategy context / strategy match

`strategy_executor.py` gắn `indicator_snapshot` vào từng `strategy_result` trước khi `publish_strategy_match`.
Evidence: `D:/Aureus/services/aureus-signal/engine/strategy_executor.py:625-650`.

`publish_strategy_match` gọi `_resolve_strategy_match_signal_snapshot`, trong đó `_build_signal_snapshot_from_indicator_snapshot` derive một số field từ indicator snapshot rồi merge vào `signal_snapshot`.
Evidence: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:143-150` và `:184-229`.

Tuy nhiên `_build_signal_snapshot_from_indicator_snapshot` hiện chỉ flatten EMA, ATR, volume SMA, session, BB, candle color và CISD MTF; không thấy mapping `tpo_d1/tpo_h1/tpo_m30` hoặc `shape` vào signal snapshot.
Evidence: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:22-127`.

Nhận định có bằng chứng:

- Shape có mặt trong `indicator_snapshot` của strategy result nếu payload chứa TPO.
- Shape chưa thấy được flatten vào `signal_snapshot` dùng cho persistence/strategy context derived fields.
- Không có bằng chứng trong các file đã đọc rằng `_classify_shape` trực tiếp kích hoạt strategy scoring. Tác động strategy hiện tại nhiều khả năng là context/diagnostic nếu consumer đọc nguyên `indicator_snapshot`; còn nếu chỉ dùng `signal_snapshot`, TPO shape không đi vào.

### Test coverage hiện có

Các test xác nhận block TPO có đủ keys `POC/VAH/VAL/shape/shape_confidence_pct/shape_scores_pct`, shape nằm trong `D/B/p/b`, confidence 0-100, score keys đủ 4 shape.
Evidence: `D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py:34-52`, `:152-167`, `:190-219`.

Test hiện chưa xác nhận semantic đúng cho từng shape D/B/p/b bằng fixtures đại diện từng profile. Test hiện chủ yếu xác nhận contract và probability distribution hợp lệ.

## Weaknesses and Risks

### 1. Confidence hiện là normalized heuristic score, chưa phải xác suất đã calibrate

Confirmed by code: `shape_confidence_pct` là score thắng sau khi normalize tổng 4 score về 100% (`tpo.py:159-170`). Không có calibration từ labeled data, replay, hay backtest trong hàm.

Operational impact: Telegram hiển thị dạng phần trăm có thể khiến người dùng hiểu nhầm là xác suất thống kê. Một shape `D 70%` hiện chỉ nghĩa là rule score D chiếm 70% trong bộ heuristic này, không chứng minh D-shape thật với độ tin cậy 70%.

### 2. Threshold brittle cho B shape và D shape

Confirmed by code: B phụ thuộc `dual_peak_ratio - 0.35`; D bị trừ khi `dual_peak_ratio > 0.45` (`tpo.py:152-154`). Đây là hard-coded thresholds.

Operational impact: profile gần ngưỡng có thể flip D/B chỉ vì một vài bin count thay đổi do candle mới, tick size hoặc sparse data. Trong SIGNAL ALERT, điều này làm context TPO dễ nhiễu ở current H1/M30 bucket.

### 3. Dual peak detection không kiểm tra khoảng cách giữa peaks

Confirmed by code: local maxima chỉ cần `c >= left and c >= right`, sau đó lấy hai prominence lớn nhất (`tpo.py:135-145`). Không có điều kiện valley depth giữa hai peaks, khoảng cách tối thiểu, hay separation theo price.

Operational impact: B-shape double distribution có thể bị nhận nhầm khi hai local peaks nằm sát nhau do noise; ngược lại B thật nhưng peaks không clean cũng có thể bị đánh thấp.

### 4. p/b semantics đang phụ thuộc skew và tail mean, không dùng time/order flow

Confirmed by code: p score = `skew + lower_tail_mean advantage`; b score = `-skew + upper_tail_mean advantage` (`tpo.py:155-156`). Hàm không dùng thứ tự thời gian trong session, không biết late upper/lower extension xảy ra khi nào.

Operational impact: p thường được hiểu như short-covering/upper distribution, b như long-liquidation/lower distribution. Nếu không biết extension xảy ra sớm hay muộn, shape có thể đúng hình học nhưng sai narrative thị trường. Điều này ảnh hưởng interpretation trong strategy review.

### 5. Sparse/incomplete current sessions dễ gây shape quá sớm

Confirmed by code: `calculate` chỉ yêu cầu len(df) >= 2 (`tpo.py:25-29`), short data vẫn được test là trả realtime blocks (`test_tpo_signal.py:54-64`). `_compute_sliding` current bucket tính tới `now_ts` và không yêu cầu số M1 tối thiểu (`tpo.py:86-96`).

Operational impact: đầu phiên/đầu bucket H1/M30, profile rất ít candles nhưng vẫn có shape/confidence. SIGNAL ALERT có thể hiển thị shape nhìn chắc chắn trong khi dữ liệu chưa đủ mature.

### 6. Tick size/binning ảnh hưởng trực tiếp tới shape

Confirmed by code: `levels_count` và index count phụ thuộc `self.tick_size`; default tick_size là 0.1 (`tpo.py:20-23`, `:181-194`). Shape dùng chính `levels/counts` này.

Operational impact: với symbol có precision khác nhau hoặc volatility khác nhau, cùng cấu trúc giá có thể tạo histogram khác. Nếu tick size không theo symbol/session volatility, score shape không ổn định giữa XAUUSD/forex/index.

### 7. Range coverage count không phân biệt close/volume/time-at-price thật

Confirmed by code: mỗi candle tăng count cho toàn bộ level từ low đến high (`tpo.py:186-194`), không dùng close, open, volume hoặc intrabar path.

Operational impact: candle có wick dài sẽ lấp nhiều bins như thể market chấp nhận toàn bộ range. Điều này có thể làm VA và shape bị kéo rộng, đặc biệt trong tin tức/outlier.

### 8. Outliers/wicks có thể kéo `low_min/high_max`, tail windows và skew

Confirmed by code: profile range lấy max high/min low toàn session (`tpo.py:172-183`), tail là 20% số bins ở hai đầu (`tpo.py:147-150`). Không có outlier clipping.

Operational impact: một spike làm tăng số bins, thay đổi tail mean, giảm/méo counts tương đối và làm p/b/D/B thay đổi. Đây là rủi ro lớn với current D1/H1 khi có news candle.

### 9. D1 session là UTC day, không phải market session configurable

Confirmed by code: `day_start = now_ts - (now_ts % 86400)` (`tpo.py:53-55`).

Operational impact: nếu TPO shape cần theo phiên Asian/London/New York hoặc broker day, D1 shape hiện có thể trộn/đứt phiên không đúng logic giao dịch. Đây là issue semantic hơn là bug.

### 10. B score có thể overlap với D trong balanced-but-lumpy profile

Confirmed by code: D ưu tiên skew thấp và dual peak thấp; B cũng cộng điểm khi skew thấp (`tpo.py:152-154`). Không có explicit rule về valley giữa distributions.

Operational impact: balanced rotation có vài cụm high count do market revisit có thể bị B hóa, dẫn tới người đọc Telegram diễn giải double distribution quá mức.

### 11. Không có explicit unknown/low-data state

Confirmed by code: fallback n=0/total<=0 trả `D` với 0 confidence, còn có dữ liệu thì luôn chọn một shape (`tpo.py:123-170`).

Operational impact: hệ thống không có trạng thái `unknown` hoặc `insufficient_data`. Consumer phải tự hiểu confidence thấp; Telegram hiện vẫn render Shape nếu shape hợp lệ và confidence là số (`formatters.py:98-102`).

### 12. Uncertainty: chưa chứng minh shape đang đi vào DB snapshot

Trong source đã đọc, `indicator_snapshot` chứa TPO và Telegram render shape. `_build_signal_snapshot_from_indicator_snapshot` không flatten TPO shape. Báo cáo này không khẳng định DB trade snapshot hiện persist shape vì chưa thấy mapping trong file đã đọc. Nếu future requirement cần lưu shape vào DB, cần trace riêng qua journal/db-writer schemas.

## Improvement Approaches

### Approach 1: Calibrated heuristic với distribution metrics rõ hơn

Concept:

Giữ heuristic deterministic nhưng thay score hiện tại bằng bộ metrics explicit hơn:

- symmetry score quanh POC
- kurtosis/compactness của value area
- peak separation và valley depth cho B
- upper/lower excess area cho p/b
- minimum sample/bucket maturity gate
- confidence dựa trên margin giữa top-1/top-2 và data quality, không chỉ normalized sum

Data required:

- `levels`, `counts`, `poc_idx` hiện có.
- Thêm derived metrics: total TPO count, number of bins, VA width, peak indices, valley ratio, sample minutes.

Expected benefit:

- Ít flip shape do threshold đơn lẻ.
- B-shape có bằng chứng double distribution tốt hơn vì kiểm tra separation/valley.
- Confidence dễ giải thích hơn: high confidence khi top shape cách xa runner-up và data đủ mature.

Risk/tradeoff:

- Vẫn là rule-based, có thể overfit nếu chỉnh threshold theo cảm tính.
- Cần document metric definitions để tránh biến thành magic numbers mới.

Implementation complexity:

- Low to medium. Có thể làm trong cùng `TPOSignal` hoặc helper nhỏ nếu future implement cho phép.

How to validate:

- Unit test synthetic profiles cho từng shape D/B/p/b.
- Boundary tests quanh threshold để đảm bảo không flip bất thường.
- Replay H1/M30/D1 vài ngày, log transition rate của shape và confidence.
- So sánh Telegram snapshots trước/sau trên cùng dữ liệu để kiểm tra giảm noise.

### Approach 2: Multi-session/timeframe context và maturity gating

Concept:

Không classify current bucket như profile hoàn chỉnh nếu dữ liệu chưa đủ. Thêm context:

- H1/M30 current bucket cần minimum elapsed minutes hoặc minimum TPO count.
- D1 nên cân nhắc session definition: UTC day, broker day, hoặc market session window.
- Compare shape D1/H1/M30 để phân biệt local noise với context lớn.
- Có thể output `shape_status`: `forming`, `confirmed`, `insufficient_data` trong future contract.

Data required:

- Bucket start/end/current timestamp đã có trong `_compute_sliding`.
- Session elapsed minutes, count candles, total counts.
- Optional market session/broker timezone config nếu thay D1 semantics.

Expected benefit:

- Giảm misleading shape ở đầu bucket.
- Người dùng Telegram biết shape đang forming hay đã đủ mature.
- Strategy interpretation an toàn hơn: H1 p-shape forming không bị hiểu như confirmed p-shape.

Risk/tradeoff:

- Có thể làm giảm số alert có shape trong giai đoạn đầu phiên.
- Nếu đổi session definition sẽ là thay đổi semantic lớn, cần quyết định rõ để không phá kỳ vọng hiện tại.

Implementation complexity:

- Medium. Maturity gate đơn giản là low; session model configurable là medium/high vì ảnh hưởng D1 và tests.

How to validate:

- Tests cho short data: expected `insufficient_data` hoặc confidence cap thay vì shape mạnh.
- Replay transition timeline trong từng H1/M30 bucket để đo số lần shape flip theo elapsed minutes.
- So sánh UTC D1 vs session-based D1 trên cùng symbols.

### Approach 3: Rule-based hybrid với TPO detector outputs

Concept:

Không để `_classify_shape` tự quyết toàn bộ narrative. Kết hợp shape geometry với detector context như:

- VA rejection
- VA breakout acceptance
- trend pullback around VA/POC
- POC/VA shift history
- price relation to VAH/VAL/POC

Shape trở thành feature trong TPO context, detector xác nhận operational meaning.

Data required:

- Current TPO block: POC/VAH/VAL/shape/confidence.
- Recent price relative to VAH/VAL/POC.
- TPO history store hoặc prior blocks để biết shift.
- Detector outputs từ TPO feature layer nếu đã có trong các quick tasks sau `260425-ekl`.

Expected benefit:

- Giảm rủi ro diễn giải shape đơn độc.
- Strategy có thể dùng composite context: ví dụ `B` + breakout acceptance khác với `B` + rejection.
- Dễ explain trong Telegram: shape là backdrop, detector là trigger context.

Risk/tradeoff:

- Complexity tăng. Nếu không tách rõ indicator/feature/detector/signal, code có thể khó bảo trì.
- Detector sai có thể che hoặc khuếch đại shape sai.

Implementation complexity:

- Medium to high tùy mức TPO detector infrastructure hiện có.

How to validate:

- Contract tests cho TPO context builder.
- Detector unit tests với fixtures giá quanh VAH/VAL/POC.
- Replay/backtest so sánh strategy tags có/không có shape confirmation.
- Kiểm tra false positives của SIGNAL ALERT khi shape high confidence nhưng detector không xác nhận.

### Approach 4: Offline labeled replay/backtest calibration

Concept:

Xây tập replay từ historical M1 để tính TPO blocks, sau đó gắn label thủ công/bán tự động hoặc proxy label cho D/B/p/b. Dùng tập này để hiệu chỉnh threshold, confidence bins, và kiểm tra shape có liên quan tới outcome strategy không.

Data required:

- Historical M1 OHLCV đủ dài theo symbol.
- Output TPO blocks per D1/H1/M30.
- Optional human labels hoặc deterministic labels từ visual/profile review.
- Trade outcomes/strategy match outcomes nếu muốn đo operational value.

Expected benefit:

- Confidence có thể được calibrate thành reliability bucket thực tế.
- Biết shape nào hữu ích cho strategy nào, timeframe nào.
- Giảm tranh luận cảm tính về threshold.

Risk/tradeoff:

- Tốn công data labeling và replay harness.
- Proxy labels có thể encode bias của heuristic cũ nếu không cẩn thận.
- Nếu data quá ít symbol/regime, calibration overfit.

Implementation complexity:

- Medium nếu replay harness đã có; high nếu cần labeling UI/process.

How to validate:

- Split train/validation theo thời gian, không random shuffle thuần túy.
- Calibration plot: confidence bucket vs label agreement.
- Stability test qua volatility regimes/sessions.
- Backtest A/B: baseline no-shape vs heuristic shape vs calibrated/hybrid shape.

## Recommendation

Nên chọn lộ trình 2 bước, không nhảy thẳng sang ML:

1. Ngắn hạn: Approach 1 + một phần Approach 2.
   - Cải thiện heuristic bằng peak separation, valley depth, maturity gate, confidence margin.
   - Đây là thay đổi nhỏ nhất nhưng xử lý đúng các rủi ro lớn nhất: threshold brittle, sparse current bucket, confidence misleading.
2. Trung hạn: Approach 3 + Approach 4.
   - Đưa shape vào TPO context/detector như feature, không dùng shape đơn độc làm trigger.
   - Dùng replay/backtest để calibrate threshold và chứng minh shape có giá trị operational.

Không khuyến nghị:

- Không nên chỉ đổi vài threshold `0.35/0.45` mà không thêm tests/replay, vì sẽ chỉ chuyển bias từ chỗ này sang chỗ khác.
- Không nên đưa `shape_confidence_pct` vào strategy scoring như xác suất thật trước khi calibration.
- Không nên implement session-based D1 nếu chưa quyết định rõ session semantics cho toàn hệ thống.

## Suggested Verification Plan

Nếu future task implement cải thiện, nên test theo thứ tự:

1. Unit fixtures cho shape geometry:
   - D: single balanced bell/rotation quanh POC.
   - B: two separated peaks với valley rõ.
   - p: upper-heavy profile có lower tail/short-covering signature theo rule đã định nghĩa.
   - b: lower-heavy profile có upper tail/long-liquidation signature theo rule đã định nghĩa.
2. Edge cases:
   - Empty/zero counts.
   - Sparse 2-5 candles.
   - Long wick/outlier.
   - Very small/large tick_size.
   - Equal peaks and flat profile.
3. Integration tests:
   - `TPOSignal.calculate` vẫn trả block contract đầy đủ.
   - `build_indicator_snapshot_for_telegram` vẫn map `tpo_d1/h1/m30`.
   - Notifier vẫn render Shape khi valid, và render safe fallback khi unknown/insufficient nếu future contract thêm state.
4. Replay validation:
   - Đo shape flip rate trong current H1/M30 bucket.
   - Đo confidence distribution theo session/timeframe.
   - So sánh trước/sau trên SIGNAL ALERT samples.
5. Strategy validation nếu dùng shape cho scoring:
   - A/B backtest với shape disabled/enabled.
   - Kiểm tra per-strategy outcome thay vì chỉ aggregate.
   - Confirm không tăng false positives trong low-liquidity/news windows.

## Sources

- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:20-23` — constructor clamp `value_area_pct`, `tick_size`.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:25-51` — `calculate` tạo `tpo_d1/tpo_h1/tpo_m30` và lưu `state_obj.tpo_profile`.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:53-59` — D1 today-only UTC window.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:61-98` — H1/M30 sliding buckets và cache closed bucket.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:100-120` — `_build_tpo_block` gọi `_classify_shape` và trả shape fields.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:122-170` — full `_classify_shape` heuristic.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:172-196` — `_build_levels_and_counts` histogram theo high-low range.
- `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:210-262` — `_build_profile_from_counts` xác định POC/VAH/VAL/poc_idx.
- `D:/Aureus/services/aureus-signal/engine/indicator_snapshot.py:123-139` — mapping `tpo_profile` vào indicator snapshot.
- `D:/Aureus/services/aureus-signal/engine/live_engine.py:827-859` — publish signal payload và SIGNAL_EVENT với indicator snapshot.
- `D:/Aureus/services/aureus-notifier/formatters.py:87-107` — Telegram render `Shape:<shape> (<confidence>%)`.
- `D:/Aureus/services/aureus-signal/engine/strategy_executor.py:625-650` — attach indicator snapshot vào strategy result.
- `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:22-127` — derive signal snapshot từ indicator snapshot nhưng chưa flatten TPO fields.
- `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:143-150` và `:184-229` — strategy match publish path.
- `D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py:34-52` — test TPO block contract.
- `D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py:54-64` — short data vẫn trả realtime blocks.
- `D:/Aureus/services/aureus-signal/tests/test_tpo_signal.py:190-219` — test shape/confidence/scores distribution contract.

## Analysis-only statement

Không có production source, tests, migrations, runtime config hoặc database schema nào được thay đổi trong quick task này. Artifact được tạo là report phân tích để hỗ trợ quyết định future implementation.
