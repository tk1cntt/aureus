# Phase 2 Summary — Signal EMA Optimization

## Goal
Hoàn tất tối ưu và hardening cho EMA signal theo plan `02-01`, giữ nguyên output contract runtime và đóng đầy đủ gate verification của phase.

## Completed
- Hardened `EMASignal.calculate` path để xử lý cache malformed/missing keys an toàn, vẫn giữ contract output (`tag`, optional `cross`, `period`, `value`, `t`).
- Bổ sung integration test riêng cho runtime path `execute_signals_for_candle` + `WindowManager` + `EMASignal(21)`.
- Mở rộng unit test fallback cho malformed cache.
- Cập nhật validation evidence: focused gate pass + coverage `engine/signals/ema.py = 92%`.
- Xác nhận collection blocker follow-up command (`test_multi_symbol` + `test_strategy_contract_v1`) đã xanh.

## Acceptance Status
- Phase 2 EMA: **Done**
- Verification: **Pass** (`6 passed`, coverage `92%`)

## Handoff to Phase 3
- Next phase: `03-signal-fvg`
- Keep same guard rails: runtime contract stability + dedicated integration test + per-phase evidence isolation.
- Continue policy: maintain phase-local docs (`RESEARCH`, `PLAN`, `VALIDATION`, `SUMMARY`, `UAT`).
