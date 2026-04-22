# Quick Task 260422-v1s - Summary

## Mục tiêu
Khắc phục tình trạng `aureus_trade_signal_snapshots` map sai/thiếu dữ liệu khiến các cột signal bị NULL hàng loạt.

## Root cause xác nhận
1. `STRATEGY_MATCH` payload từ signal engine không gửi field `signal_snapshot` xuống trader, chỉ có `active_signals`.
2. `dispatcher` không forward `signal_snapshot` từ order command sang `ORDER_OPENED` event cho journal.
3. `recompute_evaluations.py` vẫn đọc schema legacy (`signal_snapshot`, `ema21`, `ema55`, `cisd_direction`) nên lỗi runtime với DB schema mới.

## Thay đổi đã thực hiện
- `services/aureus-signal/engine/signal_event_publisher.py`
  - Bổ sung `data.signal_snapshot` trong `publish_strategy_match`.
  - Ưu tiên `strategy_result.normalized_signal_snapshot`; fallback dict rỗng.

- `services/aureus-trader/order_builder.py`
  - Forward `signal_snapshot` vào lệnh `OPEN_ORDER` (dict hoặc `{}`).

- `services/aureus-trader/dispatcher.py`
  - Khi nhận `ORDER_OPENED`, chèn `signal_snapshot` từ `order` vào `final` nếu event chưa có.

- `services/aureus-trader/recompute_evaluations.py`
  - Chuyển toàn bộ truy vấn recompute từ cột legacy sang cột schema mới của `aureus_trade_signal_snapshots`.
  - Bỏ phụ thuộc `row['signal_snapshot']`; insert trực tiếp từ các cột đã select.

- Tests cập nhật:
  - `services/aureus-signal/tests/test_signal_event_publisher.py`
  - `services/aureus-trader/tests/test_order_builder.py`
  - `services/aureus-trader/tests/test_signal_snapshot_recompute.py`

## Verification
### Unit/Integration tests
- `pytest services/aureus-signal/tests/test_signal_event_publisher.py -q` ✅
- `pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py -q` ✅
- `pytest services/aureus-trader/tests/test_dispatcher.py -q` ✅
- `pytest services/aureus-trader/tests/test_order_builder.py -q` ✅
- `pytest services/aureus-trader/tests/test_signal_snapshot_recompute.py -q` ✅
- Combined subset: 37 passed ✅

### E2E với database thật (bắt buộc theo quy định project)
1. Chạy recompute script với DB thật sau fix:
   - Kết quả: `{"processed": 2, "evaluation_inserted": 2, "signal_snapshot_inserted": 2}`
2. Chạy e2e script tạo journal + `ORDER_OPENED` và verify snapshot:
   - Kết quả snapshot: `atr=2.75`, `ema_21=3348.1`, `session=2`, `candle_color_d1=1`, `bb_m1_up=3355.8`, `cisd_m5=1` (non-null đúng mapping).

## Kết luận
Pipeline signal snapshot đã được nối đúng end-to-end (publish -> order command -> dispatcher -> journal insert), và recompute đã tương thích schema hiện tại, không còn phụ thuộc cột legacy gây null/lỗi runtime.
