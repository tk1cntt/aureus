---
phase: 260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-
verified: 2026-04-27T00:00:00Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Xác nhận GitNexus gate cho quick task 260427-v5g"
    expected: "Developer chấp nhận evidence trong SUMMARY rằng impact gate đã được thử/chạy một phần và detect_changes không khả dụng trong installed CLI, hoặc yêu cầu chạy lại bằng GitNexus MCP/tool đúng môi trường."
    why_human: "Must-have này là process gate trước sửa/commit; verifier chỉ thấy SUMMARY ghi detect_changes không chạy được vì CLI unknown command, không thể tái tạo thời điểm trước commit."
---

# Quick Task 260427-v5g Verification Report

**Task Goal:** Implement các phần TODO và các phần chưa hoàn thiện ở `services/aureus-signal/engine/orders.py`
**Verified:** 2026-04-27T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ORDER plan không còn fallback im lặng sang CURRENT hoặc FIXED_PIPS khi entry/SL method không tính được. | VERIFIED | `orders.py` checks `computed_entry is None` before SL/TP and `float(computed_entry)`, persists rejection, and publishes `ORDER_REJECTED`. PIVOT_POINT returns `(None, None)` when no valid pivot; tests pass. |
| 2 | PIVOT_POINT SL dùng pivot_index sau khi lọc pivot hợp lệ; nếu thiếu pivot tương ứng thì warning và reject order. | VERIFIED | `orders.py` builds `valid_pivots` after 5-candle filtering, then selects `valid_pivots[pivot_index - 1]`; missing selection returns `(None, None)`. `test_pivot_sl.py` covers pivot_index and no-pivot behavior. |
| 3 | PULLBACK_50 và ENTRY_PIVOT_LIMIT tạo entry từ swing point LL/HH chưa broken đúng side, hoặc reject nếu thiếu/không hợp lệ. | VERIFIED | `_entry_pullback_50` and `_entry_pivot_limit` filter by `broken`, `is_high`, and `type` (`LL` for BUY, `HH` for SELL), validate side relative to current price, and return `None` with warning if unavailable. |
| 4 | ENTRY_PIVOT_LIMIT được snapshot validation chấp nhận để seed strategies dùng đúng entry method. | VERIFIED | `snapshot_utils.py` includes `ENTRY_PIVOT_LIMIT` in `VALID_ENTRY_METHODS`; `_build_order_plan_snapshot` uses that constant for entry method validation. |
| 5 | Trước khi sửa symbol phải có GitNexus impact; trước commit phải có GitNexus detect_changes. | NEEDS HUMAN | SUMMARY documents impact attempts and partial impact results, but also states `gitnexus_detect_changes` could not be run because CLI commands were unavailable. This process gate cannot be fully verified post-hoc by code inspection. |

