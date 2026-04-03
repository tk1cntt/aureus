---
phase: 15.10
slug: refactor-signal-history-contract-reconciliation
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-27
updated: 2026-03-28
---

# Phase 15.10 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest + runtime smoke review |
| Config file | existing service test configuration |
| Quick run command | `pytest tests/test_signal_contract_normalization.py tests/test_decision_trace_schema.py -q` |
| Full suite command | `pytest tests/test_signal_contract_normalization.py tests/test_decision_trace_schema.py tests/test_state_snapshot.py tests/test_sweep_integration_execute_signals_for_candle.py tests/test_sweep_integration_live_engine.py tests/test_sweep_o1.py -q` |
| Estimated runtime | ~60-180s |

## Sampling Rate
- Sau mỗi task Plan 01/02: chạy quick command
- Sau mỗi task Plan 03: chạy test command theo map bên dưới
- Trước handoff: full suite command + smoke runtime path phải xanh

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|
| 15.10-01-T1 | 01 | 1 | Canonical contract definition | contract-focused | `pytest tests/test_signal_contract_normalization.py -q` | ✅ | ⬜ pending |
| 15.10-01-T2 | 01 | 1 | Runtime call-site reconciliation | integration-focused | `pytest tests/test_decision_trace_schema.py -q` | ✅ | ⬜ pending |
| 15.10-01-T3 | 01 | 1 | Snapshot + consumer compatibility | restore/compatibility | `pytest tests/test_state_snapshot.py -q` | ✅ | ⬜ pending |
| 15.10-03-T1 | 03 | 1 | Migrate `market_regime` → `htf_trend` | contract + grep-scope | `pytest tests/test_signal_contract_normalization.py -q` + `rg -n "market_regime|htf_trend" services/aureus-signal/engine services/aureus-signal/tests` | ✅ | ⬜ pending |
| 15.10-03-T2 | 03 | 1 | Sweep/MITIGATED event không bị mất | signal integration | `pytest tests/test_sweep_integration_execute_signals_for_candle.py tests/test_sweep_integration_live_engine.py tests/test_sweep_o1.py -q` | ✅ | ⬜ pending |
| 15.10-03-T3 | 03 | 1 | Regression coverage + output contract | full regression | `pytest tests/test_signal_contract_normalization.py tests/test_sweep_integration_execute_signals_for_candle.py tests/test_sweep_integration_live_engine.py tests/test_sweep_o1.py -q` | ✅ | ⬜ pending |

## Wave 0 Requirements
- Existing tests/fixtures available
- Không cần thêm dependency hoặc framework mới

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Runtime loop không còn lỗi kwargs/signature mismatch | Internal contract reconciliation | Cần quan sát execution path thực | Chạy loop live/backtest ngắn, kiểm tra logs + serialized state |
| Event `MITIGATED` và sweep xuất hiện trong `signal_history_normalized` khi `choch down` | Internal sweep observability | Cần xác nhận theo sequence candle thực tế | Chạy replay/backtest ngắn với case có OB mitigation + sweep, đối chiếu state output |

## Validation Sign-Off
- [x] Có mapping verify cho mọi task của plan 01
- [x] Có quick/full command rõ ràng, không watch-mode
- [x] Wave 0 không thiếu dependency
- [x] `nyquist_compliant: true` đã set
- [x] Đã bổ sung verification map riêng cho plan 03 (T1/T2/T3)
- [ ] Approval: pending execution evidence
