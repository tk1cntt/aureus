# Báo cáo phân tích Trend Detection cho Aureus Signal Engine

## Phạm vi

- Đây là báo cáo phân tích, không implement và không tạo patch cho `services/aureus-signal/**`.
- Nguồn quan sát chính: `services/aureus-signal/engine/signals/trend.py`, `ema.py`, `pivots.py`, `structure.py`, `sweep.py`.
- Mọi khuyến nghị bên dưới là giả thuyết thiết kế cần POC/backtest sau này, không phải kết luận đã kiểm chứng bằng dữ liệu live.

## 1. Hiện trạng `TrendSignal`

`TrendSignal` trong `trend.py` có contract chính:

- `TrendSignal(BaseSignal)` với `__init__(ema_period: int = 200)`.
- `calculate(df, state_obj, **kwargs)` trả event tag `htf_trend`.
- State canonical: `state_obj.htf_trend`.
- Direction output: `BULLISH`, `BEARISH`, `NEUTRAL`.
- Regime data: `TREND_UP`, `TREND_DN`, `SIDEWAYS`.

Logic hiện tại:

1. Nếu `len(df) < ema_period`, set `state_obj.htf_trend = "NEUTRAL"` và không emit signal.
2. Lấy `ema_200` từ dataframe nếu có, nếu không thì tự tính EMA từ close.
3. Đếm unmitigated OB trong `state_obj.obs`:
   - `green_count`: OB `BULLISH` chưa `mitigated`.
   - `red_count`: OB `BEARISH` chưa `mitigated`.
4. Gate quyết định:
   - Nếu `green_count >= 2` và `red_count >= 2`: `SIDEWAYS` / `NEUTRAL`.
   - Nếu `(green_count - red_count) >= 2` và `current_price > current_ema`: `TREND_UP` / `BULLISH`.
   - Nếu `(red_count - green_count) >= 2` và `current_price < current_ema`: `TREND_DN` / `BEARISH`.
   - Còn lại: `SIDEWAYS` / `NEUTRAL`.

## 2. Vì sao EMA 200 gây delay

EMA 200 là filter macro chậm. Trong logic hiện tại, giá phải nằm đúng phía của EMA 200 mới được xác nhận trend. Điều này tạo lag ở ba lớp:

- Warmup lag: trước khi đủ 200 candle, `TrendSignal` luôn đưa `state_obj.htf_trend` về `NEUTRAL`.
- Smoothing lag: EMA 200 phản ứng chậm với đảo chiều/impulse mới, nên pivot/CHOCH có thể đã báo thay đổi cấu trúc nhưng `current_price > ema_200` hoặc `< ema_200` chưa đồng thuận.
- Gate lag kép: ngay cả khi OB delta đã nghiêng bullish/bearish, trend vẫn bị chặn nếu giá còn ở sai phía EMA 200.

Kết quả là trong giai đoạn đầu của trend mới, hoặc sau một displacement mạnh nhưng EMA 200 chưa kịp xoay, output dễ vẫn là `NEUTRAL`/`SIDEWAYS`.

## 3. Vì sao OB count gate dễ trả `NEUTRAL`/`SIDEWAYS`

Gate OB hiện tại dùng chênh lệch số lượng unmitigated OB tuyệt đối `>= 2`. Cách này dễ neutral vì:

- OB count không phân biệt recency: OB cũ và OB mới có trọng số như nhau.
- OB count không phân biệt quality: `quality`, `body_ratio`, trạng thái sweep/stop-hunt/clean-breakout không tham gia vào điểm trend.
- Nếu hai phía cùng có ít nhất 2 OB, logic ép `SIDEWAYS`/`NEUTRAL` dù market structure mới nhất có thể đã nghiêng một phía.
- Nếu delta chỉ là `1`, hoặc chỉ có một OB chất lượng cao, trend vẫn `NEUTRAL`.
- OB đã được tạo từ CHOCH/structure, nhưng TrendSignal chỉ dùng count nên mất thông tin hướng cấu trúc và timing breakout.

## 4. Inventory signal hiện có có thể tận dụng

### 4.1 EMA slope/cross từ `EMASignal`

`EMASignal` đã lưu `state_obj.emas[period] = {current, prev, slope}` và emit:

- `ema_{period}_up` / `ema_{period}_down` dựa trên close so với EMA.
- `cross` metadata: `ema_{period}_cross_up` / `ema_{period}_cross_down`.
- `slope`: độ dốc EMA hiện tại.

