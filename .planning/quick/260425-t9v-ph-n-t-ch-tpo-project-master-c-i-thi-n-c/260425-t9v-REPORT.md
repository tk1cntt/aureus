# Advisory 260425-t9v: TPO shape classifier và mapping distribution/daytype

## 1. Phạm vi và kết luận ngắn

Báo cáo này chỉ phân tích/advisory, không sửa source code.

Kết luận chính: `tpo_project-master` không cung cấp trực tiếp classifier D/B/p/b tương đương Aureus. Phần hữu ích nhất để tham khảo là logic `distr/daytype` trong `tpo_helper.py`, tức một chiều ngữ cảnh phân phối theo ngày, không phải nhãn hình dạng profile.

Khuyến nghị: giữ D/B/p/b shape như metadata hình dạng riêng, đồng thời nếu triển khai thêm thì đưa `distr` thành `distribution_regime` hoặc `day_type` độc lập. Dimension này chỉ nên điều chỉnh confidence/context tag trong TPO strategy, không tự phát sinh buy/sell signal khi thiếu price relation với POC/VAH/VAL.

## 2. Current Aureus `_classify_shape`: vì sao có thể sinh D/p/50% gây nghi ngờ

Trong `D:/Aureus/services/aureus-signal/engine/signals/tpo.py`, `TPOSignal._build_tpo_block` tạo block gồm `POC`, `VAH`, `VAL`, `shape`, `shape_confidence_pct`, `shape_scores_pct`. Nhãn shape đến từ `_classify_shape(levels, counts, poc_idx)`.

Các biến chính trong classifier hiện tại:

- `total`: tổng số TPO count hợp lệ.
- `usable_bins`: số price bin có count > 0.
- `coverage`: `usable_bins / n`.
- `maturity`: `min(1.0, total / 20.0)`.
- `usable_quality`: `min(1.0, usable_bins / 5.0)`.
- `data_quality`: cap chất lượng dữ liệu từ coverage, maturity, usable bins.
- `upper_mass`, `lower_mass`, `poc_mass`, `skew`: phân bổ khối lượng trên/dưới POC.
- `symmetry`: độ cân bằng hai phía quanh POC.
- `compactness`: tỷ lệ count nằm gần POC.
- `b_evidence`: bằng chứng double-distribution từ hai peak và valley.
- `tail_delta`, `upper_share`, `lower_share`: bằng chứng lệch tail/share để tính p/b.

Điểm thô được tính như sau về mặt semantics:

- `d_score`: tăng khi profile cân xứng và compact quanh POC; giảm khi có `b_evidence` hoặc skew mạnh.
- `b_score`: phụ thuộc vào `b_evidence`, có nhân thêm symmetry nhẹ.
- `p_score`: tăng khi upper share lớn hơn lower share, tail pattern nghiêng theo p, và skew dương.
- `b_lower_score`: đối xứng với p, đại diện chữ `b` thường.

Sau đó classifier chuẩn hóa thành `shape_scores_pct` bằng cách lấy mỗi score chia cho tổng score. Vì vậy số phần trăm ở đây là tỷ trọng tương đối giữa các heuristic đang cạnh tranh, không phải xác suất thống kê đã calibrate. Một output kiểu D/p/50% có thể chỉ có nghĩa là D và p là hai heuristic mạnh nhất trong mẫu hiện tại, không có nghĩa profile chắc chắn là D hoặc p theo cách nhìn chart thủ công.

`confidence` cũng không phải `top_score` thuần. Nó bị chi phối bởi margin giữa top và runner-up, `data_quality`, và nhiều cap:

- Nếu margin nhỏ hơn 20 điểm, `margin_factor` bị nhân 0.45.
- `confidence_cap = 20 + 75 * data_quality`.
- Nếu có `b_evidence` nhưng `b_score < d_score`, cap tối đa 50%.
- Nếu `usable_bins < 5` hoặc `total < 20`, cap tối đa 35%.
- Nếu `0 < b_evidence < 0.85`, cap tối đa 50%.

Vì vậy một kết quả có shape score nhìn khá cao vẫn có confidence thấp/trung bình nếu dữ liệu còn non, usable bins ít, hoặc có bằng chứng B chưa đủ mạnh. Đây là lý do các output kiểu `D/p/50%` không nhất thiết là bug crash pipeline; nó là hệ quả của heuristic score tương đối + confidence cap.

Điểm dễ gây hiểu nhầm nhất: `D` có thể thắng nhờ `symmetry + compactness` ngay cả khi visual profile vẫn mơ hồ. Nếu profile có hai peak yếu hoặc valley chưa rõ, `b_evidence` vừa đủ để giảm confidence nhưng chưa đủ để thắng `d_score`. Khi đó D vẫn đứng đầu, confidence bị cap quanh 50% hoặc thấp hơn.

Ngược lại, `p` hoặc `b` có thể thắng nhờ tail/share skew mà không có concept distribution/daytype riêng. Classifier hiện tại không hỏi “ngày này là Trend Day hay Neutral Day so với lịch sử”; nó chỉ nhìn hình dạng count trong block hiện tại. Do đó p/b score có thể phản ánh lệch phân bổ cục bộ, không đồng nghĩa với trend distribution theo nghĩa `tpo_project-master`.

