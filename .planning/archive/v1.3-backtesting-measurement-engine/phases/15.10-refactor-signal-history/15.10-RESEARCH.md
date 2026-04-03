# Phase 15.10: Contract reconciliation before typed refactor — Research

## Objective
Khoanh vùng drift contract `log_signal` và xác định lộ trình reconcile an toàn trước khi tiếp tục typed refactor.

## Scope
- `state.log_signal` signature và payload normalization
- Runtime call-sites ghi signal trong live/backtest/precompute
- Snapshot/consumer compatibility sau reconcile

## Symptom Decomposition
1. **Signature drift:** state layer legacy, call-sites metadata-aware.
2. **Payload drift:** bản ghi lịch sử không đồng nhất field set.
3. **Compatibility drift:** consumer có thể gặp shape không mong đợi.
4. **Execution risk:** mismatch dễ gây lỗi runtime trong loop chính.

## Key Pipeline Evidence (Current Code)
- `services/aureus-signal/engine/state.py`
- `services/aureus-signal/engine/live_engine.py`
- `services/aureus-signal/engine/backtest_engine.py`
- `services/aureus-signal/signal_computer.py`
- `services/aureus-signal/engine/state_snapshot.py`
- `services/aureus-signal/engine/ai_validator.py`

## Prioritized Hypotheses
1. Canonical contract tại state layer sẽ giảm đa số drift downstream.
2. Reconcile call-sites toàn cục trước giúp tránh fix chắp vá theo từng loop.
3. Snapshot normalization là safeguard quan trọng cho backward compatibility.

## Investigation Outputs Required for Planning
- Quyết định contract canonical (shape + fallback rules).
- Checklist call-site reconciliation theo file.
- Verification set cho tests contract/snapshot + runtime smoke.

## Research Outcome
Phase 15.10 nên đi theo hướng **reconciliation-first** rồi mới tiếp tục typed-model migration, tránh refactor sâu trên nền contract chưa ổn định.
