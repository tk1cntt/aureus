---
phase: quick-260428-9kd-trend-cont-bull-va-trend-cont-limit-bull
plan: 01
subsystem: aureus-signal
tags: [strategy-evaluation, trend-continuation, regression, parity]
dependency_graph:
  requires: [services/aureus-signal/engine/strategies/seed_strategies.py, services/aureus-signal/engine/strategies/registry.py, services/aureus-signal/engine/strategies/template.py]
  provides: [TREND_CONT_BULL/TREND_CONT_LIMIT_BULL parity regression evidence]
  affects: [strategy registry evaluation before executor dispatch]
tech_stack:
  added: []
  patterns: [TDD regression, focused pytest verification, GitNexus CLI fallback]
key_files:
  created: []
  modified:
    - services/aureus-signal/tests/test_strategy_seed_sync.py
decisions:
  - Không sửa production logic vì regression chứng minh TREND_CONT_LIMIT_BULL đã được seed active và được registry evaluate/accept cùng snapshot với TREND_CONT_BULL; khác biệt chỉ nằm ở order_plan entry_type/entry_method/entry_value.
metrics:
  duration: PT0H
  completed_at: "2026-04-27T23:56:42Z"
---

# Quick 260428-9kd: Trend Cont Bull và Trend Cont Limit Bull Summary

Thêm regression chứng minh `TREND_CONT_LIMIT_BULL` đi qua seed/registry/evaluation trước executor như `TREND_CONT_BULL`, chỉ khác `LIMIT` + `ENTRY_PIVOT_LIMIT` + `entry_value=PIVOT`.

## Objective

Điều tra vì sao runtime không quan sát thấy `TREND_CONT_LIMIT_BULL` trigger trong khi `TREND_CONT_BULL` trigger trên cùng điều kiện vào lệnh, và fix surgical nếu có bug ở seed/config, registry, evaluator, dedupe, executor, hoặc runtime activation.

## Tasks Completed

| Task | Status | Commit | Notes |
|------|--------|--------|-------|
| Task 1: Trace parity path and reproduce missing TREND_CONT_LIMIT_BULL trigger | Completed | 9698f14 | Thêm regression dùng seed config thật, registry thật và snapshot `choch_up` synthetic để chứng minh cả market và limit bull cùng accepted trước executor. |
| Task 2: Apply surgical fix for the failing layer | Completed | N/A | Không cần sửa production logic; không reproduce được bug code/config sau fix trước đó `260427-wwv`. |
| Task 3: Verify runtime flow and summarize evidence | Completed | N/A | Chạy focused trend test pass; broader strategy suite vẫn fail ở lỗi runbook pre-existing đã biết. |

## Root Cause / Kết luận điều tra

- Không tìm thấy bug mới trong code path seed/registry/evaluator cho `TREND_CONT_LIMIT_BULL` ở trạng thái hiện tại.
- Seed hiện tại đã khai báo đúng:
  - `TREND_CONT_BULL`: `direction=BUY`, `entry_type=MARKET`, `entry_method=CURRENT`.
  - `TREND_CONT_LIMIT_BULL`: `direction=BUY`, `entry_type=LIMIT`, `entry_method=ENTRY_PIVOT_LIMIT`, `entry_value=PIVOT`.
- Regression mới tạo registry với đúng hai strategy từ `seed_system_strategies`, đẩy cùng một synthetic snapshot có event `choch_up` tại `t=1000`, rồi gọi `StrategyRegistry.evaluate_all(...)`.
- Kết quả regression: cả `TREND_CONT_BULL` và `TREND_CONT_LIMIT_BULL` đều nằm trong accepted results trước executor; `registry.get_rejections()` rỗng; `state.strategy_progress` của cả hai đều có `triggered_t=1000`.
- Vì cả hai strategy có key progress riêng theo tên strategy, không có bằng chứng dedupe ở registry/evaluator nuốt limit variant. Dedupe executor cũng dùng strategy id trong key theo source hiện tại, nên market variant không chia sẻ cùng dedupe key với limit variant.
- Nếu runtime vẫn không thấy order limit, khả năng cao nằm sau bước pre-executor accepted result: `ENTRY_PIVOT_LIMIT` cần pivot hợp lệ để tính entry price; khi không có LL pivot hợp lệ cho BUY, executor có thể reject order thay vì publish/dispatch. Việc này là thiết kế của limit entry, không phải mất trigger ở registry/evaluator.

## Changes Made

