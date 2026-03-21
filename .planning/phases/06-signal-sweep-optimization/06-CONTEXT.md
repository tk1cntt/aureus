# Phase 6: Signal Sweep Optimization - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Tối ưu và xác thực `sweep` signal trong phạm vi `SIG-06` theo hướng **correctness-first** và **không đổi trading intent**.

Trọng tâm phase này:
- Harden `sweep` runtime behavior (guardrails, deterministic flow, state safety).
- Giữ ổn định contract downstream (`sweep_bull`/`sweep_bear`) cho `event_filter` và outlet signals.
- Bổ sung test coverage chuyên biệt để giảm regression risk.

Ngoài phạm vi phase này:
- Đổi public contract/payload schema của `sweep`.
- Rework heuristic chọn target từ `structure`.

</domain>

<decisions>
## Implementation Decisions

### 1) Sweep Contract & Dedup Policy
- **Locked: A**
- Giữ nguyên contract hiện tại:
  - tags: `sweep_bull`, `sweep_bear`
  - payload chính: `tag`, `t`, `price_swept`, `source_type`, `source_t`, `fidelity`, `market_regime`
  - transient emission: ghi vào `state_obj.transient_signals[tag]`
- Giữ dedup theo `signal_history` tại cùng candle/target để tránh emit trùng.

### 2) Target Lifecycle (`state_obj.sweep_targets`)
- **Locked: A**
- Giữ mô hình hiện tại: tối đa **1 sweep trigger / candle**.
- Target đã sweep thì bị loại khỏi danh sách active; target chưa sweep giữ lại.
- Ưu tiên deterministic replay parity, tránh multi-fire side effects.

### 3) Regime Filter Strictness
- **Locked: A**
- Giữ rule lọc regime hiện tại:
  - Bullish sweep chỉ cho `TREND_UP` hoặc `SIDEWAYS`
  - Bearish sweep chỉ cho `TREND_DN` hoặc `SIDEWAYS`
- Không nới lỏng thành all-regime trong phase này.

### 4) Test Gate Posture
- **Locked: A**
- Bổ sung dedicated test pack cho Phase 06 gồm:
  - Unit test file sweep-focused
  - Integration test file qua signal execution path
  - Event-filter/runtime-path assertions cho transient structural tags
  - Coverage gate theo phase (`>= 80%` theo roadmap; tôn trọng gate hiện hữu của repo)

### 5) Scope Posture
- **Locked: A (Conservative Hardening)**
- Không thay đổi semantics sweep hoặc trading intent.
- Tập trung harden guard/validation/testability, giữ backward-compatible behavior.

### Claude's Discretion
- Thiết kế test matrix chi tiết cho malformed targets, dedup, regime-gated sweeps, single-trigger-per-candle.
- Mức hardening nội bộ (null/shape/type guards, logging clarity) miễn không đổi public contract.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and traceability
- `.planning/ROADMAP.md` — Phase 06 mapping, requirements, success criteria.
- `.planning/REQUIREMENTS.md` — `SIG-06`, `TST-01..04`, `VAL-01..02`.
- `.planning/STATE.md` — Current milestone progression.

### Sweep implementation and integration contracts
- `services/aureus-signal/engine/signals/sweep.py` — Sweep producer, dedup, target lifecycle.
- `services/aureus-signal/engine/signals/sweep_bull.py` — Bullish outlet consumer.
- `services/aureus-signal/engine/signals/sweep_bear.py` — Bearish outlet consumer.
- `services/aureus-signal/engine/signal_factory.py` — Wiring order (`sweep_processor` trước outlet signals).
- `services/aureus-signal/engine/event_filter.py` — Structural tags (`sweep_bull`, `sweep_bear`) trigger path.
- `services/aureus-signal/engine/signals/structure.py` — Sweep target registration (`_register_sweep_targets`).
- `services/aureus-signal/engine/state.py` — `sweep_targets` state container.

### Existing tests/baselines
- `services/aureus-signal/tests/test_signal_contract_normalization.py` — Guardrail baseline cho malformed sweep target.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SweepSignal` đã có producer flow hoàn chỉnh: detect sweep, dedup, transient emit, AI update trigger.
- `SweepBullSignal`/`SweepBearSignal` đã tách outlet consumption rõ ràng.

### Established Patterns
- Producer signal ghi transient events để outlet signals và event filter consume cùng candle.
- Structural tags dùng để quyết định snapshot persistence.
- State-driven processing ưu tiên replay consistency qua `state_obj`.

### Integration Risk Points
- Drift contract ở `sweep.py` có thể làm hỏng `event_filter` sparse snapshot trigger.
- Nới lỏng regime hoặc multi-trigger/candle có thể tạo signal noise và side effects downstream.
- Thiếu dedicated tests cho sweep làm tăng regression risk khi harden code.

</code_context>

<deferred>
## Deferred Ideas

- Đổi payload schema hoặc rename tag contracts của sweep.
- Multi-sweep emission trong cùng candle.
- Rework thuật toán chọn `sweep_targets` bên `structure`.

</deferred>

---

*Phase: 06-signal-sweep-optimization*
*Context gathered: 2026-03-21*
