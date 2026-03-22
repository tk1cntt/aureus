# Phase 12: Handle Multi-OB Mitigation Events - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Chuẩn hóa hành vi mitigation event trong `structure` theo hướng deterministic **last-event-wins** cho mỗi candle: giữ nguyên contract hiện tại (`ob_bull_mitigated`, `ob_bear_mitigated`), không mở rộng schema aggregate list, không thay đổi snapshot model hiện tại.

</domain>

<decisions>
## Implementation Decisions

### Event Contract Shape
- **D-01:** Giữ nguyên 2 key hiện tại trong `transient_signals`: `ob_bull_mitigated` và `ob_bear_mitigated`.
- **D-02:** Không thêm key list mới (`*_events`).

### Last-Event-Wins Semantics
- **D-03:** Nếu trong cùng 1 candle có nhiều mitigation cùng phía, key legacy sẽ giữ **event cuối cùng**.
- **D-04:** Đây là behavior chủ đích (deterministic), chấp nhận tradeoff không lưu toàn bộ event trước đó trong cùng candle.

### Snapshot & Event Filter Behavior
- **D-05:** Snapshot `events` giữ nguyên format hiện tại; không mở rộng payload multi-event.
- **D-06:** `event_filter` tiếp tục nhận diện structural event qua key legacy hiện có, không cần tag mới.

### AI Update Trigger Rule
- **D-07:** AI update trigger theo semantics event cuối cùng (không trigger theo từng mitigation bị overwrite).

### the agent's Discretion
- Cách viết test để chứng minh `last-event-wins` rõ ràng nhất.
- Mức độ refactor nội bộ trong `_verify_mitigations` miễn không đổi contract đã chốt.

</decisions>

<specifics>
## Specific Ideas

- Ưu tiên tính ổn định contract cho consumer đang chạy production hơn việc mở rộng schema.
- Mục tiêu phase này là chuẩn hóa hành vi overwrite thành quyết định rõ ràng, không phải mở rộng tính năng event history.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and Phase Scope
- `.planning/archive/v1.1-signal-optimization/ROADMAP.md` — Nguồn scope chính thức cho Phase 12.
- `.planning/archive/v1.1-signal-optimization/phases/10-phan-tich-toi-uu-sweep-targets/10-CONTEXT.md` — Bối cảnh trước đó của logic `structure/sweep`.

### Engine Runtime Contracts
- `services/aureus-signal/engine/signals/structure.py` — Nơi phát `ob_*_mitigated` và xử lý mitigation loop.
- `services/aureus-signal/engine/event_filter.py` — Structural event tags cho snapshot trigger.
- `services/aureus-signal/engine/live_engine.py` — Flow sử dụng transient events cho runtime/snapshot.
- `services/aureus-signal/engine/state.py` — Cơ chế `request_ai_update` và dedup semantics.
- `services/aureus-signal/engine/snapshot_utils.py` — Build snapshot payload từ `transient_signals`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_verify_mitigations` trong `structure.py`: điểm trung tâm để enforce last-event-wins behavior.
- `has_structural_event(...)` trong `event_filter.py`: đã phù hợp với key legacy hiện tại.

### Established Patterns
- Transient signal contract đang dùng key đơn cho từng event type (không list aggregate).
- Runtime hiện ưu tiên backward compatibility để tránh break dashboard/consumer.

### Integration Points
- `structure.py` phát event -> `live_engine.py` đọc event -> `snapshot_utils.py` persist event snapshot.
- `state.request_ai_update(...)` nhận trigger từ signal flow theo semantics hiện hành.

</code_context>

<deferred>
## Deferred Ideas

- Mở rộng aggregate multi-event (`ob_*_mitigated_events`) để giữ full mitigation history trong cùng candle — deferred cho phase tương lai nếu business cần.

</deferred>

---

*Phase: 12-handle-multi-ob-mitigation-events*
*Context gathered: 2026-03-22*
