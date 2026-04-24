# Quick Task 260424-fo9 Summary

## Objective
Fix runtime error `NotNullViolationError: signal_schema_version` khi `on_order_opened` ghi vào `aureus_trade_signal_snapshots`.

## Impact Analysis (Required)
- Command: `npx gitnexus impact --repo Aureus --direction upstream on_order_opened`
- Target: `services/aureus-trader/journal.py::on_order_opened`
- Risk: **LOW**
- Direct callers (d=1): 0
- Affected processes/modules: 0

## Changes

### 1) `services/aureus-trader/journal.py`
- Trong `on_order_opened`, bổ sung normalize `signal_schema_version`:
  - Lấy từ `event["signal_schema_version"]` nếu có và hợp lệ.
  - Fallback mặc định ổn định: `sig-v2.0.0` nếu thiếu/rỗng.
- Cập nhật câu `INSERT INTO aureus_trade_signal_snapshots` để persist thêm:
  - `signal_schema_version`
  - `signal_snapshot` (`jsonb`, đảm bảo có payload object; fallback `{ "timeframe": timeframe }` khi snapshot rỗng)
- Giữ nguyên logic evaluation/snapshot mapping hiện có ngoài các field cần thiết cho fix.

### 2) `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
- Cập nhật contract test để phản ánh schema/runtime hiện tại:
  - Query snapshot phải chứa `signal_schema_version` và `signal_snapshot`.
  - Assertion index args được dời tương ứng sau khi thêm cột mới.
  - Bổ sung assert fallback `signal_schema_version == "sig-v2.0.0"` khi event thiếu field.

## Verification

### Focused RED/GREEN
- `pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py -x` ✅ (4 passed)

### Regression
- `pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py services/aureus-trader/tests/test_journal.py -x` ✅ (66 passed)

### Runtime + DB e2e (real services)
- Restart service:
  - `wsl -d Aureus -e bash -lc "docker restart aureus-trader-dev"` ✅
- E2E trigger:
  - `wsl -d Aureus -u root bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-trader/tests/test_e2e_mt5_orders.py"` ✅
- Log check (new window):
  - Không còn xuất hiện mới `NotNullViolationError: signal_schema_version`.
  - Có `snapshot_insert ... result=INSERT 0 1` cho order mới.
- DB check:
  - `SELECT created_at, trace_id, ticket, signal_schema_version, jsonb_typeof(signal_snapshot) ... LIMIT 5;`
  - Kết quả có bản ghi mới với `signal_schema_version = 'sig-v2.0.0'`, `snapshot_type = object`.

## Notes
- Trong log còn thấy lỗi runtime khác cho một số order (ví dụ `invalid entry_price '0.0'`), và trước patch có phát sinh `NotNullViolationError` cho cột `signal_snapshot`; đã được xử lý trong cùng patch bằng cách luôn gửi `signal_snapshot` object hợp lệ.
- Scope fix giữ tối thiểu đúng theo quick objective: đảm bảo snapshot insert không vi phạm NOT NULL cho `signal_schema_version` và không phá regression test hiện có.
