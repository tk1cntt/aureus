---
phase: 09
plan: 01
subsystem: signal-structure
status: planned
tags: [validation, gatekeeper, pytests, coverage]

requires:
  - plan: 09-01-PLAN.md
---

# `09-VALIDATION.md`

## Testing Strategy
Bởi vì "Core Structure" không thể chạm, nên chiến lược Test của Mốc 9 dồn 80% tài nguyên vào phép thử chống xâm phạm (Snapshot Testing) thay vì Blackbox TDD truyền thống. Traceability Integration Test sẽ đóng vai trò như chốt chặn cuối cùng chứng minh Dữ liệu của Signal Factory v1.1 đã đồng bộ toàn phần.

## Per-Task Verification Map

| Task ID | Plan | Requirement | Test Type | Automated Command | Status |
|---------|------|-------------|-----------|-------------------|--------|
| 09-01-01 | 01 | SIG-09 | snapshot | `python -m pytest services/aureus-signal/tests/test_structure_o1.py -q` | ⏳ planned |
| 09-01-04 | 01 | TST-02 | integration | `python -m pytest services/aureus-signal/tests/test_structure_integration_execute_signals_for_candle.py -q` | ⏳ planned |
| 09-01-05 | 01 | TST-03,TST-04 | coverage + gate | `python -m pytest services/aureus-signal/tests/test_structure_o1.py services/aureus-signal/tests/test_structure_integration_execute_signals_for_candle.py --cov=services/aureus-signal/engine/signals/structure.py --cov-report=term-missing -q` | ⏳ planned |

## Validation Sign-Off

- [ ] Golden Master Unit Test ghi nhận 100% khớp dữ liệu logic cũ (Data Parity Validated).
- [ ] Vòng lặp Mitigation được xác thực giảm chi phí cắt khung (Slicing Bounds Asserted).
- [ ] Traceability Integration payload chứa `ob_state` mà không gây hiệu ứng phụ.
- [ ] Coverage gate command passes (>80%).
- [ ] Phase closure only after all gates are green.
