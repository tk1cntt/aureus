# Advisory 260425-tpc: TPO shape và distribution regime

## 1. Neutral Listing

Tài liệu này là đánh giá kiến trúc độc lập đối với report `260425-t9v`; mục tiêu là khóa semantics trước khi có implementation tương lai, không sửa source code. Các lựa chọn khả thi cần được nhìn như các phương án tách biệt, không giả định report trước luôn đúng.

1. **Giữ classifier hiện tại và calibrate**: tiếp tục dùng `_classify_shape(levels, counts, poc_idx)` như visual profile metadata cho D/B/p/b, nhưng bổ sung fixture, threshold calibration và giải thích confidence để giảm output mơ hồ.
2. **Thay classifier bằng rule/fixture-driven classifier**: định nghĩa lại bộ rule D/B/p/b theo synthetic profile chuẩn, làm `_classify_shape` dễ kiểm thử hơn và ít phụ thuộc vào heuristic score tương đối hiện tại.
3. **Thêm `distribution_regime` riêng từ `distr`**: tính `distr = total_tpo_count / max_tpo_count`, so với baseline lịch sử/rolling để sinh regime như `TREND`, `NORMAL`, `NEUTRAL`, `UNKNOWN`.
4. **Không thêm regime vào signal**: chỉ cải thiện report/observability, giữ detector hiện tại dựa trên price relation với POC/VAH/VAL để tránh mở thêm semantics chưa kiểm chứng.
5. **Kết hợp shape + regime ở layer context**: giữ shape là visual-shape, thêm regime là distribution intensity/regime trong `TPOContextBuilder`, rồi để detector dùng như context modifier khi setup vốn đã valid.

Các lựa chọn trên đều hợp lệ ở một phạm vi nhất định. Điểm cần tránh là trộn `shape`, `distribution_regime`, và direction signal thành cùng một nhãn vì điều đó làm người đọc hiểu sai `distr` như long/short bias.

## 2. Attribute Mapping

| Lựa chọn | Correctness | Semantic clarity | Implementation risk | Detector compatibility | Testability | Risk of false positives |
|---|---|---|---|---|---|---|
| Giữ classifier hiện tại và calibrate | Tốt nếu chỉ cần cải thiện độ tin cậy của D/B/p/b; chưa giải quyết distribution/daytype | Trung bình-tốt: vẫn giữ `_classify_shape` đúng vai trò visual profile metadata | Thấp-trung bình vì không đổi contract lớn | Cao, vì detectors hiện đã xem shape là supporting metadata | Tốt nếu có synthetic fixtures cho D/B/p/b và immature profile | Thấp nếu không tăng score quá mạnh |
| Thay classifier bằng rule/fixture-driven | Có thể tốt hơn nếu rule được khóa bằng fixture thực tế | Tốt: output shape dễ giải thích hơn | Trung bình vì có thể đổi phân bố label hiện có | Trung bình-cao; cần regression để tránh phá replay/backtest comparability | Rất tốt với fixture-driven tests | Trung bình nếu rule mới tự tin quá mức |
| Thêm `distribution_regime` riêng từ `distr` | Tốt nếu có baseline lịch sử/rolling; yếu nếu chỉ dùng threshold tĩnh | Rất tốt nếu ghi rõ `distr` là distribution intensity/regime, không phải direction | Trung bình vì cần history/baseline và propagation context | Cao nếu chỉ là context modifier | Tốt: unit test `distr`, quantile/baseline, propagation, detector non-emission | Thấp-trung bình; tăng nếu regime được dùng như trigger |
| Không thêm regime vào signal | Correctness cao theo nghĩa không introduce semantics mới | Rõ nhưng bỏ lỡ thông tin hữu ích từ report | Thấp nhất | Cao nhất | Dễ regression | Thấp nhất nhưng không giải quyết nhu cầu cải thiện context |
| Kết hợp shape + regime ở layer context | Tốt nhất nếu tách field và tách responsibility rõ | Rất tốt: shape = visual-shape, regime = distribution context | Trung bình do cần thêm field/context/test | Cao nếu detectors vẫn giữ price relation primary | Rất tốt nếu có test chứng minh regime không tự emit buy/sell | Thấp nếu score boost bị cap và chỉ áp dụng sau valid setup |

Đánh giá độc lập: report `260425-t9v` đúng khi cảnh báo `distr/daytype` của `tpo_project-master` không phải classifier D/B/p/b. Tuy nhiên report chưa đủ mạnh nếu chỉ dừng ở “nên thêm context”; implementation basis phải khóa được baseline, UNKNOWN behavior, và nguyên tắc không thay D1 bias.

## 3. Contextual Recommendation