**Score:** 4/5 truths verified automatically

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `D:/Aureus/services/aureus-signal/engine/orders.py` | Order entry/SL calculation and ORDER_REJECTED path for incomplete plans; contains `_calculate_entry_price` | VERIFIED | File exists and contains substantive implementations for `_calculate_entry_price`, entry helpers, PIVOT_POINT SL, and process-level rejection. |
| `D:/Aureus/services/aureus-signal/engine/snapshot_utils.py` | `VALID_ENTRY_METHODS` includes `ENTRY_PIVOT_LIMIT` | VERIFIED | Constant includes `ENTRY_PIVOT_LIMIT`. |
| `D:/Aureus/services/aureus-signal/tests/test_entry_price_methods.py` | Regression coverage for entry methods and no-fallback behavior | VERIFIED | File exists, imports live `SimulatedTradeManager`, asserts invalid/missing methods return `None`, process-level rejection emits `ORDER_REJECTED`, and `ENTRY_PIVOT_LIMIT` is valid. |
| `D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py` | Regression coverage for PIVOT_POINT pivot_index/no-fallback behavior | VERIFIED | File exists with tests for no pivot, `pivot_index`, 5-candle filtering, and unchanged FIXED_PIPS behavior. |
| `D:/Aureus/services/aureus-signal/tests/test_decision_trace_schema.py` | Regression coverage that rejection payload remains traceable/schema-compatible | VERIFIED | File exists and includes process-level incomplete order plan rejection assertions with trace fields and `ORDER_REJECTED`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `orders.py::_calculate_entry_price` | `orders.py::process_triggers` | `computed_entry None must reject before float(computed_entry)` | VERIFIED | `process_triggers` calls `_calculate_entry_price`, checks `if computed_entry is None`, emits rejection, and only later creates order with `float(computed_entry)`. |
| `snapshot_utils.py::VALID_ENTRY_METHODS` | `orders.py::_build_order_plan_snapshot` | entry method validation preserves `ENTRY_PIVOT_LIMIT` | VERIFIED | `orders.py` imports `VALID_ENTRY_METHODS`; `ENTRY_PIVOT_LIMIT` is present in `snapshot_utils.py`, so validation does not normalize it to CURRENT. |
| `orders.py::_calculate_sl_tp` | `orders.py::_find_pivot_for_sl_candidates` | PIVOT_POINT SL filters pivots then applies pivot_index | VERIFIED | PIVOT_POINT branch calls `_find_pivot_for_sl_candidates`, filters candidates by last 5 candles, then applies `pivot_index`. |
| `test_entry_price_methods.py` | `orders.py::_calculate_entry_price` | pytest imports manager and asserts `None`/rejection | VERIFIED | Test imports `SimulatedTradeManager` from `engine.orders` and directly exercises `_calculate_entry_price` plus `process_triggers`. |
| `test_pivot_sl.py` | `orders.py::_calculate_sl_tp` | pytest builds state swing_points and asserts pivot behavior | VERIFIED | Test imports `SimulatedTradeManager` and directly exercises `_calculate_sl_tp` and `_find_pivot_for_sl_candidates`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `orders.py` | `computed_entry` | `_calculate_entry_price` from `state_obj.last_candle`, swing points, OBs, EMAs, or entry value | Yes | VERIFIED |
| `orders.py` | PIVOT_POINT `valid_pivots` / `selected_pivot` | `_find_pivot_for_sl_candidates` from `state_obj.swing_points`, optionally filtered by `recent_candles` | Yes | VERIFIED |
| `snapshot_utils.py` | `VALID_ENTRY_METHODS` | Static validation contract consumed by `_build_order_plan_snapshot` | Yes | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| New targeted and existing order-event tests pass | `python -m pytest "D:/Aureus/services/aureus-signal/tests/test_entry_price_methods.py" "D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py" "D:/Aureus/services/aureus-signal/tests/test_decision_trace_schema.py" "D:/Aureus/services/aureus-signal/unittest/test_orders_events.py" -q` | `50 passed in 0.73s` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| QUICK-260427-V5G | `260427-v5g-PLAN.md` | Implement TODO/chưa hoàn thiện in `orders.py` with no silent fallback and tests | SATISFIED_WITH_HUMAN_GATE | Code behavior and tests are satisfied; GitNexus process gate needs human acceptance because detect_changes was documented as unavailable. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `D:/Aureus/services/aureus-signal/engine/orders.py` | 358 | `Placeholder — MT5 calculates real lot` | Info | Intentional runtime placeholder for MT5-side lot calculation, not related to entry/SL TODO completion. |
| `D:/Aureus/services/aureus-signal/engine/orders.py` | 15-17 | `fallback` in default risk budget comment | Info | Existing config fallback, unrelated to prohibited entry/SL fallback. |

### Human Verification Required

#### 1. Xác nhận GitNexus gate cho quick task 260427-v5g

**Test:** Review GitNexus evidence in `D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-SUMMARY.md`, especially lines documenting impact attempts and unavailable `gitnexus_detect_changes` CLI.

**Expected:** Developer either accepts the documented CLI limitation and diff/test substitute, or asks executor to rerun the gate in an environment where GitNexus MCP/tool supports `detect_changes`.

**Why human:** This is a process-timing gate (before edit/commit). Automated verifier cannot reconstruct whether all required pre-edit impact gates happened, and SUMMARY explicitly says detect_changes did not run due CLI unavailability.

### Gaps Summary

No code-level gaps were found for the task goal. `orders.py` now rejects incomplete entry/SL plans instead of silently falling back, `ENTRY_PIVOT_LIMIT` is accepted by validation, and regression tests pass.

Overall status remains `human_needed` because the GitNexus gate must-have is not fully machine-verifiable and `detect_changes` was documented as unavailable rather than completed.

---

_Verified: 2026-04-27T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
