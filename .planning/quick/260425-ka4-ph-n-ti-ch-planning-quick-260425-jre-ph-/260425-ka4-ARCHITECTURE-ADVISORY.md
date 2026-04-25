# Architecture Advisory: Trend Detection cho Aureus Signal Engine

## Phạm vi và giả định

Báo cáo này phân tích độc lập dựa trên `260425-jre-REPORT.md`. Đây là tư vấn kiến trúc cho POC tương lai, không phải kết luận đã kiểm chứng bằng live-data/backtest và không implement code.

Mục tiêu chính: giảm tình trạng `NEUTRAL` sai do EMA200/OB-count gate quá cứng, nhưng vẫn giữ ổn định, không repaint, không thêm dependency mới và không phá contract `state_obj.htf_trend` / event tag `htf_trend`.

## 1. Neutral Listing

Các lựa chọn khả thi từ report gốc, được liệt kê trung lập:

1. **Hybrid scoring/voting**
   - Kết hợp structure/CHOCH, EMA stack/slope, OB quality/recency/status và sweep/stop-hunt confirmation.
   - Output cuối vẫn là `BULLISH`, `BEARISH`, `NEUTRAL` qua `state_obj.htf_trend` và tag `htf_trend`.

2. **POC Shift pivot/structure**
   - Dùng chuỗi pivot confirmed như `HH/HL` hoặc `LH/LL` để xác định shift cấu trúc.
   - Có thể xem là trend source đơn giản hơn hybrid.

3. **CHOCH + OB regime**
   - Dùng `choch_up` / `choch_down` và OB được tạo bởi structure signal để xác định regime.
   - OB nên được weighted theo recency, quality, body ratio, status thay vì count thô.

4. **EMA stack/slope**
   - Thay gate EMA200 cứng bằng EMA21/55 alignment, slope và close-vs-EMA nhanh hơn.
   - EMA200 chỉ nên là macro context hoặc penalty mềm.

5. **Sweep/stop-hunt confirmation**
   - Dùng `sweep`, `stop_hunt`, `clean_breakout` để xác nhận hoặc chống false break.
   - Không nên là trend source độc lập vì tín hiệu sparse và phụ thuộc OB lifecycle.

## 2. Attribute Mapping

| Lựa chọn | Latency | Non-repaint / stability | False-flip risk | Dependency mới | Compatibility `state_obj.htf_trend` / `htf_trend` | Explainability | Testability / backtestability | Implementation complexity |
|---|---|---|---|---|---|---|---|---|
| Hybrid scoring/voting | Thấp-trung bình; nhanh hơn EMA200 nhưng vẫn có filter | Tốt nếu chỉ dùng candle-close, confirmed pivots và hysteresis | Thấp-trung bình nếu có threshold vào/ra khác nhau; cao nếu quá nhiều rule overfit | Không cần | Tốt; scoring nội bộ map về output hiện tại | Cao nếu log từng contribution: structure, EMA, OB, sweep | Cao; đo được latency, false flip, NEUTRAL reduction theo từng factor | Trung bình; cần thiết kế weight tối giản và kill criteria |
| POC Shift pivot/structure | Trung bình; chờ pivot confirm nhưng nhanh hơn EMA200 | Tốt nếu chỉ dùng confirmed pivots | Trung bình trong range hoặc liquidity sweep | Không cần | Tốt; shift map trực tiếp sang BULLISH/BEARISH/NEUTRAL | Cao; lý do dựa trên HH/HL/LH/LL dễ giải thích | Cao; replay pivot sequence được | Thấp-trung bình |
| CHOCH + OB regime | Trung bình; nhanh khi có CHOCH rõ, chậm trong continuation | Khá tốt nếu CHOCH confirmed; phụ thuộc OB lifecycle | Trung bình nếu CHOCH đơn lẻ là liquidity grab | Không cần | Tốt; regime map được về contract hiện tại | Khá cao nếu nêu CHOCH gần nhất + OB quality/recency | Khá cao; cần fixture OB lifecycle/status | Trung bình |
| EMA stack/slope | Thấp với EMA21/55 | Tốt trên candle-close; vẫn whipsaw trong sideways | Cao nếu dùng đơn thuần, nhất là M1/M5 range | Không cần | Rất tốt; thay gate nội bộ dễ giữ output | Cao; dễ giải thích bằng alignment/slope | Rất cao; metric đơn giản | Thấp |
| Sweep/stop-hunt confirmation | Thấp khi signal xuất hiện nhưng sparse | Tốt nếu event đã đóng candle | Thấp khi dùng làm confirmation; cao nếu dùng như gate bắt buộc gây thiếu tín hiệu | Không cần | Tốt nếu chỉ là modifier/confidence | Trung bình-cao; cần giải thích theo OB status | Trung bình; cần dataset có sweep/stop-hunt | Thấp-trung bình |

## 3. Contextual Recommendation

**Primary recommendation:** chọn **Hybrid scoring/voting nhẹ**, trong đó:

