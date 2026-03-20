# SPEC_STRATEGY_PLUGIN_INTERFACE

## 1. Purpose

Define the strict contract for strategy plugins to ensure deterministic behavior, flow correctness, and safe extensibility.

## 2. Canonical Interfaces

## 2.1 Strategy identity
Each plugin must declare:
- `strategy_id` (unique, immutable)
- `strategy_version` (semver)
- `spec_compatibility` (min/max supported spec versions)

## 2.2 Lifecycle hooks (required)
1. `on_bar_close(context) -> SignalIntent | None`
2. `validate_entry(intent, context) -> ValidationResult`
3. `build_order_plan(intent, context) -> OrderPlan`
4. `on_position_update(event, context) -> PositionAction | None`
5. `on_position_close(event, context) -> CloseSummary`

Hooks must be pure with respect to deterministic inputs (no hidden randomness).

## 3. Input Contract

`context` must include:
- instrument identity (`symbol`, `timeframe`)
- current closed candle + lookback window
- normalized signal states (`zigzag`, `ob`, `choch`, `fvg`, `trend_filter`)
- strategy runtime settings
- portfolio/position snapshot scoped for strategy
- `backfill_status`
- version metadata

If `backfill_status != READY`, strategy must return `None` and reason code.

## 4. Output Contract

### 4.1 SignalIntent
Required fields:
- `intent_id`
- `strategy_id`
- `symbol`, `timeframe`
- `side` (`BUY|SELL`)
- `entry_reason_codes[]`
- `confidence` (optional numeric)
- `created_at`

### 4.2 ValidationResult
- `is_valid` boolean
- `failed_rules[]` (rule ids)
- `reasons[]` (human-readable)

### 4.3 OrderPlan
Required:
- `entry_type`, `entry_price_policy`
- `sl_mode`, `sl_value`
- `tp_mode`, `tp_value`
- `trailing_mode`, `trailing_value`
- `position_sizing_mode`, `size_value`
- `expiry_policy`

## 5. Per-Strategy Risk and Position Settings

Each plugin owns its settings, including:
- `max_positions_per_symbol`
- `max_total_positions`
- `allow_pyramiding`
- cooldown and re-entry constraints

No global component may silently override these values without traceable policy event.

## 6. State Machine Contract

## 6.1 Canonical states
`IDLE -> SIGNAL_DETECTED -> ENTRY_VALIDATED -> ORDER_PLANNED -> ORDER_SUBMITTED -> POSITION_OPEN -> POSITION_MANAGED -> POSITION_CLOSED`

## 6.2 Illegal transitions
Any transition not explicitly allowed is illegal and must be rejected.

## 6.3 Mandatory validator checks
At minimum:
- backfill readiness
- closed-candle assurance
- signal predicate completeness
- risk settings completeness
- position-limit compliance

## 7. Error and Rejection Handling

Every rejection/error must include:
- `strategy_id`, `strategy_version`
- state at failure
- `reason_code`
- deterministic timestamp and correlation id

Recoverable errors may continue next bar; integrity errors must fail-closed for affected stream.

## 8. Compatibility and Migration

1. Strategy plugin must fail to load if `spec_compatibility` does not match active spec.
2. Breaking interface changes require major version bump.
3. Migration notes must define behavior changes and replay impact.

## 9. Testing Requirements for New Strategy Plugin

Minimum test pack:
- deterministic replay test (same input => same outputs)
- transition legality tests
- validation failure tests with reason codes
- risk-setting conformance tests
- order plan completeness tests

---
Version: `v1.0.0`
