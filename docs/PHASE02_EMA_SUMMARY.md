# PHASE02_EMA_SUMMARY

Nguồn chuẩn: `.planning/phases/02-signal-ema/02-01-SUMMARY.md`
Ngày export: 2026-03-21 (+07)

## Kết quả chính
- Harden `EMASignal.calculate` cho fallback path khi state/cache malformed.
- Giữ nguyên output contract (tag/cross/period/value/t), không đổi semantics.
- Bổ sung integration test riêng cho flow `execute_signals_for_candle + WindowManager + EMASignal(21)`.

## File thay đổi trọng yếu
- `services/aureus-signal/engine/signals/ema.py`
- `services/aureus-signal/tests/test_ema_o1.py`
- `services/aureus-signal/tests/test_ema_integration_execute_signals_for_candle.py`
- `.planning/phases/02-signal-ema/02-VALIDATION.md`

## Validation
- Focused tests pass theo evidence trong `02-VALIDATION.md`
- Coverage trọng yếu: `engine/signals/ema.py = 92%` (vượt gate >=80%)

## Decision/Pattern chốt
- EMA contract hiện tại là non-negotiable để tránh break downstream.
- Integration regression là blocking kể cả khi unit test còn xanh.

## Trạng thái bàn giao
- Phase 02 hoàn tất, sẵn sàng handoff sang Phase 03 (FVG).
