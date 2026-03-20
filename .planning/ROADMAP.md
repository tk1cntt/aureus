# ROADMAP — Milestone v1.1 Signal Optimization

## Proposed Roadmap

**9 phases** | **9 signals (1 signal / phase)** | Test gate per phase: unit + integration + coverage >= 80%

| # | Phase Folder | Signal | Requirements | Success Criteria | Status |
|---|---|---|---|---|---|
| 01 | `01-signal-atr` | `atr` | SIG-01, TST-01..04, VAL-01..02 | 6 | ✅ Done |
| 02 | `02-signal-ema` | `ema` | SIG-02, TST-01..04, VAL-01..02 | 6 | ⏳ Next |
| 03 | `03-signal-fvg` | `fvg` | SIG-03, TST-01..04, VAL-01..02 | 6 | Pending |
| 04 | `04-signal-pivots` | `pivots` | SIG-04, TST-01..04, VAL-01..02 | 6 | Pending |
| 05 | `05-signal-session` | `session` | SIG-05, TST-01..04, VAL-01..02 | 6 | Pending |
| 06 | `06-signal-sweep` | `sweep` | SIG-06, TST-01..04, VAL-01..02 | 6 | Pending |
| 07 | `07-signal-trend` | `trend` | SIG-07, TST-01..04, VAL-01..02 | 6 | Pending |
| 08 | `08-signal-volume-sma` | `volume_sma` | SIG-08, TST-01..04, VAL-01..02 | 6 | Pending |
| 09 | `09-signal-structure` | `structure` | SIG-09, TST-01..04, VAL-01..02 | 6 | Pending |

## Phase 01: Signal ATR Optimization

- **Directory:** `01-signal-atr`
- **Status:** Done
- **Requirements:** `SIG-01`, `TST-01..04`, `VAL-01..02`

---

## Phase 01 Completion Evidence

- Folder: `.planning/phases/01-signal-atr/`
- Research: `.planning/phases/01-signal-atr/RESEARCH.md`
- Plan: `.planning/phases/01-signal-atr/PLAN.md`
- Validation: `.planning/phases/01-signal-atr/VALIDATION.md`
- Summary: `.planning/phases/01-signal-atr/SUMMARY.md`

---

## Phase Template (applies to every phase)

For each phase `NN` (signal-specific), all criteria below must pass:

1. **Signal correctness:** optimized signal behavior keeps existing trading intent and event semantics.
2. **Dedicated signal unit test:** create/update one dedicated unit test file for this signal.
3. **Dedicated integration test:** create/update one dedicated integration test file for this signal in `aureus-signal` system flow.
4. **Unit + integration pass:** all tests for this phase must pass.
5. **Coverage gate:** coverage report for phase scope is **>= 80%**.
6. **Traceability update:** `REQUIREMENTS.md` and roadmap references updated with evidence links/commands.
7. **Phase docs required:** each phase has `RESEARCH.md`, `PLAN.md`, `VALIDATION.md`, `SUMMARY.md` in its own folder.

---

## Requirement Traceability Update

| Requirement ID | Planned Phase |
|---|---|
| SIG-01 | 01 |
| SIG-02 | 02 |
| SIG-03 | 03 |
| SIG-04 | 04 |
| SIG-05 | 05 |
| SIG-06 | 06 |
| SIG-07 | 07 |
| SIG-08 | 08 |
| SIG-09 | 09 |
| TST-01 | 01-09 |
| TST-02 | 01-09 |
| TST-03 | 01-09 |
| TST-04 | 01-09 |
| VAL-01 | 01-09 |
| VAL-02 | 01-09 |

---

## Next Up

**Phase 02 (`02-signal-ema`)** — optimize `ema` with dedicated unit + integration tests and coverage >= 80% before phase closure.