Trong kiến trúc Aureus hiện tại, `TPOSignal._build_tpo_block(...)` trả về `POC`, `VAH`, `VAL`, `shape`, `shape_confidence_pct`, và `shape_scores_pct`. `_classify_shape` nên được hiểu là visual-shape classifier cho hình dạng profile D/B/p/b trong block hiện tại. Nó không nên bị ép gánh nghĩa market daytype hoặc hướng giao dịch.

`distr` từ reference nên được đưa vào như một đại lượng khác: `distr = total_tpo_count / max_tpo_count`. Ý nghĩa hợp lý là distribution intensity/regime: profile phân phối rộng/hẹp so với điểm tập trung nhất và so với baseline lịch sử/rolling. `distribution_regime` vì vậy có thể là `TREND`, `NORMAL`, `NEUTRAL`, hoặc `UNKNOWN`, nhưng không có nghĩa long/short.

Các detector TPO hiện tại đặt price relation làm primary:

- VAL reclaim hoặc VAH reject cho VA rejection.
- Breakout/breakdown qua VAH/VAL kèm acceptance closes cho VA breakout acceptance.
- D1 bias, H1 pullback, M30 confirmation cho trend pullback.

Shape hiện chỉ là supporting metadata và trong invalid reasons đã nhấn mạnh shape không đủ nếu thiếu price relation. Vì vậy recommendation phù hợp nhất là giữ/cải thiện `_classify_shape` như visual-shape classifier riêng bằng fixture/calibration, đồng thời thêm `distribution_regime` riêng dựa trên `distr` với baseline lịch sử/rolling. Regime chỉ là context modifier cho detector scoring/tagging khi setup vốn đã valid theo price relation, không tự emit buy/sell và không thay D1 bias.

Cách dùng an toàn:

- `TREND`: chỉ boost nhẹ continuation/pullback nếu setup đã valid theo VA/POC relation và không conflict D1 bias.
- `NORMAL`: giữ weighting cân bằng, không tạo bias mới.
- `NEUTRAL`: giảm hoặc annotate confidence cho continuation thiếu acceptance; không đảo chiều side.
- `UNKNOWN`: không ảnh hưởng score, chỉ giữ metadata để tránh quyết định trên baseline thiếu dữ liệu.

## 4. Adversarial Mode

Phản biện chính với recommendation trên: thêm `distribution_regime` có thể làm hệ thống nhìn có vẻ “thông minh hơn” nhưng thực tế tăng false positives nếu baseline yếu hoặc semantics bị dùng quá tay.

1. **Nguy cơ overfitting**: synthetic fixtures cho D/B/p/b và ngưỡng `distr` có thể khớp vài mẫu đẹp nhưng sai trên symbol/timeframe khác. Nếu test chỉ dùng profile lý tưởng, classifier sẽ fail khi profile live nhiễu hoặc immature.
2. **Thiếu rolling baseline**: `distr` không có nhiều ý nghĩa nếu không so với lịch sử đủ đại diện. Threshold tĩnh hoặc copy `math.floor(mean/std)` từ reference có thể quá thô, làm `TREND`/`NEUTRAL` đổi trạng thái thất thường.
3. **Nhầm TREND thành long/short**: `TREND` chỉ nói distribution rộng/mạnh, không nói hướng. Nếu detector hoặc downstream dùng `TREND` như buy/sell bias, hệ thống sẽ phá nguyên tắc price relation primary.
4. **Làm tăng score quá mức**: nếu `distribution_regime` được cộng score độc lập, setup yếu có thể thành valid dù chưa reclaim/reject/accept VAH/VAL. Đây là rủi ro trực tiếp cho false positives.
5. **Phá replay/backtest comparability**: thêm field và scoring modifier có thể làm số lượng signal thay đổi. Nếu không có regression basis trước/sau, khó biết improvement đến từ signal tốt hơn hay chỉ từ nới điều kiện.
6. **Mơ hồ giữa shape score và regime confidence**: `shape_scores_pct` là tỷ trọng heuristic tương đối; regime từ `distr` là historical classification. Trộn hai confidence này sẽ làm debugging khó và làm advisory bị hiểu sai.

Điều kiện để recommendation vẫn đáng làm: phải có `UNKNOWN` khi thiếu baseline, detector tests chứng minh regime không tự tạo setup, và replay/backtest regression trước khi cho regime tác động score live.

## Suggested Best Choice

Best choice cụ thể: **giữ và cải thiện `_classify_shape` như visual-shape classifier riêng bằng synthetic fixture/calibration, đồng thời thêm `distribution_regime` riêng dựa trên `distr = total_tpo_count / max_tpo_count` với baseline lịch sử/rolling; `distribution_regime` chỉ là context modifier cho detector scoring/tagging khi setup vốn đã valid theo price relation, không tự emit buy/sell và không thay D1 bias.**

