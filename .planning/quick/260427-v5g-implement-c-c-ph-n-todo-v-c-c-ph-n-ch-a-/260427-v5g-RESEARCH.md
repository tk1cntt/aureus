# Quick Task 260427-v5g: orders.py TODO Implementation - Research

**Researched:** 2026-04-27
**Domain:** `services/aureus-signal/engine/orders.py` order-plan validation, entry price, PIVOT_POINT SL
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Implement toàn bộ TODO/chưa hoàn thiện trong `orders.py`, chỉ sửa file khác khi bắt buộc để test hoặc tương thích. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]
- Nếu có lỗi broker/order lifecycle: log warning và reject order. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]
- Không retry order submission vì order chỉ có ý nghĩa tức thì; retry làm mất tính đúng thời điểm vào lệnh. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]
- Nếu thay đổi chạm tới database hoặc luồng tạo/sửa data, phải chạy DB E2E để xác nhận chỉnh sửa và tạo data thành công. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]

### Claude's Discretion
- Giữ thay đổi tối thiểu, theo pattern hiện có, không mở rộng scope ngoài nhu cầu của `orders.py`. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
- Không có deferred ideas trong CONTEXT.md. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]
</user_constraints>

## Summary

`orders.py` hiện có 4 TODO/chưa hoàn thiện chính: `pivot_index` trong PIVOT_POINT SL, bỏ fallback sang FIXED_PIPS khi không có pivot hợp lệ, bỏ fallback CURRENT cho entry methods bị lỗi, và implement `_entry_pullback_50`/`_entry_pivot_limit`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] Hướng implement nên thống nhất với decision: mọi lỗi tính entry/SL/TP phải `logger.warning` rồi reject qua luồng `ORDER_PLAN_INCOMPLETE`/`ORDER_REJECTED`, không retry và không tự đổi sang giá hiện tại. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]

`process_triggers()` đã có sẵn cơ chế reject: nếu `sl` hoặc `tp` là `None`, snapshot thiếu `sl_value`/`tp_value` sẽ bị `_missing_order_plan_keys()` bắt, `_persist_rejection()` lưu vào state, và publish Redis stream `ORDER_REJECTED`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] Vì vậy cách sửa ít scope nhất là để `_calculate_entry_price()` trả `None` khi không tính được, rồi thêm guard trong `process_triggers()` để warning + reject trước khi cast `float(computed_entry)`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]

**Primary recommendation:** Implement helpers trả `Optional[float]`, không fallback im lặng; dùng một helper reject chung trong `process_triggers()` nếu entry/sl/tp không tính được, publish `ORDER_REJECTED`, và cập nhật tests hiện có đang assert fallback cũ.

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi phải dùng tiếng Việt. [VERIFIED: D:/Aureus/CLAUDE.md]
- Khi command lỗi, tham khảo `RUN_SERVICES.md`. [VERIFIED: D:/Aureus/CLAUDE.md]
- Nếu sửa tính năng liên quan database phải test e2e với database để xác nhận chỉnh sửa và tạo data thành công. [VERIFIED: D:/Aureus/CLAUDE.md]
- Trước khi chỉnh sửa function/class/method phải chạy `gitnexus_impact({target: "symbolName", direction: "upstream"})` và báo blast radius. [VERIFIED: D:/Aureus/CLAUDE.md]
- Trước khi commit phải chạy `gitnexus_detect_changes()` để xác nhận scope. [VERIFIED: D:/Aureus/CLAUDE.md]
- Không refactor ngoài yêu cầu; match style hiện có; remove only orphan do thay đổi tạo ra. [VERIFIED: D:/Aureus/CLAUDE.md]

## TODO Inventory and Recommended Implementation

| Area | Current State | Recommended Action | Confidence |
|------|---------------|--------------------|------------|
| PIVOT_POINT `pivot_index` | TODO tại `_calculate_sl_tp()`, hiện chọn pivot đầu tiên sau filter. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | Sau khi filter `pivots`, chọn candidate thứ `pivot_index - 1`; nếu thiếu candidate thì warning và để `sl=None`. `pivot_index=1` là nearest, `2` là second nearest theo comment hiện có. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | HIGH |
| No valid PIVOT_POINT pivot | Fallback FIXED_PIPS đã bị comment, nhưng chưa warning/return rõ ràng. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | Log warning `PIVOT_POINT SL ... no valid pivot ... rejected`, return `(None, None)` hoặc để `sl=None` để TP RR không tính được và reject. Nên return `(None, None)` để explicit. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | HIGH |
| `_calculate_entry_price()` fallback | TODO nói bỏ fallback CURRENT; hiện unknown/CURRENT đều trả close, helper failures trả fallback `None` vì caller pass `None`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | Chỉ `CURRENT` trả close. Unknown hoặc method fail trả `None` + warning. `process_triggers()` phải reject nếu `computed_entry is None` trước `_calculate_sl_tp()`/`float()`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | HIGH |
| `_entry_pullback_50()` | TODO, hiện return `None`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] | Dùng swing point gần nhất chưa broken đúng side: BUY dùng LL, SELL dùng HH. BUY entry = midpoint giữa LL price và trigger candle high; SELL entry = midpoint giữa HH price và trigger candle low. Reject nếu thiếu pivot hoặc entry không đúng side so với current close. Pattern có trong `tmp/simulated_orders.py`. [VERIFIED: D:/Aureus/tmp/simulated_orders.py] | MEDIUM-HIGH |
| `_entry_pivot_limit()` | TODO, seed strategies đang dùng `ENTRY_PIVOT_LIMIT` nhưng constant chưa cho phép. [VERIFIED: D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py] | Thêm `ENTRY_PIVOT_LIMIT` vào `VALID_ENTRY_METHODS`, tests constants, và implement chọn newest valid LL/HH chưa broken từ `state_obj.swing_points`. BUY → LL price dưới current; SELL → HH price trên current; lỗi thì `None` + warning/reject. [VERIFIED: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py] | HIGH |