Tín hiệu này có thể dùng để thay EMA 200 đơn lẻ bằng EMA stack/slope nhanh hơn như EMA21/55, vẫn không cần dependency mới.

### 4.2 Pivot HH/HL/LL/LH từ `PivotSignal`

`PivotSignal` dùng ZigZagPro và chỉ emit pivot đã confirmed, non-repainting. State chính:

- `state_obj.swing_points`.
- Label pivot: `HH`, `LL`, `LH`, `HL`.
- Giữ metadata như `is_choch`, `ob`, `breakout_t`, `structure_label` nếu có.

Đây là nguồn tốt cho POC Shift/market structure vì phản ánh higher-high/higher-low hoặc lower-low/lower-high sau xác nhận.

### 4.3 CHOCH/OB từ `StructureSignal`

`StructureSignal` phát hiện CHOCH và tạo OB:

- Event `choch` với value `choch_up` hoặc `choch_down`.
- Tạo OB trong `state_obj.obs` với `ob_type`, `top`, `bottom`, `t_start`, `t_breakout`, `quality`, `body_ratio`, `status`.
- Export `transient_signals["ob_state"]` chứa active OB.

Đây là signal structural shift trực tiếp hơn OB count đơn thuần.

### 4.4 Sweep/stop-hunt/clean-breakout từ `SweepSignal`

`SweepSignal` cập nhật trạng thái OB:

- `TOUCHED`, `SWEEP`, `BROKEN_PENDING`, `STOP_HUNT`, `CLEAN_BREAKOUT`.
- Emit tag generic `sweep` với value như `sweep_bull`, `sweep_bear`, `stop_hunt_bull`, `stop_hunt_bear`, `clean_breakout_bull`, `clean_breakout_bear`.

Tín hiệu này hữu ích để phân biệt sweep/reclaim với breakout thật, giảm false flip nếu dùng làm confirmation thay vì trend source chính.

## 5. SWOT các phương án trend detection khả thi

### Phương án 1: POC Shift dựa trên pivot/market structure

Input hiện có:

- `state_obj.swing_points` từ `PivotSignal`.
- Label `HH`, `HL`, `LL`, `LH`.
- Metadata CHOCH nếu đã được `StructureSignal` gắn vào pivot.

SWOT:

- Strength: bám trực tiếp vào cấu trúc giá; có thể nhận trend sớm hơn EMA 200; dựa trên pivot confirmed nên non-repaint tốt hơn signal tick-level.
- Weakness: vẫn có lag do pivot phải được confirm; trong range dễ sinh chuỗi HH/LL nhiễu nếu amplitude chưa phù hợp.
- Opportunity: có thể định nghĩa POC Shift đơn giản như chuyển từ chuỗi `LH/LL` sang `HH/HL`, hoặc ngược lại; tận dụng dữ liệu đã có, không thêm dependency.
- Threat: false regime shift khi thị trường quét thanh khoản rồi quay đầu; cần confirmation bằng sweep/CHOCH hoặc EMA slope.

Đánh giá:

- Lag kỳ vọng: thấp-trung bình, nhanh hơn EMA 200 nhưng chậm hơn candle breakout raw vì chờ pivot confirm.
- Ổn định/non-repaint: tốt nếu chỉ dùng confirmed pivots.
- Timeframe phù hợp: M5/M15/H1 để giảm nhiễu; M1 cần filter bổ sung.

### Phương án 2: EMA stack/slope nhanh hơn EMA 200

Input hiện có:

- `state_obj.emas[period].current`, `prev`, `slope`.
- Tag `ema_{period}_up/down` và cross metadata từ `EMASignal`.
- Có thể dùng EMA21/55 hoặc EMA21/55/200 nếu các period đã được engine tính.

SWOT:

- Strength: dễ hiểu, dễ đo latency, ít phụ thuộc vào OB lifecycle; phản ứng nhanh hơn EMA 200 nếu dùng EMA21/55 + slope.
- Weakness: vẫn là indicator lagging; dễ bị whipsaw trong sideways; cross có thể flip nhiều ở M1.
- Opportunity: thay gate cứng `price vs EMA200` bằng score: EMA21 > EMA55, slope dương, giá trên EMA55.
- Threat: nếu bỏ structure confirmation, trend có thể bị false bullish/bearish trong pullback hoặc news spike.

