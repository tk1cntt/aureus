# SPEC_ROLLOUT_GATES

## 1. Purpose

Define mandatory promotion gates for deployment path:
`SHADOW -> PAPER -> LIVE`.

## 2. Stage Definitions

## 2.1 SHADOW
- System runs full signal + strategy pipeline.
- No real order execution.
- Generates decision traces and shadow outcomes.

## 2.2 PAPER
- Simulated order execution with broker-like constraints.
- Full strategy lifecycle and risk rules active.
- Produces performance metrics used for live readiness.

## 2.3 LIVE
- Real order execution enabled for approved scope.

## 3. Universal Gate Checks (all stages)

1. Closed-candle invariant compliance.
2. Backfill readiness enforcement.
3. State machine + validator pass rates above threshold.
4. Decision trace completeness pass.
5. No critical integrity incidents unresolved.

## 4. Promotion Gates

## 4.1 SHADOW -> PAPER
Required evidence:
- deterministic replay parity report,
- rejection reason-code distribution,
- trace completeness report,
- data integrity incident log.

Must pass:
- zero critical determinism violations,
- zero trades generated while `backfill_status != READY`,
- required trace fields completeness >= configured threshold.

## 4.2 PAPER -> LIVE
Required evidence:
- strategy-level performance report,
- drawdown profile,
- execution quality diagnostics,
- adaptive phase status report.

Must pass:
- calibrated metric thresholds (winrate, profit factor, max drawdown) per approved policy,
- no unresolved high-severity validator/state errors,
- operational readiness checklist signed.

## 5. Live Guardrails

In LIVE, system must continuously enforce:
- per-strategy position limits,
- integrity fail-closed behavior,
- real-time incident alerting,
- immediate rollback path to PAPER/disabled mode.

## 6. Rollback Policy

Rollback to previous safe stage when any occurs:
- critical determinism breach,
- repeated flow validation failures,
- severe data continuity failures,
- metric degradation beyond allowed bounds.

Rollback event must capture:
- trigger reason code,
- affected strategies/symbols,
- timestamp,
- operator/system initiator,
- remediation ticket/reference.

## 7. Evidence Retention

For each promotion decision, retain:
- gate check outputs,
- metric snapshots,
- relevant trace samples,
- approval record.

Retention should support full audit and post-mortem review.

## 8. Minimal Go/No-Go Checklist

- [ ] Determinism validated
- [ ] Backfill gate validated
- [ ] Flow correctness validated
- [ ] Trace completeness validated
- [ ] Strategy performance validated
- [ ] Rollback drill validated

---
Version: `v1.0.0`
