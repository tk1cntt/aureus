# ROADMAP

## Archived Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.1 | Signal Optimization | 07-13 | ✅ Shipped 2026-03-22 |
| v1.2 | Strategy Sequence Engine | 14-15 | ✅ Shipped 2026-03-22 |
| v1.3 | Backtesting & Measurement Engine | 15.5-20 | ✅ Closed 2026-04-03 (known gaps logged) |
| v1.4 | TradingAgents Market Data Integration | 21-25 | ✅ Closed 2026-04-05 (known gaps logged) |
| v1.5 | Signal Delivery & Trade Management | 26-53 | ✅ Shipped 2026-04-21 |
| v1.6 | Strategy Evaluation & Insight Delivery | 54-58 | ✅ Shipped 2026-06-10 (known gaps logged) |

---

## Current Milestone: v1.7 (Planning)

**Status:** Awaiting requirements definition

**Milestone v1.6 shipped:** 2026-06-10
- Completed: Phase 54 (Scoring Framework), Phase 55 (Evaluation Pipeline), Phase 58 (Strategy Fixes)
- Deferred to v1.7: Phase 55.1, 56, 57

---

### v1.6 Completed Phases (Archived)

<details>
<summary>✅ Phase 54: Strategy Scoring Framework (COMPLETED 2026-04-21)</summary>

- Two-stage scoring core (gate + weighted-sum)
- Immutable version snapshot output
- Per-trade + aggregate scoring
- Contract tests for formula, versioning, breakdown

**Key Files:**
- `services/aureus-signal/engine/scoring/__init__.py`
- `services/aureus-signal/engine/scoring/models.py`
- `services/aureus-signal/engine/scoring/gate.py`
- `services/aureus-signal/engine/scoring/normalize.py`
- `services/aureus-signal/engine/scoring/compute.py`
- `services/aureus-signal/engine/scoring/aggregate.py`

</details>

<details>
<summary>✅ Phase 55: Evaluation Data Model & Pipeline (COMPLETED 2026-04-23)</summary>

- Journal-linked evaluation schema
- DB-level guardrails (unique/FK/check)
- Signal snapshot hybrid storage (JSONB + typed columns)
- E2E pipeline tests

**Key Files:**
- `services/aureus-db-writer/migrations/add_trade_evaluations.sql`
- `services/aureus-db-writer/tests/test_evaluation_migration.py`
- `services/aureus-trader/tests/test_signal_snapshot_migration.py`

</details>

<details>
<summary>✅ Phase 58: Fix Inactive Trading Strategies (COMPLETED 2026-06-06)</summary>

- 6 TPO strategies verified end-to-end
- 2 FZ_CONT strategies verified (choch->bos sequence)
- bos_up/bos_down emission fixed

**Key Fixes:**
- structure.py: hardcoded "choch" tag → dynamic `tag`
- Test timestamp alignment for bos_up emission

</details>

---

### Deferred Work (v1.7 candidates)

<details>
<summary>📋 Phase 55.1: Restore Evaluation Pipeline (Deferred)</summary>

**Goal:** Restore aureus_trade_evaluations table and INSERT paths
**Depends on:** Phase 55
**Plans:** 1 plan (pending)

</details>

<details>
<summary>📋 Phase 56: Multi-Dimensional Reporting Engine (Deferred)</summary>

**Goal:** Report engine drill-down per-trade + aggregate multi-dimensional
**Requirements:** RPT-01→05, ACC-03
**Status:** Not started

</details>

<details>
<summary>📋 Phase 57: Telegram Insight Delivery (Deferred)</summary>

**Goal:** Telegram insight delivery với evaluation context
**Requirements:** TEL-EVAL-01→04, ACC-02
**Status:** Not started

</details>

---

## Backlog

- [ ] Define v1.7 requirements and scope
- [ ] Prioritize deferred phases (55.1, 56, 57)
- [ ] Consider additional strategy performance improvements

