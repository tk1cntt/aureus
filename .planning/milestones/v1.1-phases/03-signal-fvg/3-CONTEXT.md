# Phase 3: Signal FVG Optimization - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Tối ưu và xác thực `fvg` signal trong phạm vi `SIG-03` theo hướng accuracy-first, giữ deterministic behavior, và **backward-compatible hoàn toàn** với runtime integrations + strategy evaluation hiện tại.

</domain>

<decisions>
## Implementation Decisions

### FVG contract shape
- Chọn **1C**: giữ **đồng thời** 2 kênh contract để đảm bảo backward-compatible:
  1) **Transient event keys** dùng cho integration filter/runtime snapshot:
     - `fvg_bull_new`, `fvg_bear_new`, `fvg_bull_mitigated`, `fvg_bear_mitigated`
  2) **Signal tags** dùng cho strategy sequence/history:
     - `fvg_up`, `fvg_down`
- Không rename public contract hiện có trong phase này; chỉ chuẩn hóa payload/guard nội bộ nếu cần.

### Mitigation semantics
- Chọn **2A**: mitigation theo `touch` semantics và emit **1 lần/event**:
  - Bullish mitigated khi `low <= top`
  - Bearish mitigated khi `high >= bottom`
- Giữ hành vi emit-once để tránh noise và giữ deterministic/replay parity.

### State handling policy
- Chọn **3A**: giữ lifecycle `FRESH -> TOUCHED -> BROKEN` hiện tại cho `state_obj.fvgs`.
- Bổ sung guard/dedup tối thiểu để tăng determinism; không refactor schema state lớn trong phase này.
- Duy trì `transient_signals` là ephemeral-per-candle contract.

### Test gate strategy
- Chọn **4C**: bắt buộc đầy đủ test gates cho Phase 03:
  - Unit tests
  - Helper integration tests
  - Factory contract test (wiring)
  - Runtime-path integration test (không patch factory cho chính FVG signal)
  - Coverage gate `>= 80%` cho scope thay đổi

### Non-negotiable rule
- **Bắt buộc backward-compatible hoàn toàn** với behavior hiện có (event keys + strategy tags + downstream consumption).

### Claude's Discretion
- Cấu trúc chi tiết test matrix cho edge cases (boundary 3-candle detection, dedup, emit-once).
- Mức hardening (logging/guards) miễn không làm đổi public contract.

</decisions>

<specifics>
## Specific Ideas

- Decision (1) được khóa theo phân tích strategy/runtime:
  - Strategy (`TemplateStrategy`) tiêu thụ `signal_history.tag` theo chuỗi (`fvg_up` nằm trong `smc_trend_scalping`).
  - Integration filter tiêu thụ `transient_signals` keys (`fvg_bull_new/...`) để trigger snapshot.
- Vì vậy, phase này phải giữ dual compatibility thay vì chuyển hẳn sang 1 schema mới.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and traceability
- `.planning/ROADMAP.md` — Phase 03 goal/depends/requirements/success criteria.
- `.planning/REQUIREMENTS.md` — `SIG-03`, `TST-01..04`, `VAL-01..02` quality gates.
- `.planning/STATE.md` — Current planning state (Phase 03 discuss/planning).

### FVG implementation and runtime contracts
- `services/aureus-signal/engine/signals/fvg.py` — Current FVG creation + mitigation transient events.
- `services/aureus-signal/engine/signals/fvg_up.py` — Bullish FVG tag-style signal.
- `services/aureus-signal/engine/signals/fvg_down.py` — Bearish FVG tag-style signal.
- `services/aureus-signal/engine/event_filter.py` — Structural tags consumed for snapshot trigger.
- `services/aureus-signal/engine/state.py` — `fvgs`, `transient_signals`, `signal_history` lifecycle.
- `services/aureus-signal/engine/signal_factory.py` — FVG factory wiring (`fvg_up`, `fvg_down`) behind feature flag.

### Strategy compatibility references
- `services/aureus-signal/engine/strategies/smc_trend_scalping.py` — Strategy sequence includes `fvg_up` tag.
- `services/aureus-signal/engine/strategies/template.py` — Sequence engine matches `signal_history` by `tag`.

### Process/quality guardrails
- `.planning/SIGNAL_INTEGRATION_PROCESS.md` — Mandatory anti-masking + 3-layer integration testing policy.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FVGSignal` already emits transient events for new/mitigated gaps.
- `FVGUpSignal`/`FVGDownSignal` already express directional `tag` contracts.
- `SymbolState` already owns FVG lifecycle lists and history logging.

### Established Patterns
- Strategy matching depends on `signal_history.tag` order and timestamps.
- Event-driven sparse snapshot depends on transient structural keys in `event_filter`.
- Factory wiring integrity is a known regression hotspot and must be explicitly tested.

### Integration Points
- Runtime/backtest engines log tags to `signal_history` and consume transient events per candle.
- Any FVG contract drift can break either strategy confluence or snapshot triggering.

</code_context>

<deferred>
## Deferred Ideas

- Renaming or unifying event-key/tag schema into a single new public contract.
- Deep refactor of `fvgs` persisted schema beyond minimal deterministic hardening.

</deferred>

---

*Phase: 03-signal-fvg*
*Context gathered: 2026-03-20*