## 3. Reference `tpo_project-master`: logic nào liên quan trực tiếp

Trong `D:/Aureus/tpo_project-master/tpo_helper.py`, hàm `tpo()` xây TPO profile thủ công:

- Tạo price levels từ low đến high theo `ticksize`.
- Với mỗi level, ghép chữ cái phiên vào `alphabets` và cộng `tpocount`.
- Chọn POC từ level có `tpocount` max, nếu nhiều candidate thì chọn gần midpoint.
- Tính VAH/VAL bằng cách mở rộng quanh POC theo count phía trên/dưới.
- Tính thêm LVN, excess, balance target.

Phần này có liên quan đến Aureus ở mức profile mechanics: POC/VAH/VAL/count distribution. Nó không phải classifier D/B/p/b.

Logic liên quan nhất nằm trong `get_context()`:

```python
dist_df['distr'] = dist_df.tpocount/dist_df.maxtpo
dismean = math.floor(dist_df.distr.mean())
dissig = math.floor(dist_df.distr.std())
```

Sau đó `daytype` được gán theo vị trí của `distr` so với mean/std lịch sử:

- `distr >= dismean` và `< dismean + dissig` → `Trend Distribution Day`.
- `distr < dismean` và `>= dismean - dissig` → `Normal Variation Day`.
- `distr < dismean - dissig` → `Neutral Day`.
- `distr > dismean + dissig` → `Trend Day`.

Ý nghĩa đáng tham khảo: `distr = tpocount / maxtpo` đo độ phân phối rộng/hẹp của tổng TPO count so với count cực đại tại POC. Đây là một regime/daytype dimension được calibrate theo lịch sử nhiều ngày, không phải nhãn hình học D/B/p/b trong một block đơn lẻ.

Các hàm phụ trợ khác:

- `get_rf()` tạo `rf` từ hướng Close/High/Low so với bar trước, dùng làm breadth/range-flow context.
- `get_mean()` tính rolling mean volume/rf/IB để làm baseline lịch sử.
- `get_contextnow()` đánh giá initial balance hiện tại so với POC/VAH/VAL và volume/rf mean.

Các phần này hữu ích như context/ranking phụ trợ, nhưng không nên copy nguyên xi vào Aureus vì naming, index handling, dataframe schema, session assumption, và calibration khác nhau.

## 4. Logic nào không nên copy nguyên xi

Không nên copy trực tiếp `tpo_project-master` vào source Aureus vì:

1. Code reference dùng schema OHLCV khác (`Open`, `High`, `Low`, `Close`, `Volume`, `datetime`) trong khi Aureus signal hiện dùng `t`, `h`, `l`, `c`.
2. `get_context()` group theo ngày và dùng lịch sử nhiều ngày; Aureus hiện build D1/H1/M30 block trong signal runtime.
3. `distr/daytype` ở reference là historical classification, không phải shape classifier D/B/p/b.
4. Threshold dùng `math.floor(mean/std)` có thể quá thô với symbol/timeframe khác nhau.
5. Logic `daytype` có semantics market profile truyền thống, cần calibrate lại với data Aureus và từng symbol trước khi ảnh hưởng strategy.

Do đó hướng đúng là học concept `distr` và daytype calibration, không copy implementation.

## 5. Mapping đề xuất: `distr` sang semantics TREND/NORMAL/NEUTRAL

Bảng mapping khuyến nghị cho Aureus:

| Reference regime | Điều kiện khái niệm | Aureus semantics | Cách dùng khuyến nghị |
|---|---|---|---|
| `distr cao` | `distr` cao hơn baseline lịch sử, tốt nhất > mean + sigma/quantile cao | `TREND` | Context trend-day/trend-distribution; tăng confidence cho continuation nếu price relation, POC shift, VA relation cùng hướng |
| `distr trung bình` | `distr` quanh baseline lịch sử | `NORMAL` | Context normal/normal-variation; giữ scoring cân bằng, ưu tiên setup có reclaim/reject/acceptance rõ |
| `distr thấp` | `distr` thấp hơn baseline lịch sử, profile kém phân phối hoặc low participation | `NEUTRAL` | Context balance/neutral/low-participation; giảm confidence cho trend continuation nếu thiếu breakout/acceptance |

Cụ thể:

- `distr cao → TREND`: chỉ nên dùng khi được calibrate với recent history và tốt hơn nếu được xác nhận bởi range expansion, POC shift, hoặc close relation với VAH/VAL. Không nên coi distr cao là tự động long/short.
- `distr trung bình → NORMAL`: phù hợp để diễn giải ngày normal variation, setup vẫn phải dựa trên price relation như VAL reclaim, VAH reject, VA breakout acceptance.
- `distr thấp → NEUTRAL`: nên hiểu là balance/low-participation context. Nó có thể làm giảm niềm tin vào trend signal, hoặc tăng cảnh báo mean-reversion/balance, nhưng không tự tạo entry.

