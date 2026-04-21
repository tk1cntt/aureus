---
phase: "43"
phase_slug: "b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the"
date: "2026-04-16"
source: "43-RESEARCH.md"
status: "active"
---

# Phase 43 Validation Strategy

## Validation Architecture

### Goal-Backward Validation
- Verify mỗi snapshot M1 có đủ trường mới theo scope phase: candle color đa TF + BB đa TF.
- Verify semantics: TF lớn dùng last-closed candle, không dùng forming candle.
- Verify additive contract: field cũ không đổi nghĩa; field mới null khi thiếu data.

### Required Validation Dimensions
1. **Schema alignment**
   - `aureus_signal_snapshots` phải có cột/field lưu được:
     - `candle_color_d1`, `candle_color_h1`, `candle_color_m30`, `candle_color_m15`, `candle_color_m5`
     - `bb_m1`, `bb_m5`, `bb_m15`, `bb_m30`, `bb_h1`
   - Cả `insert_single_snapshot` và `batch_insert_snapshots` phải ghi đủ field mới.

2. **Runtime correctness**
   - Mỗi nến M1 ghi 1 snapshot với payload field mới.
   - Với TF > M1, dữ liệu lấy từ last closed candle tại thời điểm M1.

3. **Null policy**
   - Thiếu dữ liệu TF nào -> `null` đúng field tương ứng.
   - Không dùng sentinel giả (`0`, `UNKNOWN`) cho field numeric/object BB.

4. **Backward compatibility**
   - Các field hiện có (`emas`, `atr_14`, `vol_sma_20`, `htf_trend`, `cisd_mtf`) vẫn hoạt động.
   - Không ảnh hưởng flow trigger event / notifier.

### Test Strategy
- Unit tests cho helper tính candle color theo OHLC và rule BULLISH/BEARISH/DOJI.
- Unit tests cho BB snapshot theo từng TF (M1/M5/M15/M30/H1) + null cases.
- Integration test pipeline M1 -> snapshot -> DB writer (single + batch path).
- Migration/schema test: chạy migration và xác nhận schema có field mới.

### Acceptance Signals
- Test suite pass cho module thay đổi.
- Log runtime có snapshot payload mới theo M1 cadence.
- Query DB mẫu xác nhận field mới populated đúng và ổn định theo thời gian.

## Validation Risks
- Drift giữa đường insert đơn và batch gây mất field.
- Sai semantics last-closed vs forming candle ở TF lớn gây dữ liệu rung.
- Null handling không nhất quán giữa signal engine và db writer.

## Mitigations
- Checklist bắt buộc cập nhật cả 2 đường insert.
- Test explicit cho ranh giới candle HTF.
- Golden test payload để bắt regression contract.
