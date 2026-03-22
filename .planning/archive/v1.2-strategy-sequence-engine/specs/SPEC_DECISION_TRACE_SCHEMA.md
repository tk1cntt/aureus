# SPEC_DECISION_TRACE_SCHEMA

## 1. Purpose

Define required trace payload captured at **every entry decision point** so that each trade can be fully audited and replayed.

## 2. Capture Policy

1. Capture event for every entry decision (`ACCEPTED` or `REJECTED`).
2. Capture occurs at decision time (not deferred batch).
3. Trace records are immutable append-only.

## 3. Required Top-Level Fields

- `trace_id` (UUID)
- `decision_status` (`ACCEPTED | REJECTED`)
- `decision_timestamp`
- `symbol`
- `timeframe`
- `strategy_id`
- `strategy_version`
- `spec_version`
- `engine_version`
- `correlation_id`

## 4. Market Snapshot Block

- `bar_timestamp`
- `bar_ohlcv`
- `spread` (if available)
- `session_label`
- `backfill_status`
- `data_window_start`
- `data_window_end`
- `data_window_hash` (or equivalent deterministic fingerprint)

## 5. System Signal Snapshot Block

Must include values for all system-defined signals at decision time, not just strategy-local predicates.

Required keys:
- `zigzag_state`
- `ob_state`
- `choch_state`
- `fvg_state`
- `trend_filter_state`

Each state should include:
- primary value/result
- confidence/quality (if available)
- source params/version id

## 6. Rule Evaluation Block

- `evaluated_rules[]`
  - `rule_id`
  - `result` (`PASS|FAIL|SKIP`)
  - `reason_code`
  - `evidence_refs[]` (references to signal values/thresholds)

If `decision_status=REJECTED`, at least one `FAIL` rule is mandatory.

## 7. Order Plan Snapshot Block (for accepted decisions)

- `entry_type`
- `entry_policy`
- `sl_mode`, `sl_value`
- `tp_mode`, `tp_value`
- `trailing_mode`, `trailing_value`
- `size_mode`, `size_value`
- `expiry_policy`

## 8. Flow Integrity Block

- `current_state`
- `next_state`
- `transition_allowed` boolean
- `validator_passed` boolean
- `validator_failures[]`

## 9. Storage and Query Requirements

1. Trace must be queryable by: symbol, strategy, timeframe, time range, reason_code, status.
2. Retention must support backtest calibration and post-trade forensic analysis.
3. Indexing must prioritize recent-time + strategy filters.

## 10. Quality Gates

A decision trace is valid only if:
- all required top-level fields exist,
- backfill status is present,
- system signal snapshot contains all mandatory keys,
- rule block is non-empty,
- accepted decision has order plan snapshot.

## 11. Example Minimal JSON Shape

```json
{
  "trace_id": "uuid",
  "decision_status": "ACCEPTED",
  "decision_timestamp": "2026-03-20T00:00:00Z",
  "symbol": "XAUUSD",
  "timeframe": "M1",
  "strategy_id": "S1_CHOCH_OB_RETEST_TREND",
  "strategy_version": "1.0.0",
  "spec_version": "1.0.0",
  "engine_version": "1.0.0",
  "backfill_status": "READY",
  "signals": {
    "zigzag_state": {},
    "ob_state": {},
    "choch_state": {},
    "fvg_state": {},
    "trend_filter_state": {}
  },
  "evaluated_rules": []
}
```

---
Version: `v1.0.0`
