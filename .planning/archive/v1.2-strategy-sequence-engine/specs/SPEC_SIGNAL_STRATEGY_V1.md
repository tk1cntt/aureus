# SPEC_SIGNAL_STRATEGY_V1

## 1. Purpose

This document is the v1 source of truth for live signal + strategy behavior in Aureus.
Primary objective: **algorithm correctness and flow correctness over speed**.

## 2. Scope (V1)

### 2.1 Instruments
- `XAUUSD`
- `BTCUSD`
- `ETHUSD`
- `USTEC`
- `USDJPY`
- `EURUSD`
- `GBPUSD`
- `AUDUSD`

### 2.2 Timeframe
- `M1` only.

### 2.3 Mandatory signal primitives
- `ZigZag`
- `OB` (Order Block)
- `CHOCH`
- `FVG`
- `trend_filter`

## 3. Non-Negotiable Processing Invariants

1. **Closed-candle only**: no decision logic may use unclosed candle values.
2. **Deterministic execution**: same input data + same config + same versions => identical outputs.
3. **Backfill-before-calculate**: if required history is incomplete, pipeline must not compute signals or emit entries.
4. **Fail-closed behavior**: on integrity uncertainty, block trading for affected stream and emit rejection reason.

## 4. Candle and Data Readiness Rules

### 4.1 Closed candle gate
A candle is eligible only when:
- exchange timestamp is finalized,
- OHLCV are immutable for that interval,
- bar sequencing has no unresolved gap.

### 4.2 Backfill readiness gate
For each `(symbol, timeframe)` stream, engine must have:
- minimum lookback required by all active signal primitives,
- contiguous bars for lookback window,
- consistent timezone/session normalization.

If any item fails, set `backfill_status != READY` and block decisions.

## 5. Signal Semantics (Contract Level)

### 5.1 ZigZag
- Produces pivot structure events from closed bars only.
- Pivot revisions are allowed only per ZigZag algorithm rules; all revisions must be versioned in signal state.

### 5.2 OB
- OB candidates are derived from finalized structure context.
- OB validity state must be explicit: `CANDIDATE | VALID | INVALIDATED | MITIGATED`.

### 5.3 CHOCH
- CHOCH event requires structure break conditions defined by configured rules.
- Event payload must include direction and reference pivots used to confirm break.

### 5.4 FVG
- FVG state must include boundaries, status (`OPEN | PARTIAL | FILLED | INVALID`), and direction.

### 5.5 trend_filter
- Trend output must be explicit (`BULL | BEAR | NEUTRAL`) and must include source parameters.

## 6. Strategy Framework Rules

1. Strategies are plugins (see `SPEC_STRATEGY_PLUGIN_INTERFACE.md`).
2. Each strategy defines its own trigger, SL/TP/trailing, and position limits.
3. Multiple strategies may open independent positions on same symbol.
4. PnL and analytics are isolated per strategy.

## 7. Sample Strategy #1 (Reference)

### 7.1 ID
- `S1_CHOCH_OB_RETEST_TREND`

### 7.2 Entry logic (BUY side, SELL mirrored)
1. Detect bullish CHOCH on closed candle.
2. Locate valid bullish OB.
3. Confirm price retests OB boundary on closed candle.
4. `trend_filter == BULL`.
5. All state-machine and validator checks pass.

### 7.3 Exit/risk
- Defined in strategy config only (no hidden defaults in engine).
- Required explicit fields: SL mode/value, TP mode/value, trailing mode/value.

## 8. Flow Correctness Enforcement

### 8.1 Mandatory double guard
- **State machine** enforces legal lifecycle transitions.
- **Rule validator** enforces pre/post conditions per transition.

### 8.2 Required rejection behavior
If any check fails:
- decision must be rejected,
- reason code must be emitted,
- trace snapshot must be persisted.

## 9. Determinism and Versioning

Each decision event must carry:
- `spec_version` (this doc version),
- `strategy_version`,
- `engine_version`.

Any change to signal semantics, rule thresholds, or transition logic requires version bump and migration notes.

## 10. Acceptance Criteria (V1)

1. Closed-candle invariant validated in tests.
2. Deterministic replay parity achieved on repeated runs.
3. Backfill gate blocks all decisions on incomplete data.
4. Sample strategy emits entries only when all required signal predicates pass.
5. Invalid transitions are rejected with reason codes.
6. Entry decisions generate complete trace snapshots.

## 11. Out of Scope (V1)

- Multi-timeframe orchestration.
- Auto-optimizing strategy parameters in live without gate approval.
- Tick-level trigger decisions.

---
Version: `v1.0.0`
