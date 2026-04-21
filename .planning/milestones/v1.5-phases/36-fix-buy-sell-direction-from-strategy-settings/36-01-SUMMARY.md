---
phase: 36
plan: 01
type: execute
tags:
  - strategy-direction
  - validation
  - template-strategy
requires:
  - Phase 35: MT5 Order Status Reporter (DONE)
provides:
  - Direction bắt buộc cấu hình rõ ràng, không suy luận từ tên strategy
affects:
  - services/aureus-signal/engine/strategies/template.py (direction validation)
  - services/aureus-signal/engine/strategies/seed_strategies.py (added direction field)
  - services/aureus-signal/tests/test_template_strategy.py (3 tests mới)
tech-stack:
  added: []
  patterns:
    - Explicit config over implicit naming convention
    - Case-insensitive validation with clear error messages
    - Database-first validation (fail early at strategy init)

key-files:
  modified:
    - services/aureus-signal/engine/strategies/template.py
    - services/aureus-signal/engine/strategies/seed_strategies.py
    - services/aureus-signal/tests/test_template_strategy.py

decisions:
  - "Direction MUST be explicitly configured in trade_execution — no fallback into strategy name"
  - "Invalid or missing direction raises ValueError immediately at TemplateStrategy.__init__"
  - "Case-insensitive validation (.strip().upper()) to handle config typos gracefully"

metrics:
  duration_minutes: 10
  completed_date: "2026-04-08"
  tests_passing: 16
  tests_new: 3
---

# Phase 36 Plan 01: Fix BUY/SELL Direction from Strategy Settings — Summary

**One-liner:** Bỏ fallback direction từ tên strategy ("BEAR"→SELL, "BULL"→BUY), bắt buộc cấu hình rõ ràng trong trade_execution config với validation stric.

## Tasks Completed

| Task | Name | Status |
|------|------|--------|
| 1 | Sửa TemplateStrategy.__init__ direction validation | ✅ DONE |
| 2 | Cập nhật seed_strategies.py thêm direction | ✅ DONE |
| 3 | Thêm test direction validation + chạy tests | ✅ DONE (16 pass) |
| 4 | Kiểm tra DB strategy templates có direction | ✅ DONE (6/6 rows OK) |

## Implementation Details

### Task 1: template.py (line 39-45)

```python
# TRƯỚC: fallback vào tên strategy
self.direction = self.trade_execution.get("direction")
if not self.direction:
    self.direction = "SELL" if "BEAR" in self.name.upper() else "BUY"

# SAU: bắt buộc config rõ ràng
direction = str(self.trade_execution.get("direction", "")).strip().upper()
if direction not in ("BUY", "SELL"):
    raise ValueError(
        f"Strategy '{self.name}': 'direction' must be 'BUY' or 'SELL' in trade_execution config. "
        f"Got: {self.trade_execution.get('direction')!r}"
    )
self.direction = direction
```

### Task 2: seed_strategies.py
Cả 6 strategies đều có `"direction"` trong `trade_execution`:
- TREND_CONT_BULL → BUY
- TREND_CONT_BEAR → SELL
- ORDER_FLOW_BULL → BUY
- ORDER_FLOW_BEAR → SELL
- SESSION_SWEEP_BULL → BUY
- SESSION_SWEEP_BEAR → SELL

### Task 3: Tests (16 passing)
3 tests mới:
- `test_direction_required` — raise ValueError khi không có direction
- `test_direction_invalid_value` — raise ValueError khi direction sai (e.g. "HEDGE")
- `test_direction_case_insensitive` — chấp nhận "buy", "Buy", "BUY"

### Task 4: DB Verification
```
 id |        name        | direction 
----+--------------------+-----------
  1 | TREND_CONT_BULL    | BUY
  2 | TREND_CONT_BEAR    | SELL
  3 | ORDER_FLOW_BULL    | BUY
  4 | ORDER_FLOW_BEAR    | SELL
  5 | SESSION_SWEEP_BULL | BUY
  6 | SESSION_SWEEP_BEAR | SELL
(6 rows)
```

## Self-Check: PASSED

- [x] template.py line 39-45 có direction validation
- [x] Không còn fallback vào tên strategy
- [x] 6 seed strategies có direction trong trade_execution
- [x] 16 tests pass (có 3 tests mới)
- [x] DB 6 rows có direction đúng
- [x] ValueError raise cho missing/invalid direction
