---
phase: 22
reviewers: [claude]
reviewed_at: 2026-04-03T22:36:49.7858683+07:00
plans_reviewed: ["22-01-PLAN.md", "22-02-PLAN.md", "22-03-PLAN.md"]
---

# Cross-AI Plan Review � Phase 22

## the agent Review

# Phase 22 Plan Review (Cross-AI)

## Plan 01 — Provider Interface Definitions & Data Models

### 1) Summary
This is a strong foundational plan for Phase 22: it introduces the right abstractions (`MarketDataProvider`, `DecisionProvider`) and keeps implementation scope small. It aligns with locked decisions (dual interfaces, provider package location, `abc.ABC`) and is appropriately additive. The main risk is contract ambiguity (raw candle typing/shape guarantees and decision action normalization).

### 2) Strengths
- Clear, minimal scope: interface + dataclass only.
- Correctly separates market data from decision generation.
- Uses async methods, matching existing runtime patterns.
- Re-export strategy in `providers/__init__.py` improves discoverability.
- Includes lifecycle hooks (`setup`/`teardown`) for future provider implementations.

### 3) Concerns
- **MEDIUM:** `DecisionSignal.action` is a free-form `str`; no explicit canonical enum/`Literal` contract (risk of drift: `OVERWEIGHT` vs `BUY`).
- **MEDIUM:** Candle contract uses `Dict[str, Any]` without stronger typing (`TypedDict`/validation), increasing integration ambiguity.
- **LOW:** `metadata` field is extra beyond must-haves (minor scope creep, probably acceptable).
- **LOW:** Verification only checks import/smoke; no contract tests included in this plan (delegated to Plan 03, which is okay if dependency sequencing is fixed).

### 4) Suggestions
- Define action contract explicitly (e.g., `Literal["BUY","SELL","HOLD"]`) and document mapping responsibility for non-canonical provider outputs.
- Consider a `TypedDict` for raw candle shape (`t,o,h,l,c,v,symbol`) to reduce implicit assumptions.
- Add short docstring note that `MarketDataProvider` returns **raw candle dicts**, not `CandleRecord`, to avoid confusion with `state.py`.

### 5) Risk Assessment
**Overall risk: LOW-MEDIUM.**  
Good design and bounded scope; biggest risk is contract ambiguity that can propagate to Plan 23+ implementations.

---

## Plan 02 — Redis Market Data Provider Extraction

### 1) Summary
The intent (pure extraction, no behavior change) is right for Phase 22, but the proposed implementation has several internal inconsistencies and potential behavior drift compared to the current engine path. It’s close, but needs tightening before execution to avoid accidental runtime regressions.

### 2) Strengths
- Correctly introduces `RedisMarketDataProvider` as default-compatible adapter.
- Preserves core Redis stream mechanics (`xreadgroup`, `xack`, stream key shape).
- Includes recovery path for `NOGROUP`.
- Historical fetch path and oldest-first conversion are sensible and testable.
- Keeps integration with `live_engine.py` out of this step (good separation).

### 3) Concerns
- **HIGH:** Must-have says “consumer group creation handled in `setup()`”, but implementation makes `setup()` no-op and creates groups in `subscribe()`. Contract mismatch.
- **HIGH:** Plan claims zero behavior change, but parsing/typing may shift behavior (`t/o/h/l/c/v` forced to strings; defaulting missing fields to `"0"`), which can mask malformed data.
- **MEDIUM:** Broad `except Exception` with retry loop can hide persistent failures and create noisy infinite loops.
- **MEDIUM:** `xack` after `yield` means if downstream processing crashes, message remains pending (possibly acceptable, but should be deliberate and documented).
- **LOW:** Unused imports (`datetime`, `timezone`) indicate implementation looseness.
- **LOW:** No explicit cancellation handling (`asyncio.CancelledError`) for graceful shutdown.

### 4) Suggestions
- Resolve setup inconsistency: either move group creation to `setup(symbols)` or update must-have/contract to “lazy creation in subscribe.”
- Preserve current field types exactly as existing engine expects (or explicitly validate and fail on malformed payloads rather than silently coercing).
- Narrow exception handling; treat `CancelledError` separately and re-raise.
- Add explicit malformed-message handling path (log taxonomy placeholder) without inventing fallback semantics that hide data issues.
- Document ack semantics and pending-entry expectations.

### 5) Risk Assessment
**Overall risk: MEDIUM-HIGH.**  
Architecture direction is correct, but current draft can introduce subtle runtime drift despite “pure refactor” intent.

---

## Plan 03 — Provider Tests & Backward Compatibility Verification

### 1) Summary
Good test intent and coverage targets, but dependency wiring is flawed and some tests are likely brittle. The plan should be adjusted to ensure it validates actual delivered artifacts in wave order and avoids environment-coupled failures.

### 2) Strengths
- Tests core contracts (ABCs, dataclass, re-exports, provider subclassing).
- Includes historical formatting/order checks.
- Includes backward-compatibility smoke checks for existing imports.
- Calls for full test suite regression run, aligned with zero-regression goal.

### 3) Concerns
- **HIGH:** `depends_on: [1]` is incorrect; this plan tests `RedisMarketDataProvider`, so it must depend on Plan 2.
- **MEDIUM:** Full suite requirement “all tests pass” may fail due to unrelated baseline instability; could block phase unfairly.
- **MEDIUM:** `subscribe()` behavior tests mentioned in must-haves (“handles NOGROUP”) are not clearly implemented in provided test code.
- **LOW:** Importing `engine.live_engine` in unit tests may pull heavy runtime deps and make tests fragile.
- **LOW:** `asyncio.run` in unittest is okay but can clash in certain environments; `pytest.mark.asyncio` might be cleaner if pytest-native style is already used.

### 4) Suggestions
- Change dependency to `depends_on: [1,2]`.
- Add explicit async unit tests for:
  - NOGROUP recovery path
  - non-CANDLE message filtering
  - timestamp normalization edge cases
- Separate “contract tests” from “full regression suite” gating (e.g., phase gate requires targeted tests + smoke subset; full suite reported separately if flaky).
- Prefer lightweight import compatibility tests that avoid executing heavy runtime initialization.

### 5) Risk Assessment
**Overall risk: MEDIUM.**  
Test strategy is directionally good, but current ordering and brittleness could cause false negatives and delivery friction.

---

## Overall Phase-22 Plan Quality

- **Alignment with phase goals:** Good overall; plans map to provider abstraction and backward compatibility.
- **Biggest gap:** Plan dependency and behavior-preservation rigor (especially Plan 02/03).
- **Recommended before execution:**  
  1) Fix Plan 03 dependency,  
  2) Reconcile Plan 02 setup semantics and type/validation behavior,  
  3) Tighten contract definitions in Plan 01.

**Overall program risk: MEDIUM** until those adjustments are made.


---

## Consensus Summary

Only one reviewer (claude) was available in this environment, so consensus is limited. Treat the review section above as primary feedback and re-run with additional CLIs when available for broader adversarial coverage.

### Agreed Strengths
- Not applicable (single reviewer run).

### Agreed Concerns
- Not applicable (single reviewer run).

### Divergent Views
- Not applicable (single reviewer run).