Đánh giá:

- Lag kỳ vọng: thấp với EMA21/55; trung bình nếu vẫn giữ EMA200 làm filter phụ.
- Ổn định/non-repaint: tốt vì EMA không repaint trên candle close, nhưng có thể nhiễu nếu tính intrabar.
- Timeframe phù hợp: M1/M5 cho phản ứng nhanh; H1 làm filter macro.

### Phương án 3: CHOCH + OB regime

Input hiện có:

- Event `choch_up` / `choch_down` từ `StructureSignal`.
- `state_obj.obs` với `ob_type`, `quality`, `body_ratio`, `t_breakout`, `mitigated`, `status`.

SWOT:

- Strength: dùng đúng semantic market structure shift; OB được tạo kèm breakout context nên giàu thông tin hơn count delta.
- Weakness: CHOCH cần opposing extreme nên có thể không emit trong continuation trend; OB lifecycle phức tạp và phụ thuộc chất lượng pivot.
- Opportunity: trend regime có thể bám theo CHOCH gần nhất, weighted bởi OB quality/recency thay vì chỉ đếm số OB.
- Threat: CHOCH đơn lẻ có thể là liquidity grab; nếu set trend ngay có thể tăng false flip.

Đánh giá:

- Lag kỳ vọng: trung bình, thường nhanh hơn EMA 200 ở đảo chiều cấu trúc rõ.
- Ổn định/non-repaint: khá tốt vì dựa trên pivot/CHOCH confirmed, nhưng cần quy tắc chống flip liên tục.
- Timeframe phù hợp: M5/M15/H1; M1 nên dùng làm event confirmation thay vì regime duy nhất.

### Phương án 4: Sweep/stop-hunt confirmation

Input hiện có:

- `sweep` event value: `sweep_bull`, `sweep_bear`, `stop_hunt_bull`, `stop_hunt_bear`, `clean_breakout_bull`, `clean_breakout_bear`.
- OB status transition trong `state_obj.obs`.

SWOT:

- Strength: phân biệt false break/reclaim với clean breakout; hữu ích để giảm sai trend sau cú quét thanh khoản.
- Weakness: không phải trend source độc lập; phụ thuộc OB đã tồn tại; có thể sparse signal.
- Opportunity: dùng làm confirmation cho POC Shift/CHOCH, ví dụ chỉ nâng confidence khi có `clean_breakout_*` hoặc tránh flip khi chỉ là `stop_hunt_*`.
- Threat: nếu dùng sweep làm gate bắt buộc, trend detection có thể quá ít tín hiệu và quay lại tình trạng `NEUTRAL` nhiều.

Đánh giá:

- Lag kỳ vọng: thấp khi OB state đã có; nhưng sparse nên không luôn có signal.
- Ổn định/non-repaint: tốt ở event đã đóng candle, nhưng cần chống duplicate/history mismatch.
- Timeframe phù hợp: M1/M5 cho micro confirmation; M15/H1 làm context phụ.

### Phương án 5: Hybrid scoring/voting giữa structure + EMA + OB/sweep

Input hiện có:

- Pivot structure: `HH/HL/LL/LH` từ `state_obj.swing_points`.
- EMA stack/slope/cross từ `state_obj.emas`.
- CHOCH/OB từ `StructureSignal` và `state_obj.obs`.
- Sweep/stop-hunt/clean-breakout từ `SweepSignal`.

SWOT:

- Strength: giảm phụ thuộc vào một gate cứng; có thể cho trend sớm khi nhiều nguồn đồng thuận; fallback về `NEUTRAL` khi score yếu thay vì chỉ vì thiếu OB delta `>= 2`.
- Weakness: cần thiết kế trọng số và hysteresis cẩn thận; dễ overfit nếu thêm quá nhiều rule.
- Opportunity: giữ compatibility với `state_obj.htf_trend` bằng cách output vẫn là `BULLISH/BEARISH/NEUTRAL`, nhưng data có thêm score/confidence trong POC tương lai.
- Threat: nếu không backtest, scoring có thể tạo cảm giác chính xác giả; cần đo false flip rate và latency rõ ràng.

Đánh giá:

- Lag kỳ vọng: thấp-trung bình; có thể nhanh hơn EMA 200 nhưng vẫn có filter ổn định.
- Ổn định/non-repaint: tốt nếu chỉ dùng candle-close, confirmed pivots và hysteresis.
- Timeframe phù hợp: M5/M15 làm trend regime chính; M1 dùng execution confirmation; H1 làm macro bias.

