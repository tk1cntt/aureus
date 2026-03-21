# Phase 5: Signal Session Optimization - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Tối ưu và xác thực `session` signal trong phạm vi `SIG-05` theo hướng correctness-first, giữ deterministic behavior, và **không đổi trading intent**.

Trọng tâm phase này:
- Chuẩn hóa xác định session theo khung giờ business đã chốt ở **GMT+7**.
- Mapping đúng từ timestamp MT5 (broker time context) sang cửa sổ session của user để tránh lệch giờ.
- Giữ ổn định contract runtime cho các thành phần downstream đọc `current_session`.

Ngoài phạm vi phase này:
- Thiết kế lại chiến lược trading theo session.
- Thay đổi semantics tổng thể của các judge/strategy downstream.

</domain>

<decisions>
## Implementation Decisions

### Locked Choices
- User đã chốt: **1A, 2A, 3A, 4A** (theo bộ lựa chọn của `gsd-discuss-phase 5`).
- Nguyên tắc triển khai: ưu tiên phương án A cho toàn bộ decision points đã thảo luận.

### Session Windows (User Baseline - GMT+7)
- `ASIA`: `07:00-11:00`
- `LONDON`: `14:00-17:00`
- `NEW_YORK`: `19:00-23:00`
- Ngoài các khung trên: `LUNCH_TIME` (hoặc off-window tương đương theo contract hiện tại)

### Time Mapping Rule (Critical)
- Timestamp nhận từ MT5 phải được mapping đúng sang broker-time reference, sau đó quy chiếu về mốc giờ dùng để phân loại session.
- Mục tiêu: tránh lệch session khi broker DST thay đổi (GMT+2/GMT+3).
- Không hardcode suy diễn mâu thuẫn với timestamp thực tế của nến.

### Contract Stability
- Giữ output signal `tag = market_session`.
- Giữ cập nhật `state_obj.current_session` ổn định cho toàn bộ consumer downstream.
- Giữ cấu trúc `tracking_vars['session_hlo']` tương thích ngược.

### Claude's Discretion
- Cách hardening guard cho boundary time, DST boundary, và empty/malformed input.
- Tổ chức test matrix chi tiết miễn đạt gate chất lượng phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and requirements
- `.planning/ROADMAP.md` — phase mapping và success criteria phase 5.
- `.planning/REQUIREMENTS.md` — `SIG-05`, `TST-01..04`, `VAL-01..02`.
- `.planning/PROJECT.md` — mục tiêu milestone: deterministic + accuracy-first.

### Session implementation
- `services/aureus-signal/engine/signals/session.py` — logic phân loại session, DST, state updates.
- `services/aureus-signal/engine/signal_factory.py` — wiring `SessionSignal`.
- `services/aureus-signal/engine/state.py` — `current_session` default/contract.

### Downstream consumers
- `services/aureus-signal/engine/strategies/trend_continuation.py` — session-aware strategy branch.
- `services/aureus-signal/engine/strategies/order_flow_dominance.py` — session-aware scoring/logic.
- `services/aureus-signal/engine/logic/judges/structure.py` — session-dependent judge behavior.
- `services/aureus-signal/engine/state_snapshot.py` — snapshot serialize/restore `current_session`.
- `services/aureus-signal/engine/snapshot_utils.py` — snapshot payload session field.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SessionSignal` đã có DST detection và state enrichment.
- Pipeline đã có wiring session signal trong signal factory.

### Risk Points
- Lệch giờ tại DST boundary có thể làm sai session classification.
- Sai inclusive/exclusive boundary có thể gây churn session shift không mong muốn.
- Regression ở `current_session` có thể ảnh hưởng nhiều strategy/judge.

### Test Gap Observed
- Chưa thấy dedicated session-focused test file trong `services/aureus-signal/tests`.
- Cần bổ sung test coverage có chủ đích cho phase 05 để đạt gate.

</code_context>

<deferred>
## Deferred Ideas

- Mở rộng session taxonomy beyond ASIA/LONDON/NEW_YORK.
- Dynamic per-symbol session profile và holiday calendar modeling.

</deferred>

---

*Phase: 05-signal-session-optimization*
*Context gathered: 2026-03-21*
