# ROADMAP — Milestone v1.1 Signal Optimization

## Proposed Roadmap

**9 phases** | **9 signals (1 signal / phase)** | Test gate per phase: unit + integration + coverage >= 80%

| # | Phase | Signal | Requirements | Success Criteria |
|---|---|---|---|---|
| 1 | Signal ATR Optimization | `atr` | SIG-01, TST-01..04, VAL-01..02 | 6 |
| 2 | Signal EMA Optimization | `ema` | SIG-02, TST-01..04, VAL-01..02 | 6 |
| 3 | Signal FVG Optimization | `fvg` | SIG-03, TST-01..04, VAL-01..02 | 6 |
| 4 | Signal Pivots Optimization | `pivots` | SIG-04, TST-01..04, VAL-01..02 | 6 |
| 5 | Signal Session Optimization | `session` | SIG-05, TST-01..04, VAL-01..02 | 6 |
| 6 | Signal Sweep Optimization | `sweep` | SIG-06, TST-01..04, VAL-01..02 | 6 |
| 7 | Signal Trend Optimization | `trend` | SIG-07, TST-01..04, VAL-01..02 | 6 |
| 8 | Signal Volume SMA Optimization | `volume_sma` | SIG-08, TST-01..04, VAL-01..02 | 6 |
| 9 | Signal Structure Optimization | `structure` | SIG-09, TST-01..04, VAL-01..02 | 6 |

---

## Phase Template (applies to every phase)

For each phase `N` (signal-specific), all criteria below must pass:

1. **Signal correctness:** optimized signal behavior keeps existing trading intent and event semantics.
2. **Dedicated signal unit test:** create/update one dedicated unit test file for this signal.
3. **Dedicated integration test:** create/update one dedicated integration test file for this signal in `aureus-signal` system flow.
4. **Unit + integration pass:** all tests for this phase must pass.
5. **Coverage gate:** coverage report for phase scope is **>= 80%**.
6. **Traceability update:** `REQUIREMENTS.md` and roadmap references updated with evidence links/commands.

---

## Requirement Traceability Update

| Requirement ID | Planned Phase |
|---|---|
| SIG-01 | 1 |
| SIG-02 | 2 |
| SIG-03 | 3 |
| SIG-04 | 4 |
| SIG-05 | 5 |
| SIG-06 | 6 |
| SIG-07 | 7 |
| SIG-08 | 8 |
| SIG-09 | 9 |
| TST-01 | 1-9 |
| TST-02 | 1-9 |
| TST-03 | 1-9 |
| TST-04 | 1-9 |
| VAL-01 | 1-9 |
| VAL-02 | 1-9 |

---

## Next Up

**Phase 1: Signal ATR Optimization** — optimize `atr` with dedicated unit + integration tests and coverage >= 80% before phase closure.