## 6. Tương thích với TPO detectors hiện tại

Trong `D:/Aureus/services/aureus-signal/engine/signals/tpo_detectors.py`, các detector hiện tại đặt price relation làm điều kiện chính:

- `VARejectionDetector`: cần VAL reclaim hoặc VAH reject trên H1/M30.
- `VABreakoutAcceptanceDetector`: cần breakout/breakdown qua VAH/VAL và acceptance closes.
- `TrendPullbackDetector`: cần D1 bias/price relation, H1 pullback, M30 confirmation.

Shape hiện chỉ là supporting evidence:

- Long supportive shapes: `b`, `D`.
- Short supportive shapes: `p`, `D`.
- Nếu shape không support, detector vẫn nhấn mạnh price relation là primary.

Vì vậy `distribution_regime` tương lai nên nằm cùng cấp context với `shape`, `poc_shift`, `va_width_change`, `price_location`, không thay thế các điều kiện entry.

Ví dụ semantics an toàn:

- TREND + bullish POC shift + accepted above VAH → tăng confidence continuation.
- TREND nhưng close chưa liên quan VAH/VAL/POC → chỉ tag context, không emit setup.
- NEUTRAL + price near POC/inside VA → giảm confidence breakout, ưu tiên chờ confirmation.
- NORMAL → không bias quá mạnh, giữ detector hiện tại làm quyết định chính.

## 7. Future implementation yêu cầu trước khi sửa source code

Trước khi implement, nên có test plan rõ ràng:

1. Unit test cho `_classify_shape` hiện tại bằng synthetic profiles:
   - D cân xứng compact quanh POC.
   - B/double distribution có hai peak và valley rõ.
   - p skew upper-heavy.
   - b skew lower-heavy.
   - immature profile ít usable bins để xác nhận confidence cap.

2. Unit test cho distribution regime mới:
   - Tính `distr = total_tpo_count / max_tpo_count` từ profile count.
   - Calibrate baseline bằng rolling history hoặc fixture nhiều ngày.
   - Case `distr cao` trả `TREND`.
   - Case `distr trung bình` trả `NORMAL`.
   - Case `distr thấp` trả `NEUTRAL`.

3. Integration test cho `TPOContextBuilder` nếu thêm field:
   - Context của D1/H1/M30 có `distribution_regime` nhưng vẫn giữ `shape` và `shape_confidence_pct`.
   - Missing history không làm detector crash; regime có thể là `unknown` hoặc absent.

4. Detector test:
   - Distribution regime không tự tạo valid setup khi thiếu price relation.
   - TREND chỉ tăng score khi setup vốn đã valid theo VA/POC relation.
   - NEUTRAL chỉ giảm/annotate confidence theo rule đã định, không đảo chiều side.

5. Replay/backtest regression:
   - So sánh số lượng signal trước/sau.
   - Kiểm tra không tăng false-positive do regime tag.
   - Log các trường mới trong indicator snapshot nếu cần, nhưng tránh phá schema downstream.

## 8. Rủi ro semantics cần khóa trước implement

- Không gọi `distr` là “trend direction”. Nó là distribution intensity/regime, không biết long hay short nếu thiếu giá so với POC/VAH/VAL.
- Không dùng `TREND` để thay cho D1 bias. D1 bias hiện dựa vào close so với VAH/VAL/POC.
- Không dùng `distr thấp` như bearish. Low distribution có thể là balance, thiếu participation, hoặc profile chưa mature.
- Không trộn phần trăm `shape_scores_pct` với confidence của regime. Một bên là relative shape heuristic, một bên là historical regime classification.

## 9. Recommendation cuối cùng

Nên triển khai tương lai theo hướng hai tầng:

1. Cải thiện/calibrate shape classifier D/B/p/b riêng, để output visual-shape đáng tin hơn.
2. Thêm `distribution_regime` riêng dựa trên `distr` lịch sử: `TREND`, `NORMAL`, `NEUTRAL`.

Trong Aureus strategy, `distribution_regime` nên là context modifier:

- TREND: boost continuation/pullback setup đã có price confirmation.
- NORMAL: giữ neutral weighting.
- NEUTRAL: caution/discount trend continuation khi thiếu acceptance.

Không nên để `distr` trực tiếp emit buy/sell tags. Điều kiện primary vẫn là price relation với POC/VAH/VAL, D1 bias, POC shift, và acceptance/reclaim/reject như hệ thống hiện tại.

## 10. Checklist đáp ứng yêu cầu

- Đã giải thích vì sao `_classify_shape` có thể sinh D/p/50% gây nghi ngờ mà không crash pipeline.
- Đã phân biệt rõ Aureus D/B/p/b shape với `tpo_project-master` daytype/distribution logic.
- Đã nêu logic reference hữu ích nhất là `distr/daytype`, không phải D/B/p/b classifier.
- Đã mapping cụ thể `distr cao → TREND`, `distr trung bình → NORMAL`, `distr thấp → NEUTRAL`.
- Đã khuyến nghị future implementation và test trước khi sửa source code.
