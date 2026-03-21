# Phase 4: Signal Pivots Optimization - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Optimize and validate the `pivots` signal for deterministic and stable behavior **without changing trading intent**.

For this phase, scope is locked to **conservative hardening**:
- Guardrails and determinism hardening around existing pivot flow
- Input/state safety improvements
- Contract stability and regression-proofing

Out of scope in this phase:
- Rewriting pivot core math
- Changing pivot confirmation semantics
- Expanding strategy capability scope

</domain>

<decisions>
## Implementation Decisions

### Risk Posture
- Locked choice: **Conservative** (`1`)
- Preserve current MQL5-parity behavior as default baseline
- Prioritize correctness and parity over optimization ambition

### Algorithm Change Policy
- **Do not modify pivot core algorithm** in `zigzag_pro2` for this phase
- **Do not change non-repaint confirmation behavior** (tentative last pivot handling)
- Any refactor must be behavior-preserving at signal-contract level

### Metadata & State Safety
- Hardening around metadata merge is allowed only if it does not alter pivot semantics
- Preserve existing downstream metadata continuity (`is_choch`, `ob`, `fvg`, `broken`, `breakout_t`)
- Keep `swing_points` contract and bounded history behavior consistent

### Persistence & Contract Stability
- Keep output schema stable: `tag`, `price`, `t`, `is_high`
- Keep stable DB sync intent unchanged (current `stable_pivot` convention)
- No new public signal tags introduced in this phase

### Claude's Discretion
- Internal guard implementation details (validation checks, defensive branches, logging granularity)
- Test fixture structure and helper organization
- Naming of internal helper utilities (non-public)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and mapping
- `.planning/ROADMAP.md` — phase mapping, per-phase success criteria template, traceability updates
- `.planning/REQUIREMENTS.md` — `SIG-04`, `TST-01..04`, `VAL-01..02` constraints and quality gates
- `.planning/PROJECT.md` — milestone objective: deterministic correctness first, no trading-intent drift

### Pivots implementation and contracts
- `services/aureus-signal/engine/signals/pivots.py` — current pivot calculation flow, merge behavior, persistence handoff
- `services/aureus-signal/engine/common/zigzag_pro2.py` — strict MQL5-port pivot engine baseline (algorithm must remain stable in this phase)
- `services/aureus-signal/engine/state.py` — symbol state structures and bounded ledgers (`swing_points`, `tracking_vars`)

### Downstream integration points
- `services/aureus-signal/engine/signal_factory.py` — signal wiring, pivots config injection, normalized snapshot source
- `services/aureus-signal/engine/event_filter.py` — structural event trigger semantics to keep consistent
- `services/aureus-signal/engine/strategies/template.py` — tag-sequence consumption pattern and scoring sensitivity

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PivotSignal` in `pivots.py` already encapsulates dynamic amplitude, incremental updates, merge/relabel, and persistence sync hooks
- `build_normalized_signal_snapshot` in `signal_factory.py` provides a stable diagnostic contract when signal state is missing

### Established Patterns
- Stateful signal processing with `SymbolState` as single source for transient + persistent runtime context
- Non-repaint discipline: avoid acting on tentative latest structural point
- Strategy evaluation depends on stable tag history ordering and deterministic event production

### Integration Points
- `create_signal_set(...)` pipeline in `signal_factory.py`
- `state_obj.swing_points` consumers in structure/choch/sweep flow
- Redis stream sync path for stable pivot persistence in `pivots.py`

</code_context>

<specifics>
## Specific Ideas

- Add parity-focused regression tests to ensure conservative hardening does not drift baseline pivot outputs.
- Prefer defensive guards around malformed/edge candle slices over algorithmic reinterpretation.

</specifics>

<deferred>
## Deferred Ideas

- Core pivot algorithm redesign or confirmation-logic changes (candidate for future phase only if parity framework is prepared).
- Aggressive optimization that risks divergence from strict MT5-equivalent behavior.

</deferred>

---

*Phase: 04-signal-pivots*
*Context gathered: 2026-03-21*
