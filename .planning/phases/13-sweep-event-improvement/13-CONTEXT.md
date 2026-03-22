# Phase 13: Sweep Event Improvement - Context

**Gathered:** 2026-03-22
**Updated:** 2026-03-22 (runtime flow clarified + deprecation roadmap)
**Status:** Plan/context synchronized for execution

<domain>
## Phase Boundary

Chuẩn hóa state machine của `sweep` theo mô hình mỗi trạng thái là một thế đánh riêng và đồng bộ event contract theo status.

Bổ sung boundary kiến trúc:
- `has_structural_event` chỉ là gate cho snapshot/conditional sync.
- AI trigger không phân tán trong signal processors; gom về một policy tập trung ở runtime engine.

</domain>

<decisions>
## Implementation Decisions

### Sweep Status Model
- **D-01:** Bộ trạng thái chuẩn gồm: `PENDING`, `TOUCHED`, `SWEEP`, `BROKEN_PENDING`, `STOP_HUNT`, `DEAD`.
- **D-02:** `STOP_HUNT` là trạng thái giao dịch riêng, không chỉ là tag event.

### Event Contract
- **D-03:** Bỏ hẳn `OB_STATE_CHANGE`.
- **D-04:** Mỗi state phát event theo format status-key trong `transient_signals` (ví dụ `sweep_stop_hunt`, `sweep_dead`).
- **D-05:** Mỗi status đại diện một thế đánh khác nhau và downstream xử lý theo state đó.

### Runtime Orchestration (Locked)
- **D-13:** Signal processors (`sweep.py`, `structure.py`) chỉ emit domain events vào `transient_signals`; không gọi `request_ai_update(...)` trực tiếp.
- **D-14:** Thêm policy tập trung tại engine để map event -> AI trigger codes theo tick.
- **D-15:** `has_structural_event` giữ vai trò snapshot gate, không kiêm logic trigger AI.
- **D-16:** Điểm gọi `request_ai_update(...)` duy nhất nằm ở orchestration path trong `live_engine.py`.

### Deprecation Roadmap
- **D-17 (Phase A):** Giữ `state.request_ai_update` như compatibility API; signal layer không còn gọi trực tiếp.
- **D-18 (Phase B):** Khi callsites ổn định, đổi tên/internalize hoặc xóa API legacy.

### Downstream Compatibility (Locked)
- **D-08 (1B):** `transient_signals` dùng key theo status.
- **D-09 (2B):** AI trigger events do policy trung tâm quyết định tại runtime.
- **D-10 (3B):** `event_filter.STRUCTURAL_TAGS` mở rộng để nhận status-tags mới của sweep.
- **D-11 (4A):** **Không migration window** — cutover trực tiếp sang format mới trong Phase 13.
- **D-12 (5A):** Giữ nguyên cách snapshot serialize `events` (dump `transient_signals.values()`), chỉ thay nội dung event theo schema mới.

### Transition Semantics
- **D-06:** `BROKEN_PENDING` chuyển `STOP_HUNT` nếu 1–2 nến sau reclaim lại OB.
- **D-07:** `BROKEN_PENDING` chuyển `DEAD` nếu 2 nến sau vẫn ở ngoài OB.

</decisions>

<specifics>
## Specific Ideas

- User xác nhận mong muốn gom xử lý event trigger về 1 chỗ để tránh phân tán giữa `structure` và `sweep`.
- User xác nhận vẫn giữ logic status-based sweep contract của Phase 13.
- User yêu cầu plan/context phải chỉ rõ phần nào xử lý event sau khi đã emit vào `transient_signals`.

</specifics>

<canonical_refs>
## Canonical References

### Scope and prior context
- `.planning/archive/v1.1-signal-optimization/ROADMAP.md`
- `.planning/archive/v1.1-signal-optimization/phases/10-phan-tich-toi-uu-sweep-targets/10-CONTEXT.md`
- `.planning/archive/v1.1-signal-optimization/phases/12-handle-multi-ob-mitigation-events/12-CONTEXT.md`

### Runtime implementation targets
- `services/aureus-signal/engine/signals/sweep.py`
- `services/aureus-signal/engine/signals/structure.py`
- `services/aureus-signal/engine/event_filter.py`
- `services/aureus-signal/engine/live_engine.py`
- `services/aureus-signal/engine/state_snapshot.py`
- `services/aureus-signal/engine/snapshot_utils.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SweepSignal._update_ob_states(...)` là hook trung tâm cho sweep transitions.
- `state.request_ai_update(...)` đã có aggregation behavior (`ai_update_pending`, `ai_trigger_events`).
- `live_engine.run_signal_engine(...)` đã có vị trí orchestration phù hợp để đặt policy tập trung.

### Established Patterns
- `transient_signals` là bus event theo tick (producer-consumer) và được clear mỗi nến.
- `has_structural_event(...)` dùng để quyết định snapshot/redis sync path.
- Snapshot persistence đang serialize `transient_signals.values()`.

### Integration Points
- `signals/*` emit event -> `transient_signals`
- `live_engine` evaluate event policy -> `request_ai_update`
- `event_filter` evaluate persistence event significance
- `state_snapshot`/`snapshot_utils` persist event payloads

</code_context>

<deferred>
## Deferred Ideas

- Nếu cần scoring/priority AI trigger (multi-event conflict resolution), tách thành phase tiếp theo để tránh nở scope.

</deferred>

---

*Phase: 13-sweep-event-improvement*
*Context updated: 2026-03-22*