- **Structure/CHOCH là trend source chính**: pivot shift `HH/HL` hoặc `LH/LL`, cộng CHOCH gần nhất, quyết định hướng nền.
- **EMA21/55 slope/alignment là momentum filter**: xác nhận động lượng hiện tại, tránh dùng EMA200 làm gate cứng.
- **OB recency/quality/status là confidence**: OB mới, quality tốt, status phù hợp tăng độ tin cậy; không dùng count delta thô làm điều kiện duy nhất.
- **Sweep/stop-hunt là confirmation/anti-false-break**: `clean_breakout_*` có thể tăng confidence; `stop_hunt_*` hoặc sweep ngược hướng nên giảm confidence hoặc trì hoãn flip.
- **EMA200 chỉ là macro penalty/filter mềm**: nếu hướng hybrid ngược EMA200 thì giảm điểm hoặc yêu cầu thêm confirmation, không ép về `NEUTRAL` ngay.

Lý do lựa chọn này phù hợp nhất cho Aureus Signal Engine:

1. Không thêm dependency mới; tận dụng signal đã có trong engine.
2. Giữ contract downstream hiện tại: `state_obj.htf_trend` và event tag `htf_trend`.
3. Giải quyết đúng hai nguyên nhân trong report gốc: EMA200 delay và OB count gate quá cứng.
4. Có khả năng giảm `NEUTRAL` sai mà không biến EMA21/55 thành nguồn whipsaw đơn thuần.
5. Explainability và testability tốt nếu POC log score contribution theo từng nguồn.

**Backup:** nếu muốn giảm complexity hoặc cần POC nhanh hơn, chọn **POC Shift pivot/structure** làm hướng backup. POC Shift đơn giản hơn hybrid, vẫn bám market structure và non-repaint nếu chỉ dùng confirmed pivots, nhưng cần filter range/sweep để tránh false regime shift.

**Không nên chọn làm giải pháp chính:** thay TrendSignal bằng EMA stack/slope đơn thuần. Cách này giảm latency nhanh nhất nhưng dễ tăng whipsaw và bỏ phí semantic CHOCH/OB/sweep vốn là domain signal của engine.

## 4. Adversarial Mode

### Failure modes của recommendation hybrid

1. **Overfit scoring**
   - Nếu weight quá nhiều rule nhỏ, POC có thể fit tốt trên vài case nhưng không ổn định trên market khác.
   - Guardrail: bắt đầu với số factor tối thiểu; mỗi factor phải có metric trước/sau.

2. **False confidence từ signal đồng nguồn**
   - Pivot, CHOCH và OB không hoàn toàn độc lập; nếu cộng điểm như nguồn độc lập có thể double-count cùng một cấu trúc.
   - Guardrail: nhóm structure/CHOCH/OB thành cụm liên quan, tránh cho chúng áp đảo hoàn toàn EMA/sweep.

3. **Whipsaw trong range**
   - EMA21/55 và pivot shift có thể flip liên tục khi thị trường đi ngang.
   - Guardrail: hysteresis, minimum hold candles, threshold vào/ra khác nhau, và range/sideways fallback khi score yếu.

4. **Repaint hoặc lookahead do dùng pivot chưa confirm**
   - Nếu POC lấy tentative pivot hoặc intrabar signal, backtest sẽ đẹp giả.
   - Guardrail: chỉ dùng candle-close, confirmed pivots, CHOCH/OB đã được xác nhận theo trạng thái engine.

5. **Phá compatibility downstream**
   - Nếu output thêm format mới hoặc thay semantic `htf_trend`, các consumer Telegram/strategy/journal có thể lệch kỳ vọng.
   - Guardrail: output canonical vẫn là `BULLISH`, `BEARISH`, `NEUTRAL`; score/confidence nếu có chỉ là metadata phụ.

### Khi nào không nên chọn hybrid

- Khi mục tiêu trước mắt là patch cực nhỏ, cần ít rule nhất để kiểm tra giả thuyết structure shift.
- Khi chưa có harness backtest/replay đủ để đo false flip và latency.
- Khi dữ liệu OB/sweep hiện tại thiếu nhất quán hoặc sparse đến mức scoring không giải thích được.

Trong các trường hợp trên, chọn backup **POC Shift pivot/structure** trước, rồi chỉ thêm EMA/sweep filter sau khi metric chứng minh cần thiết.

### Success criteria cho POC

- Detection latency giảm so với baseline EMA200, tính bằng số candle từ CHOCH/pivot shift đến khi `htf_trend` đổi.
- Tỷ lệ `NEUTRAL` sai giảm trên các đoạn trend rõ.
- False flip rate không tăng quá mức so với baseline.
- Downstream compatibility giữ nguyên: `state_obj.htf_trend` và tag `htf_trend` vẫn hoạt động.
- Explainability đạt mức có thể đọc được: mỗi decision có lý do từ structure, EMA, OB hoặc sweep.

### Kill criteria cho POC

- Hybrid scoring phức tạp hơn POC Shift nhưng không cải thiện rõ latency/NEUTRAL reduction.
- False flip rate tăng đáng kể trong sideways hoặc news spike.
- Cần thêm dependency hoặc thay đổi contract output hiện tại.
- Không thể giải thích trend decision bằng contribution cụ thể.

## Kết luận

Lựa chọn tốt nhất là **Hybrid scoring/voting nhẹ với structure/CHOCH là trend source chính, EMA21/55 slope/alignment là momentum filter, OB recency/quality/status là confidence, sweep/stop-hunt là confirmation/anti-false-break, và EMA200 chỉ là macro penalty/filter mềm**. Backup hợp lý là **POC Shift pivot/structure** nếu muốn giảm complexity cho vòng POC đầu tiên.
