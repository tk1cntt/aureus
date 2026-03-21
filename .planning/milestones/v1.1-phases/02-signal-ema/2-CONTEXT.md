# Phase 2: Signal EMA Optimization - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Tối ưu và xác thực `ema` signal trong phạm vi `SIG-02` để giữ nguyên trading intent, đảm bảo deterministic behavior, và đóng đủ quality gates của phase (unit + integration + coverage >= 80%).

</domain>

<decisions>
## Implementation Decisions

### EMA contract output
- Chọn **A**: giữ contract event/tag hiện có (`ema_{period}_up`, `ema_{period}_down`, cross tags) để tránh breaking behavior downstream.
- Ưu tiên parity trước khi tối ưu thêm.

### Calculation path strategy
- Chọn **A**: tiếp tục mô hình warmup batch (`ewm`) + incremental O(1) sau warmup.
- Không thay đổi business semantics; chỉ harden correctness/perf trong cùng behavior.

### State handling policy
- Chọn **A**: chuẩn hóa đọc/ghi `state_obj.emas[period]` theo cấu trúc hiện tại (`current`, `prev`, `slope`) và bổ sung guard an toàn tối thiểu.
- Tránh refactor lớn protocol state ở phase này.

### Test gate strategy
- Chọn **A**: ưu tiên dedicated unit + integration theo `TST-01..04`, đảm bảo coverage gate >= 80% cho scope thay đổi EMA.
- Chỉ đóng phase khi toàn bộ gates pass.

### Claude's Discretion
- Cách tổ chức test cases chi tiết cho edge cases (warmup boundary, empty input, cached-key fallback).
- Mức hardening nội bộ (log/guard) miễn không đổi contract output.

</decisions>

<specifics>
## Specific Ideas

- User chọn toàn bộ phương án **A** cho các điểm quyết định của `/gsd-discuss-phase 2`.
- Ưu tiên ổn định contract và deterministic parity trước khi mở rộng tối ưu sâu.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and traceability
- `.planning/ROADMAP.md` — Phase mapping, success criteria structure, và thứ tự phase.
- `.planning/REQUIREMENTS.md` — `SIG-02`, `TST-01..04`, `VAL-01..02` quality gates và traceability.
- `.planning/PROJECT.md` — Milestone goal: correctness-first, deterministic behavior.
- `.planning/STATE.md` — Current planning state and phase progression notes.

### EMA implementation baseline
- `services/aureus-signal/engine/signals/ema.py` — Current EMA logic, tags, warmup/incremental path, state writeback.
- `services/aureus-signal/engine/signals/base.py` — Base signal contract (`calculate(df, state_obj, **kwargs)`).
- `services/aureus-signal/tests/test_ema_o1.py` — Existing O(1) parity validation against pandas `ewm`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EMASignal` (`engine/signals/ema.py`): đã có nhánh warmup + O(1), có thể harden trực tiếp thay vì tạo signal mới.
- `BaseSignal` (`engine/signals/base.py`): contract chung cho signal implementations.

### Established Patterns
- Signals trả `dict` metadata với `tag` và optional `cross`.
- State được cache theo từng signal trong `state_obj` để hỗ trợ incremental compute.
- Test parity pattern đã có sẵn qua so sánh với pandas `ewm` trên từng step.

### Integration Points
- Engine signal registry/runtime sẽ tiếp tục consume output tag contract hiện tại từ `ema.py`.
- Phase 02 cần bổ sung/duy trì dedicated integration coverage trong `services/aureus-signal/tests` theo roadmap gate.

</code_context>

<deferred>
## Deferred Ideas

- Mọi thay đổi làm đổi naming/tag contract EMA hoặc refactor lớn state protocol được defer sang phase riêng nếu cần.

</deferred>

---

*Phase: 02-signal-ema*
*Context gathered: 2026-03-20*
