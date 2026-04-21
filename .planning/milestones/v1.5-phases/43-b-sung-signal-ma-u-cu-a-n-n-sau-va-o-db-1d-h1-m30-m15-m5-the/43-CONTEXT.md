# Phase 43: b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Bổ sung dữ liệu indicator signal vào DB theo từng nến M1, gồm 2 nhóm:
1) màu nến đa khung thời gian (1D, H1, M30, M15, M5) gắn theo mỗi nến M1
2) Bollinger Bands đa khung thời gian (H1, M30, M15, M5, M1) gắn theo mỗi nến M1

Phase này chỉ mở rộng payload/snapshot + schema lưu trữ liên quan indicator; không thêm capability mới về trigger strategy hoặc notification logic.

</domain>

<decisions>
## Implementation Decisions

### Màu nến đa khung thời gian
- **D-01:** Màu nến cho mỗi TF được xác định theo quy tắc thống nhất từ OHLC của nến TF đó:
  - `BULLISH` nếu `close > open`
  - `BEARISH` nếu `close < open`
  - `DOJI` nếu `close == open` (sau khi normalize theo digits của symbol)
- **D-02:** Lưu key rõ ràng theo TF trong snapshot: `candle_color_d1`, `candle_color_h1`, `candle_color_m30`, `candle_color_m15`, `candle_color_m5`.
- **D-03:** Giá trị màu nến phải uppercase để đồng nhất với các enum/status đã có trong hệ thống.

### Bollinger Bands đa khung thời gian
- **D-04:** BB cho mỗi TF lưu đủ 3 line chuẩn: `upper`, `middle`, `lower` (không chỉ status rút gọn), để downstream dùng linh hoạt cho dashboard/analytics.
- **D-05:** TF bắt buộc cho BB: `M1`, `M5`, `M15`, `M30`, `H1`.
- **D-06:** Cấu trúc đề xuất theo namespace `bb_<tf>` để dễ parse và tránh vỡ contract cũ, ví dụ:
  - `bb_m1: {upper, middle, lower}`
  - `bb_m5: {upper, middle, lower}`
  - ...

### Đồng bộ theo từng nến M1
- **D-07:** Mỗi khi chốt nến M1, ghi 1 snapshot DB; snapshot này chứa giá trị mới nhất khả dụng của tất cả TF yêu cầu.
- **D-08:** Với TF lớn hơn M1 (M5/M15/M30/H1/D1), dùng **last closed candle** tại thời điểm M1 đó (không dùng nến đang hình thành) để đảm bảo tính ổn định/replay được.
- **D-09:** Không chờ TF lớn đóng nến mới ghi DB; vẫn ghi mỗi M1 để giữ chuỗi dữ liệu liên tục cho phân tích theo trục thời gian M1.

### Quy ước lưu DB (naming/null/fallback)
- **D-10:** Nếu tại thời điểm M1 chưa đủ dữ liệu để tính màu nến/BB ở TF nào, lưu `null` cho TF đó (không dùng giá trị giả như 0 hay string placeholder).
- **D-11:** Không backfill nội suy trong phase này; planner có thể chọn xử lý data quality downstream nếu cần.
- **D-12:** Giữ compatibility: trường mới được bổ sung theo kiểu additive, không đổi nghĩa các field indicator đã có (`emas`, `atr_14`, `vol_sma_20`, `htf_trend`, `cisd_mtf`).

### Claude's Discretion
- Chi tiết vị trí code cụ thể để inject snapshot (module hiện có hay helper mới nhỏ)
- Cách tổ chức migration DB (JSONB-only hoặc cột tách) miễn đáp ứng naming đã chốt
- Mức log chi tiết cho trường hợp null ở TF lớn

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Signal snapshot pipeline
- `services/aureus-signal/engine/indicator_snapshot.py` — helper snapshot hiện tại, điểm mở rộng hợp lý cho candle color + BB MTF
- `services/aureus-signal/engine/live_engine.py` — pipeline xử lý theo candle, điểm attach snapshot theo nhịp M1
- `services/aureus-signal/engine/signals/resampler.py` — chuẩn resample M1 → TF lớn, định nghĩa completed vs forming candle
- `services/aureus-signal/engine/state.py` — cấu trúc state/transient_signals và normalize history

### Persistence / DB writer
- `services/aureus-db-writer/main.py` — parse payload stream và ghi DB, cần đảm bảo field indicator mới được persist đúng contract

### Upstream decisions
- `.planning/phases/40-signal-classification-indicator-event-based/40-CONTEXT.md` — nền tảng indicator snapshot trước đó
- `.planning/phases/41-b-sl-pivot-point/41-CONTEXT.md` — conventions signal/state liên quan phase liền trước
- `.planning/phases/42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry/42-CONTEXT.md` — conventions payload propagation xuyên layer gần nhất

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_indicator_snapshot_for_telegram()` trong `indicator_snapshot.py` đã có pattern gom indicator values theo cấu trúc nhẹ, phù hợp để mở rộng thêm candle color + BB MTF.
- `resample_to_tf()` trong `signals/resampler.py` đã hỗ trợ M1, M5, M15, M30, H1, D1 với rule rõ ràng về nến forming/completed.

### Established Patterns
- Pipeline hiện tại xử lý theo nhịp nến và attach snapshot vào payload theo kiểu additive (không phá hợp đồng cũ).
- Nhiều status/value trong hệ thống đã theo convention uppercase; lựa chọn này đồng nhất với dữ liệu hiện hành.

### Integration Points
- Signal engine: tính thêm indicator values theo từng M1 trước khi publish.
- DB writer: đảm bảo parse/persist các key indicator mới vào record snapshot mà không làm hỏng event cũ.

</code_context>

<specifics>
## Specific Ideas

- Ưu tiên thiết kế payload dễ đọc khi debug nhanh: nhóm theo namespace `candle_color_*` và `bb_<tf>`.
- Chọn `last closed` cho TF lớn để tránh jitter dữ liệu khi replay/backtest đối chiếu.
- Null-first policy giúp phân biệt rõ “chưa có dữ liệu” với “dữ liệu hợp lệ bằng 0”.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `Investigate missing OB events in signal_history_normalized` — deferred vì ngoài scope phase 43 (liên quan event history integrity, không phải bổ sung indicator fields)
- `Remove market_regime use htf_trend` — deferred vì là thay đổi logic signal classification/regime, không phải mở rộng dữ liệu indicator đa TF theo yêu cầu hiện tại

</deferred>

---

*Phase: 43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the*
*Context gathered: 2026-04-16*