## Integration Points

- `process_triggers()` builds `order_plan_snapshot`, computes entry, computes SL/TP, validates required keys, then appends active order and publishes `ORDER_OPEN`/`ORDER_PENDING`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]
- `ORDER_REJECTED` is an accepted stream event; DB writer explicitly skips `ORDER_REJECTED` because it is not a real trade. [VERIFIED: D:/Aureus/services/aureus-db-writer/main.py]
- `seed_strategies.py` already defines `TREND_CONT_LIMIT_BULL/BEAR` with `entry_method: ENTRY_PIVOT_LIMIT` and `sl.pivot_index: 2`, so adding the entry method is compatibility work, not new feature expansion. [VERIFIED: D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py]
- `snapshot_utils.VALID_ENTRY_METHODS` currently excludes `ENTRY_PIVOT_LIMIT`, causing `_build_order_plan_snapshot()` to default it to CURRENT with a warning. [VERIFIED: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py] Planner should include updating this constant if implementation targets the TODO in `orders.py`.
- There is a similarly named `engine/simulated_orders.py` used by backtest tests; task scope is `orders.py`, so avoid changing backtest manager unless tests or shared constants require it. [VERIFIED: D:/Aureus/services/aureus-signal/tests/test_entry_price_methods.py]

## Architecture Patterns

### Reject flow to reuse

```python
# Source: D:/Aureus/services/aureus-signal/engine/orders.py
reason_payload = {
    "trace_id": trace_id,
    "symbol": symbol,
    "strategy_id": strat_id,
    "strategy_name": strategy_name,
    "decision_phase": "process_triggers",
    "status": "REJECTED",
    "reason_code": "ORDER_PLAN_INCOMPLETE",
    ...
}
self._persist_rejection(state_obj, reason_payload)
await self.r.xadd(f"aureus:stream:{symbol}:orders", {"type": "ORDER_REJECTED", "data": json.dumps(reason_payload)})
```

Use the same pattern for entry calculation failure, preferably by extracting a small local/helper method only if it reduces duplication; keep surgical. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]

### Pivot search pattern

`_find_pivot_for_sl_candidates()` already filters swing points in reverse order, skips `broken`, and enforces BUY→LL / SELL→HH. Reuse or mirror this for PIVOT_POINT SL and entry pivot to avoid divergent semantics. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry lifecycle/order submit | Custom retry/backoff | Immediate reject + warning | User decision says order timing is moment-specific; retry can create stale entries. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md] |
| New persistence for rejected orders | DB table/write path | Existing `state_obj.record_order_rejection`/`order_rejections` + `ORDER_REJECTED` stream | Existing flow already records rejection without creating real order rows. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] |
| New swing/pivot model | New classes/schema | Existing `state_obj.swing_points` dicts with `price`, `is_high`, `type`, `broken`, `t` | Orders and pivot SL already use this runtime shape. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] |

## Common Pitfalls

