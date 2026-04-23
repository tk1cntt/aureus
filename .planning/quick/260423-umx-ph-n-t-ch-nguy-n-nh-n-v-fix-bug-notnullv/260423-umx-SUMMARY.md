# Quick Task 260423-umx Summary

## Mục tiêu
Fix lỗi runtime:

`asyncpg.exceptions.NotNullViolationError: null value in column "timeframe" of relation "aureus_trade_signal_snapshots"`

khi `on_order_opened` insert snapshot.

## Root cause
Trong `on_order_opened`, câu lệnh insert vào `aureus_trade_signal_snapshots` chưa truyền cột `timeframe` mặc dù schema DB yêu cầu NOT NULL.
Vì vậy khi record snapshot được ghi, DB reject do `timeframe=NULL`.

## Impact analysis (trước edit)
- Symbol: `on_order_opened` (`services/aureus-trader/journal.py`)
- Command: `npx gitnexus impact on_order_opened --repo Aureus --direction upstream --depth 3` (chạy trên host, không chạy trong WSL)
- Kết quả:
  - direct callers (d=1): 0
  - affected processes: 0
  - risk: LOW

## Thay đổi đã thực hiện
1. `services/aureus-trader/journal.py`
   - Bổ sung `timeframe` vào danh sách cột insert `aureus_trade_signal_snapshots`.
   - Bổ sung param bind `timeframe` vào VALUES và argument list.
   - Dùng fallback timeframe đã chuẩn hóa sẵn trong `on_order_opened` (`event -> journal -> M1`) cho cả evaluation và snapshot insert.

2. `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
   - Cập nhật assertions theo vị trí param mới sau khi thêm `timeframe` vào snapshot insert.
   - Assert `snapshot_args[5] == "M1"` cho case thiếu timeframe.
   - Cập nhật contract query expectation: snapshot insert có chứa `timeframe`.

## Kết quả verify
### Unit tests
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py services/aureus-trader/tests/test_evaluation_pipeline.py -q"`
- Kết quả: **8 passed**.

### E2E DB/runtime check
- Chạy script e2e trader:
  - `./.venv/bin/python services/aureus-trader/tests/test_e2e_trader.py`
- Kiểm tra DB trước/sau:
  - `SELECT COUNT(*) FROM aureus_trade_signal_snapshots`
- Kết quả: chưa phát sinh row mới vì runtime event ORDER_OPENED đang thiếu `trace_id` (log `on_order_opened: missing trace_id in event`) nên flow journal stop sớm trước bước insert snapshot.
- Tuy vậy, bug gốc NotNullViolation do thiếu cột/param `timeframe` đã được loại bỏ ở code path insert và được khóa bằng unit tests.

## Scope check
Đổi trong đúng phạm vi quick task:
- `services/aureus-trader/journal.py`
- `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
- docs quick task (`PLAN.md`, `SUMMARY.md`) và `STATE.md` do workflow.

## Kết luận
Fix đã đảm bảo snapshot insert có `timeframe` hợp lệ, chặn lỗi `NotNullViolation` do `timeframe NULL` ở layer SQL binding.