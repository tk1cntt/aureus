# Yêu cầu thực thi và kiểm thử: cải thiện `_classify_shape` / TPO shape

Nguồn trace:

- Report nguồn: `.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md`
- Advisory: `.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md`

Tài liệu này là cơ sở cho future implementation/testing. Phạm vi quick task hiện tại không sửa production code, tests, migration, database schema hoặc runtime config.

## Decision Summary

Quyết định kiến trúc cuối cùng: cải thiện `_classify_shape` theo hướng **calibrated deterministic heuristic + maturity/data-quality gate**, sau đó dùng **TPO detector context và offline replay/backtest calibration** làm lớp xác nhận trước khi shape được dùng cho strategy scoring.

Ý nghĩa quyết định:

- Shape vẫn là deterministic/explainable geometry layer cho TPO profile.
- `shape_confidence_pct` chưa được coi là xác suất thật khi chưa có calibration evidence.
- Maturity/data-quality phải ngăn sparse/current bucket tạo confidence gây hiểu nhầm.
- Detector context là confirmation layer, không thay thế shape classifier.
- Replay/backtest là điều kiện bắt buộc trước khi shape ảnh hưởng scoring.

## In Scope

Các yêu cầu nên thực hiện khi có task implement sau này:

### REQ-LQO-01: Calibrated heuristic metrics

Future implementation phải định nghĩa rõ các metric hình học thay cho hoặc bổ sung score hiện tại:

- Symmetry quanh POC cho D-shape.
- Compactness hoặc VA width quality cho balanced profile.
- Upper/lower excess area cho p/b.
- Skew chỉ là một thành phần, không được là bằng chứng duy nhất.

### REQ-LQO-02: Peak separation + valley depth cho B-shape

B-shape chỉ nên có confidence cao khi có đủ bằng chứng double distribution:

- Có hai peak có prominence đáng kể.
- Hai peak có khoảng cách tối thiểu theo bin/price.
- Valley giữa hai peak đủ sâu so với peak chính/phụ.
- Balanced-but-lumpy profile không được tự động bị B hóa chỉ vì có local maxima sát nhau.

### REQ-LQO-03: Maturity/data-quality gate

Future classifier phải tính hoặc nhận data-quality/maturity context:

- Minimum candle count hoặc elapsed minutes cho current H1/M30 bucket.
- Minimum total TPO count và minimum usable bins.
- Sparse/empty profile phải trả confidence thấp, capped confidence, hoặc state an toàn nếu future contract cho phép.
- Current bucket và closed bucket phải được phân biệt trong logic confidence.

### REQ-LQO-04: Confidence margin top-1/top-2

`shape_confidence_pct` phải phản ánh mức tách biệt giữa lựa chọn thắng và runner-up:

- Top-1/top-2 margin thấp thì confidence không được cao.
- Data-quality thấp thì confidence phải bị cap dù normalized score cao.
- Tài liệu/test phải ghi rõ confidence là heuristic confidence, không phải xác suất thống kê nếu chưa calibrate.

### REQ-LQO-05: Outlier/tick_size robustness

Future implementation phải kiểm soát các nguồn nhiễu đã nêu trong report:

- Wick/outlier không được dễ dàng kéo méo toàn bộ shape.
- Tick size/binning sensitivity phải có test boundary.
- Equal peaks, flat profile và long-tail profile phải có hành vi ổn định.

### REQ-LQO-06: Detector context như confirmation layer

Khi liên kết shape với TPO detectors:

- Shape là backdrop geometry.
- Detector context như VA rejection, breakout acceptance, POC/VA shift chỉ xác nhận narrative vận hành.
- Không dùng detector để che lỗi classifier; test phải cover trường hợp shape high confidence nhưng detector không xác nhận.

### REQ-LQO-07: Replay/backtest validation trước scoring

Trước khi shape ảnh hưởng strategy scoring:

- Phải chạy replay để đo flip rate theo D1/H1/M30.
- Phải đo confidence distribution theo timeframe/symbol/session.
- Phải có A/B backtest nếu shape được thêm vào scoring/tagging logic.
- Phải đánh giá per-strategy outcome, không chỉ aggregate.

### REQ-LQO-08: Telegram/indicator snapshot compatibility

Future implementation không được làm mất contract hiện tại của indicator snapshot/Telegram nếu chưa có migration:

- TPO block vẫn cần POC/VAH/VAL/shape/shape_confidence_pct/shape_scores_pct hoặc migration rõ ràng.
- Nếu thêm state như `forming`/`insufficient_data`, notifier phải render an toàn.
- Telegram không được diễn đạt confidence như xác suất thắng/thua khi chưa calibrate.

## Out of Scope / Do Not Do

- Không dùng ML ngay trong bước cải thiện đầu tiên.
- Không coi `shape_confidence_pct` là xác suất thật khi chưa có calibration bằng replay/labeled evidence.
- Không đưa shape vào strategy scoring trước khi có replay/backtest validation.
- Không chỉ chỉnh threshold hiện tại như `0.35/0.45` mà không thêm metric, test và calibration basis.
- Không đổi D1 session semantic từ UTC day sang broker day/market session nếu chưa có quyết định kiến trúc riêng.
- Không mở rộng DB/persistence contract cho TPO shape nếu chưa trace riêng qua journal/schema/signal snapshot path.
- Không thêm production behavior dựa trên assumption chưa có trong `260425-kwd-REPORT.md` hoặc advisory.