1. **Casting `None` to float after entry failure.** `process_triggers()` currently does `float(computed_entry)` when creating order; if `_calculate_entry_price()` starts returning `None`, add explicit reject before this point. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]
2. **Old tests expect fallback.** `test_entry_price_methods.py` currently asserts invalid/missing OB/EMA/FIXED_OFFSET fallback to current close and constants exclude `ENTRY_PIVOT_LIMIT`; these must be updated to new reject/None behavior or supplemented with process-level rejection tests. [VERIFIED: D:/Aureus/services/aureus-signal/tests/test_entry_price_methods.py]
3. **Pivot SL test mismatch.** `test_pivot_sl.py::test_pivot_point_no_pivot_fallbacks_to_fixed_pips` expects fallback, contradicting user decision/TODO; update it to expect `(None, None)` or rejection at process level. [VERIFIED: D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py]
4. **`ENTRY_PIVOT_LIMIT` validation gap.** If only `_entry_pivot_limit()` is implemented but `VALID_ENTRY_METHODS` is not updated, `_build_order_plan_snapshot()` will still normalize it to `CURRENT`. [VERIFIED: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py]
5. **DB/E2E trigger.** If implementation only changes order rejection/open stream behavior and unit tests, no DB schema/data writer modification is required; if planner changes DB writer or journal persistence, DB E2E becomes mandatory per CLAUDE.md and CONTEXT. [VERIFIED: D:/Aureus/CLAUDE.md]

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 on Python 3.12.9 [VERIFIED: local CLI] |
| Config file | none detected at repo root or `services/aureus-signal/pytest.ini` [VERIFIED: Glob] |
| Quick run command | `python -m pytest services/aureus-signal/tests/test_entry_price_methods.py services/aureus-signal/tests/test_pivot_sl.py services/aureus-signal/tests/test_decision_trace_schema.py -q` [VERIFIED: Glob/Read] |
| Broader order event command | `python -m pytest services/aureus-signal/unittest/test_orders_events.py services/aureus-signal/unittest/test_simulated_orders_pullback.py -q` [VERIFIED: Glob/Read] |
| DB/E2E command | Required only if DB/data-write path touched; candidate test file exists at `services/aureus-trader/tests/test_e2e_mt5_orders.py`. [VERIFIED: Glob] |

### Wave 0 Gaps

- [ ] Add/update tests for process-level rejection when entry method fails, invalid method is supplied, PIVOT_POINT has no valid pivot, and `ENTRY_PIVOT_LIMIT` is accepted. [VERIFIED: D:/Aureus/services/aureus-signal/tests/test_entry_price_methods.py]
- [ ] Update existing fallback assertions to align with locked behavior: warning + reject/no order, no retry. [VERIFIED: D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Unit tests | yes | 3.12.9 | none |
| pytest | Unit tests | yes | 9.0.2 | none |
| Redis | Integration/process stream tests if using real Redis | not probed | — | Use existing FakeRedis unit tests unless E2E requested |
| Database | DB/E2E only if data path touched | not probed | — | Skip if code-only order validation change |

**Missing dependencies with no fallback:** none for targeted unit validation. [VERIFIED: local CLI]

## Security Domain

No authentication/session/cryptography surface is introduced by this quick task. Input validation still applies: validate `entry_method`, `pivot_index`, and numeric entry/SL/TP values before creating an order, and reject invalid inputs rather than fallback silently. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | DB/E2E can be skipped if implementation does not modify DB writer/schema/journal persistence and only changes order validation/rejection behavior. [ASSUMED] | Validation Architecture | If order streams are considered “luồng tạo/sửa data”, planner may need a DB E2E run even without DB code changes. |

## Open Questions

1. **Should `PULLBACK_50` use newest LL/HH or exact CHOCH pivot from trigger progress?**
   - What we know: TODO asks nearest unbroken LL/HH; tmp reference uses newest matching swing point by time. [VERIFIED: D:/Aureus/services/aureus-signal/engine/orders.py] [VERIFIED: D:/Aureus/tmp/simulated_orders.py]
   - What's unclear: Whether trigger `progress` tag should constrain pivot to the CHOCH event.
   - Recommendation: Use nearest unbroken LL/HH for this quick task; do not parse `progress` unless tests reveal necessity. [ASSUMED]

## Sources

### Primary (HIGH confidence)
- `D:/Aureus/services/aureus-signal/engine/orders.py` — target TODOs, reject flow, pivot helpers.
- `D:/Aureus/.planning/quick/260427-v5g-implement-c-c-ph-n-todo-v-c-c-ph-n-ch-a-/260427-v5g-CONTEXT.md` — locked behavior decisions.
- `D:/Aureus/CLAUDE.md` — GitNexus, DB/E2E, surgical-change constraints.
- `D:/Aureus/services/aureus-signal/engine/snapshot_utils.py` — entry method constants and order plan required keys.
- `D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py` — `ENTRY_PIVOT_LIMIT` live strategy configs.
- `D:/Aureus/services/aureus-signal/tests/test_entry_price_methods.py` and `D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py` — existing tests requiring updates.

### Secondary (MEDIUM confidence)
- `D:/Aureus/tmp/simulated_orders.py` — historical/reference implementation for pivot-based pullback and pivot-limit semantics.

## Metadata

**Confidence breakdown:**
- TODO scope: HIGH — direct target file read.
- Integration points: HIGH — direct code/tests read.
- Implementation details for pullback formula: MEDIUM-HIGH — supported by TODO wording and tmp reference, but exact CHOCH-progress binding remains unclear.
- Validation: HIGH for unit tests, MEDIUM for DB/E2E skip decision.

**Research date:** 2026-04-27
**Valid until:** 2026-05-04
