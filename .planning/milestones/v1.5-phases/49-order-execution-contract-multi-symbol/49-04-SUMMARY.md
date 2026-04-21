---
phase: 49-order-execution-contract-multi-symbol
plan: 04
type: execute-summary
focus: [ORDER-01, ORDER-02, PH45-05, PH45-06]
files_modified:
  - services/aureus-nautilus-node/execution_client.py
  - services/aureus-nautilus-node/tests/test_execution_client.py
verification:
  - python -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py D:/Aureus/services/aureus-nautilus-node/tests/test_execution_risk_controls.py D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py -q
result: pass
completed: 2026-04-20
---

# 49-04 Summary

## Blast radius (pre-edit)
- Symbol: `_validate_and_build_orders`
- Risk: **CRITICAL**
- d=1 direct caller: `_handle_message`
- d=2: `_poll_orders_once`
- d=3: `_poll_loop`
- Affected processes: 5

## Changes delivered
- Chuẩn hóa critical-field reject về reason code ổn định: `ORDER_OPEN_MISSING_CRITICAL_FIELD` khi thiếu `trace_id|symbol|side|qty` (bao gồm thiếu cả `qty` và `quantity`).
- Hỗ trợ alias volume: ưu tiên `qty`, fallback `quantity`.
- Giữ strict idempotency `DUPLICATE_TRACE_ID`.
- Parse `sl/tp` an toàn, reject `INVALID_SL_TP` thay vì gây crash.
- Bổ sung metric `order_open_optional_fallback_total` theo test contract hiện có.
- Điều chỉnh test polling để truyền streams explicit, khớp behavior hiện tại của `_poll_orders_once`.
- Giữ guard `SYMBOL_STREAM_MISMATCH` không regress.

## Verification
- `test_execution_client.py`, `test_execution_risk_controls.py`, `test_execution_client_policy.py` chạy cùng lượt: **11 passed**.

## Notes
- `gitnexus detect-changes` CLI không có trong môi trường hiện tại (`unknown command 'detect-changes'`).
- Chưa thực hiện commit trong lượt này.