## Acceptance Criteria

Future implementation được coi là đạt khi thỏa các tiêu chí sau:

- [ ] Có metric definition rõ cho D/B/p/b, không chỉ dựa vào normalized score cũ.
- [ ] B-shape có kiểm tra peak separation và valley depth.
- [ ] Sparse/empty/current bucket không tạo high confidence gây hiểu nhầm.
- [ ] Confidence có xét top-1/top-2 margin và data-quality/maturity.
- [ ] Unit tests có fixture đại diện D, B, p, b.
- [ ] Edge tests bao phủ sparse, empty/zero counts, outlier/wick, tick_size sensitivity, equal peaks, flat profile.
- [ ] Integration tests xác nhận indicator snapshot và Telegram render không bị phá contract.
- [ ] Replay validation báo cáo ít nhất flip rate và confidence distribution.
- [ ] Nếu shape đi vào scoring, có A/B backtest và per-strategy outcome review.
- [ ] Tài liệu release/summary ghi rõ `shape_confidence_pct` là heuristic confidence nếu chưa có calibration xác suất.

## Test Basis

### Unit fixture tests

- D-shape: single balanced/bell-like distribution quanh POC, symmetry cao, không có dual peak rõ.
- B-shape: hai peak tách biệt, valley rõ, skew không quá lệch.
- p-shape: profile upper-heavy hoặc có lower tail/excess pattern theo metric đã định nghĩa.
- b-shape: profile lower-heavy hoặc có upper tail/excess pattern theo metric đã định nghĩa.

### Edge-case tests

- Empty counts hoặc total count bằng 0.
- Sparse 2-5 candles/current bucket đầu kỳ.
- Long wick/outlier kéo range rộng.
- Very small/large tick_size tạo binning khác nhau.
- Equal peaks và flat profile.
- Profile gần threshold để kiểm tra flip/boundary behavior.

### Integration tests

- `TPOSignal.calculate` vẫn trả TPO blocks hợp lệ cho `tpo_d1`, `tpo_h1`, `tpo_m30`.
- `build_indicator_snapshot_for_telegram` vẫn đưa TPO profile vào indicator snapshot.
- Telegram formatter render Shape an toàn khi confidence thấp hoặc nếu future contract thêm `forming`/`insufficient_data`.
- Strategy context không được tự động coi shape là scoring input nếu chưa có requirement scoring riêng.

### Replay/backtest tests

- Replay H1/M30 current bucket để đo shape flip rate theo elapsed minutes.
- Replay D1/H1/M30 để đo confidence distribution theo timeframe và session.
- So sánh before/after trên cùng historical M1 OHLCV.
- Nếu dùng shape cho scoring, chạy A/B backtest baseline no-shape vs shape-enabled vs detector-confirmed shape.
- Báo cáo per-strategy false positives, không chỉ tổng PnL hoặc aggregate win rate.

## Traceability

| Requirement | Nguồn từ `260425-kwd-REPORT.md` | Nguồn từ `260425-lqo-ARCHITECTURE-ADVISORY.md` | Test basis |
|---|---|---|---|
| REQ-LQO-01 Calibrated heuristic metrics | Weakness: confidence chưa calibrate, threshold brittle; Approach 1 | Suggested best choice: metric rõ cho D/B/p/b | Unit fixture D/B/p/b, boundary tests |
| REQ-LQO-02 Peak separation + valley depth | Weakness: dual peak không kiểm tra separation/valley | Bước 3 và guardrail B-shape | B-shape separated peaks, balanced-but-lumpy negative case |
| REQ-LQO-03 Maturity/data-quality gate | Weakness: sparse/incomplete current sessions | Suggested best choice: maturity/data-quality gate | Sparse/current bucket tests, flip-rate replay |
| REQ-LQO-04 Confidence margin top-1/top-2 | Weakness: confidence là normalized heuristic score | Bước 2 trade-off và Bước 3 confidence margin | Confidence margin boundary tests |
| REQ-LQO-05 Outlier/tick_size robustness | Weakness: tick_size/binning và outlier/wick sensitivity | Guardrail metric/test/replay | Outlier/wick và tick_size tests |
| REQ-LQO-06 Detector context confirmation | Approach 3 rule-based hybrid với TPO detector outputs | Bước 3 detector context là confirmation layer | Integration detector context tests |
| REQ-LQO-07 Replay/backtest trước scoring | Approach 4 và Recommendation | Suggested best choice: replay/backtest trước scoring | Replay metrics, A/B backtest |
| REQ-LQO-08 Telegram/indicator compatibility | Role in TPO System: indicator snapshot và Telegram SIGNAL ALERT | Explainability và guardrail Telegram | Integration snapshot/Telegram tests |

## Ghi chú triển khai sau này

- Nếu future implementation sửa database hoặc persistence path, phải test e2e với database theo CLAUDE.md.
- Nếu sửa symbol production như `_classify_shape`, cần chạy GitNexus impact analysis trước khi sửa và `gitnexus_detect_changes()` trước khi commit.
- Nếu GitNexus index stale, cần chạy `npx gitnexus analyze` trước khi dựa vào impact graph.