## 6. So sánh nhanh

| Phương án | Lag so với EMA 200 | Ổn định/non-repaint | Rủi ro false signal | Phù hợp nhất |
|---|---:|---|---|---|
| POC Shift pivot/structure | Nhanh hơn | Tốt nếu confirmed pivot | Trung bình trong range | M5/M15/H1 |
| EMA stack/slope EMA21/55 | Nhanh hơn nhiều | Tốt trên candle close | Cao trong sideways | M1/M5/M15 |
| CHOCH + OB regime | Nhanh hơn | Khá tốt | Trung bình nếu CHOCH giả | M5/M15/H1 |
| Sweep/stop-hunt confirmation | Nhanh khi có OB | Tốt | Thấp hơn nếu dùng làm confirmation | M1/M5 |
| Hybrid scoring/voting | Nhanh hơn có kiểm soát | Tốt nếu có hysteresis | Thấp-trung bình | M5/M15 chính, H1 filter |

## 7. Recommendation / Khuyến nghị POC

### Nên POC trước: Hybrid scoring/voting nhẹ

Khuyến nghị POC đầu tiên là hybrid scoring tối giản, không phải implement ngay trong quick task này. Lý do:

- Giải quyết nguyên nhân chính: EMA 200 quá chậm và OB count quá cứng.
- Tận dụng signal hiện có, không cần dependency mới.
- Có thể giữ output contract `state_obj.htf_trend` với `BULLISH`/`BEARISH`/`NEUTRAL`.
- Cho phép POC so sánh từng nguồn đóng góp thay vì thay toàn bộ logic bằng một signal mới chưa kiểm chứng.

Một hướng scoring để POC sau này có thể đánh giá, không implement tại đây:

- Structure score: pivot sequence/POC Shift và CHOCH gần nhất.
- EMA score: EMA21/55 alignment + slope, EMA200 chỉ làm macro penalty/filter mềm.
- OB score: recency/quality/status thay vì count delta thô.
- Sweep score: confirmation hoặc anti-false-break, không bắt buộc luôn có.
- Hysteresis: cần ngưỡng vào/ra khác nhau để giảm false flip.

### Backup: POC Shift dựa trên pivot/market structure

Nếu muốn đơn giản hơn hybrid, chọn POC Shift làm backup:

- Ít rule hơn scoring.
- Bám sát market structure.
- Có non-repaint behavior nhờ confirmed pivots.
- Nhược điểm là vẫn cần filter range/sweep để tránh flip sai.

### Không nên chọn ngay: thay bằng EMA stack đơn thuần

Không nên chỉ thay EMA 200 bằng EMA21/55 đơn thuần như giải pháp cuối cùng:

- Có thể giảm latency nhưng tăng whipsaw.
- Không tận dụng được CHOCH/OB/sweep vốn là logic domain của engine.
- Vẫn không giải quyết triệt để vấn đề sideways/range nếu không có structure filter.

## 8. Tiêu chí đánh giá POC sau này

Khi user chọn hướng POC, nên đo tối thiểu:

1. Detection latency so với EMA 200: số candle từ CHOCH/pivot shift đến khi `htf_trend` đổi.
2. Tỷ lệ giảm `NEUTRAL` sai: các đoạn có trend rõ nhưng logic cũ vẫn `NEUTRAL`/`SIDEWAYS`.
3. False flip rate: số lần `BULLISH` ↔ `BEARISH` đảo chiều rồi quay lại trong N candle.
4. Non-repaint behavior: chỉ dùng confirmed pivot/candle-close event, không dùng tentative pivot.
5. Compatibility: vẫn set được `state_obj.htf_trend` và emit tag `htf_trend` để downstream không vỡ contract.
6. Explainability: data output nên giải thích được score đến từ structure/EMA/OB/sweep nào.

## 9. Kết luận

Logic hiện tại neutral nhiều vì dùng hai gate cứng: EMA 200 chậm và OB count delta `>= 2`. Hướng POC hợp lý nhất là hybrid scoring nhẹ, trong đó structure/pivot và CHOCH đóng vai trò trend source chính, EMA stack/slope là filter momentum, OB/sweep là confirmation/risk control. Báo cáo này chỉ phân tích và khuyến nghị; không implement, không sửa source code.
