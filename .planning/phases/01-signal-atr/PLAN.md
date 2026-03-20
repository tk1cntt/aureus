# Phase 1 Plan — Signal ATR Optimization

## Scope
- Signal: `atr`
- Objective: hoàn tất correctness + integration hardening cho ATR trước khi mở Phase 2 (`ema`).

## Executed Work Plan
1. **Factory wiring fix**
   - Đăng ký `atr_14` đúng trong `engine/signal_factory.py::create_signal_set(...)`.
2. **Integration test hardening**
   - Bổ sung/điều chỉnh test để chạy qua wiring thật, tránh patch factory cho ATR path.
3. **Contract alignment**
   - Đồng bộ assert `signal_history` theo schema runtime (`t`).
4. **Regression guard**
   - Duy trì test contract cho factory + helper-level + runtime-path.
5. **Governance update**
   - Cập nhật process rule: không xóa test case legacy.

## Deliverables
- ATR được wire đầy đủ vào factory.
- Bộ test integration không còn masking wiring issue.
- Process tài liệu hóa anti-masking + no-deletion rule cho legacy tests.