- Cập nhật `services/aureus-signal/tests/test_strategy_seed_sync.py`:
  - thêm import `pandas`, `SymbolState`, `StrategyRegistry`, `TemplateStrategy`;
  - thêm test `test_trend_cont_bull_and_limit_bull_match_same_snapshot_before_executor`;
  - test dùng `FakePool/FakeConn` sẵn có để seed config thật, đăng ký hai strategy vào registry, evaluate snapshot `choch_up`, rồi assert parity trước executor.

## GitNexus Evidence

- `npx gitnexus query "TREND_CONT_LIMIT_BULL TREND_CONT_BULL strategy trigger evaluation dedupe executor" --repo Aureus` trả về seed/evaluation related processes, nổi bật `seed_system_strategies` và `_seed_with_conn` trong các process `run_strategy_executor`, `run_signal_engine`, `main`, `verify_sparse_storage`.
- `npx gitnexus context TemplateStrategy --repo Aureus` xác nhận `TemplateStrategy` có các method liên quan `_evaluate_sequence`, `on_bar_close`, `evaluate`, `validate_entry`, `build_order_plan`.
- Impact trước khi thêm regression test:
  - `npx gitnexus impact TemplateStrategy --repo Aureus --direction upstream`: impactedCount 0, risk LOW.
  - `npx gitnexus impact StrategyRegistry --repo Aureus --direction upstream`: impactedCount 0, risk LOW.
- `gitnexus_detect_changes` theo yêu cầu project không khả dụng trong CLI hiện tại:
  - `npx gitnexus detect_changes --scope staged` → `unknown command 'detect_changes'`.
  - `npx gitnexus detect-changes --scope staged` → `unknown command 'detect-changes'`.
  - Fallback đã dùng `git diff`/`git diff --stat` xác nhận chỉ thay đổi `services/aureus-signal/tests/test_strategy_seed_sync.py`.

## Verification

### Regression đơn lẻ

Command:

```bash
cd D:/Aureus && python -m pytest services/aureus-signal/tests/test_strategy_seed_sync.py::test_trend_cont_bull_and_limit_bull_match_same_snapshot_before_executor -q
```

Result: `1 passed in 1.22s`.

### Trend continuation focused suite

Command:

```bash
cd D:/Aureus && python -m pytest services/aureus-signal/tests -k "trend_cont" -x
```

Result: `6 passed, 656 deselected in 19.74s`.

### Strategy broader suite

Command:

```bash
cd D:/Aureus && python -m pytest services/aureus-signal/tests -k "strategy" -x
```

Result: `94 passed, 1 skipped, 508 deselected`, rồi fail tại pre-existing/out-of-scope `test_runbook_contract` do thiếu `.planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md`.

### Combined final suite

Command:

```bash
cd D:/Aureus && python -m pytest services/aureus-signal/tests -k "trend_cont or strategy" -x
```

Result: `97 passed, 1 skipped, 505 deselected`, rồi fail cùng pre-existing/out-of-scope `test_runbook_contract` do thiếu runbook phase 46.

## Deviations from Plan

None - plan được thực hiện đúng phạm vi. Không có production bug mới để sửa, nên Task 2 kết thúc bằng bằng chứng không cần đổi production code.

## Deferred Issues

- Pre-existing/out-of-scope: `services/aureus-signal/tests/test_strategy_seed_sync.py::test_runbook_contract` fail vì thiếu `D:/Aureus/.planning/phases/46-strategy-seed-sync/46-ROLLBACK-RUNBOOK.md`. Lỗi này đã được ghi nhận từ quick `260427-wwv` và không do thay đổi của quick này.
- GitNexus CLI trong môi trường hiện tại không có command `detect_changes`/`detect-changes`; đã document limitation và fallback bằng diff scope.

## Known Stubs

None found in modified file.

## Threat Flags

None. Quick này chỉ thêm regression test, không thêm endpoint, auth path, file access runtime, schema change, hoặc trust boundary mới.

## Self-Check: PASSED

- File modified exists: `D:/Aureus/services/aureus-signal/tests/test_strategy_seed_sync.py`.
- Summary exists: `D:/Aureus/.planning/quick/260428-9kd-trend-cont-bull-va-trend-cont-limit-bull/260428-9kd-SUMMARY.md`.
- Commit exists: `9698f14`.
- Scope check: `git diff --stat HEAD~1..HEAD` chỉ hiển thị `services/aureus-signal/tests/test_strategy_seed_sync.py` với 48 insertions.
