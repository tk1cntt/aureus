# Phase 15.9: Enrich signal_history with semantic metadata — Research

## Objective
Xác định điểm cần chuẩn hóa contract metadata để tăng khả năng AI narrative/debug mà không phá compatibility cho pipeline hiện hữu.

## Scope
- `signal_history` producer path (signals → engine call-sites → `state.log_signal`)
- Consumer path (`ai_validator`, snapshot serialize/restore)
- Không mở rộng sang refactor Pydantic đa hình toàn diện (thuộc 15.10+)

## Symptom Decomposition
1. **Producer drift:** calculators/call-sites không thống nhất keys metadata.
2. **State contract drift:** `log_signal` chưa nhất quán giữa các runtime loop.
3. **Consumer ambiguity:** narrative/snapshot path cần fallback khi metadata thiếu.
4. **Compatibility risk:** mọi thay đổi phải giữ `tag`, `t` cho legacy readers.

## Key Pipeline Evidence (Current Code)
- `services/aureus-signal/engine/state.py`
  - Trục contract chính của `signal_history`
- `services/aureus-signal/engine/live_engine.py`
- `services/aureus-signal/engine/backtest_engine.py`
- `services/aureus-signal/signal_computer.py`
  - Các call-sites ghi signal trong live/backtest/precompute
- `services/aureus-signal/engine/ai_validator.py`
- `services/aureus-signal/engine/state_snapshot.py`
  - Consumer + persistence/restore path cần đọc metadata an toàn

## Prioritized Hypotheses
1. Chuẩn hóa contract tại state layer trước sẽ giảm phần lớn drift downstream.
2. Đa số regression đến từ call-site signature mismatch hơn là logic signal core.
3. Snapshot normalization là điểm chốt để giữ metadata qua vòng serialize/restore.

## Investigation Outputs Required for Planning
- Canonical metadata contract và fallback matrix.
- Danh sách call-sites cần reconcile theo mức ưu tiên.
- Verification matrix cho tests contract/snapshot + smoke runtime.

## Research Outcome
Phase 15.9 nên đi theo hướng **contract-first + compatibility-first**: chốt shape record, đồng bộ producer, rồi cập nhật consumer/snapshot với fallback rõ ràng.