Chi tiết quyết định:

- `_classify_shape` tiếp tục trả D/B/p/b, confidence, scores cho visual-shape metadata.
- `distr` được tính từ profile count, không lấy từ direction hoặc close movement.
- `distribution_regime` dùng tập giá trị tối thiểu: `TREND`, `NORMAL`, `NEUTRAL`, `UNKNOWN`.
- `UNKNOWN` là default bắt buộc khi thiếu đủ rolling-history/baseline.
- Detector không được chuyển invalid setup thành valid chỉ vì `TREND`.
- D1 bias vẫn dựa trên relation với VAH/VAL/POC; `distribution_regime` không thay D1 bias và không đảo side.
- Score modifier nếu có phải nhỏ, có cap, và chỉ chạy sau khi condition chính đã valid.

Lựa chọn này tốt hơn “chỉ sửa `_classify_shape`” vì nó hấp thụ phần đúng của report `260425-t9v` về `distr/daytype` mà không làm nhiễu semantics shape. Nó cũng tốt hơn “thay classifier hoàn toàn” vì giảm rủi ro phá detector compatibility và replay/backtest comparability.

## Requirements & Test Basis

Checklist làm nguồn cho implementation tương lai:

### Requirements

- [ ] Giữ `shape`, `shape_confidence_pct`, `shape_scores_pct` là visual-shape metadata; không đổi nghĩa sang distribution regime.
- [ ] Calibrate `_classify_shape` bằng fixture rõ ràng cho D/B/p/b và immature profile; confidence phải giảm khi evidence yếu hoặc dữ liệu non.
- [ ] Tính `distr = total_tpo_count / max_tpo_count` từ count distribution của profile; xử lý `max_tpo_count <= 0` bằng `UNKNOWN` hoặc absent safe value.
- [ ] Sinh `distribution_regime` từ `distr` bằng baseline lịch sử/rolling, ưu tiên quantile hoặc rolling mean/std đã kiểm chứng thay vì threshold tĩnh.
- [ ] Hỗ trợ regime `TREND`, `NORMAL`, `NEUTRAL`, `UNKNOWN`; thiếu baseline phải ra `UNKNOWN` và không ảnh hưởng score.
- [ ] Propagate `distribution_regime` qua TPO context theo timeframe, tách biệt với `shape`.
- [ ] Detector chỉ dùng regime như context modifier cho scoring/tagging sau khi setup đã valid theo price relation.
- [ ] Regime không tự emit buy/sell, không tạo valid setup khi thiếu VAL reclaim/VAH reject/breakout/acceptance/pullback confirmation.
- [ ] Regime không thay D1 bias, không đảo side long/short, không được hiểu `TREND` là direction.
- [ ] Replay/backtest phải có basis so sánh trước/sau về số lượng signal, score distribution, và false-positive candidates.

### Test Basis

- [ ] **Synthetic shape fixtures**: D cân xứng/compact quanh POC; B double distribution có hai peak và valley rõ; p upper-heavy; b lower-heavy; immature profile ít usable bins hoặc total thấp để xác nhận confidence cap.
- [ ] **Unit test `distr`**: kiểm tra `distr = total_tpo_count / max_tpo_count` với profile count bình thường, zero/empty count, single-bin count, và profile có nhiều max peak.
- [ ] **Baseline/rolling-history test**: fixture nhiều phiên để phân loại `TREND`, `NORMAL`, `NEUTRAL`, `UNKNOWN`; test thiếu history, stale history, và boundary quanh quantile/mean-std.
- [ ] **Context builder propagation test**: D1/H1/M30 context có `distribution_regime` độc lập với `shape`; missing/UNKNOWN không làm context builder hoặc detector crash.
- [ ] **Detector non-emission tests**: `TREND` không tự tạo setup khi thiếu price relation; `NEUTRAL` không tự tạo short; `NORMAL` không thay score khi setup invalid.
- [ ] **Detector modifier tests**: khi setup đã valid theo price relation, `TREND` chỉ boost trong cap cho continuation phù hợp; `NEUTRAL` chỉ discount/annotate và không đảo side; `UNKNOWN` no-op.
- [ ] **D1 bias protection tests**: `distribution_regime` không thay D1 bias và không override conflict với D1 bullish/bearish guard.
- [ ] **Replay/backtest regression basis**: chạy cùng dataset trước/sau, so sánh count signal theo setup/side/timeframe, score histogram, invalid reasons, và các case score tăng do regime.
- [ ] **Downstream compatibility tests**: indicator snapshot/Telegram/replay nếu thêm field mới phải không phá consumer hiện tại; missing field phải backward-compatible.
