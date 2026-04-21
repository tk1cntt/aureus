---
phase: 55-evaluation-data-model-pipeline
reviewed: 2026-04-21T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - services/aureus-db-writer/migrations/add_trade_evaluations.sql
  - services/aureus-db-writer/tests/test_evaluation_migration.py
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_evaluation_pipeline.py
  - services/aureus-trader/tests/test_signal_snapshot_migration.py
  - services/aureus-trader/tests/test_signal_snapshot_pipeline.py
  - services/aureus-trader/recompute_evaluations.py
  - services/aureus-trader/tests/test_evaluation_recompute.py
  - services/aureus-trader/tests/test_signal_snapshot_recompute.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 55: Code Review Report

**Reviewed:** 2026-04-21T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Đã review đúng phạm vi cố định 9 file của phase 55, tập trung vào bug/security/code quality theo ngữ cảnh Python + SQL migration + test contract.

Không phát hiện lỗ hổng bảo mật mức critical. Có 2 vấn đề mức **Warning** liên quan đến tính đúng đắn luồng xử lý và validation tham số thời gian.

## Warnings

### WR-01: Ép kiểu `score_total` không an toàn làm fail toàn bộ handler sau khi đã update journal

**File:** `services/aureus-trader/journal.py:245`
**Issue:** Trong `on_order_opened`, code gọi trực tiếp `float(score_total_raw)` khi persist evaluation. Nếu payload có `score_total` không parse được (ví dụ string không phải số), exception sẽ bị bắt ở outer `except`, khiến hàm trả `False` dù journal có thể đã được cập nhật thành công trước đó. Điều này gây trạng thái xử lý không nhất quán (partial success nhưng reported failure).

**Fix:** Validate và parse `score_total_raw` trước khi insert; nếu invalid thì log warning và skip persist evaluation thay vì ném exception cho cả handler.

```python
score_total_raw = event.get("score_total", event.get("score"))
score_total = None
if score_total_raw is not None:
    try:
        score_total = float(score_total_raw)
    except (TypeError, ValueError):
        logger.warning("on_order_opened: score_total is not numeric")

has_scoring_core = not (
    score_total is None
    or score_breakdown is None
    or weights_snapshot is None
    or missing_data_policy is None
)
# ... dùng score_total khi INSERT
```

### WR-02: Thiếu kiểm tra `start <= end` cho input recompute time-range

**File:** `services/aureus-trader/recompute_evaluations.py:30-31`
**Issue:** `_validate_args` parse được `--start` và `--end` nhưng không validate thứ tự thời gian. Nếu user truyền `start > end`, job vẫn chạy và trả kết quả rỗng/khó hiểu, làm giảm độ tin cậy vận hành và khả năng phát hiện sai cấu hình.

**Fix:** Parse thành datetime và chặn sớm nếu khoảng thời gian không hợp lệ.

```python
start_dt = _parse_iso8601(args.start)
end_dt = _parse_iso8601(args.end)
if start_dt > end_dt:
    raise ValueError("--start must be <= --end")
```

---

_Reviewed: 2026-04-21T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
