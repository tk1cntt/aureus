# Aureus–Nautilus Integration (Execution Slice 1)

This plan implements the first production-oriented slice of the Aureus→Nautilus integration while keeping Aureus signal generation behavior intact. The target of this slice is to introduce the execution bridge contract and feedback loop with minimal, controlled change surface.

## User Review Required

> [!IMPORTANT]
> **Scope confirmation requested:** I recommend implementing **Slice 1 = bridge + execution event pipeline + minimal mode toggle plumbing**, but **not** full portfolio/reconciliation APIs yet.  
> This keeps risk low and gives us measurable parity checkpoints before broader cutover.

## Proposed Changes

### Integration Orchestration

#### [NEW] [main.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-bridge/main.py)
Create a new bridge worker service that:
- Consumes `aureus:stream:*:orders`
- Applies idempotency guard by `trace_id`
- Routes intents to Nautilus adapter layer
- Publishes normalized execution events to `aureus:stream:{symbol}:execution`

#### [NEW] [mapper.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-bridge/mapper.py)
Add translation helpers for:
- Side/type/quantity mapping
- Status mapping (`ORDER_ACCEPTED`, `PARTIAL_FILL`, `FILLED`, `CANCELED`, `REJECTED`, `RISK_BLOCKED`)
- Contract normalization + validation for required fields (`trace_id`, `symbol`, `event_time`)

#### [NEW] [reconciliation.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-bridge/reconciliation.py)
Add execution-report normalization and terminal-state safety rules to avoid duplicate/invalid transitions.

---

### Aureus Signal Engine (Minimal Wiring)

#### [MODIFY] [live_engine.py](file:///d:/AIFramework/aureus/services/aureus-signal/engine/live_engine.py)
Add/configure `execution_mode` gate (`simulated|nautilus`) so that:
- Signal detection and trigger generation remain unchanged
- In `nautilus` mode, local simulated PnL/order-closing path is bypassed where appropriate
- Existing snapshot/checkpoint behavior is preserved

#### [MODIFY] [orders.py](file:///d:/AIFramework/aureus/services/aureus-signal/engine/orders.py)
Preserve existing intent publication and enrich metadata needed for bridge correlation (primarily `trace_id` continuity and execution metadata field support).

---

### Persistence

#### [MODIFY] [main.py](file:///d:/AIFramework/aureus/services/aureus-db-writer/main.py)
Extend stream discovery/processing to include `aureus:stream:*:execution` and write normalized rows to new execution table buffer path.

#### [MODIFY] [schema.sql](file:///d:/AIFramework/aureus/services/aureus-db-writer/schema.sql)
Add initial `aureus_execution_events` table with indexing on:
- `trace_id`
- `symbol`
- `event_time`
- `status`

(Positions/account snapshots deferred to a later slice.)

---

### Tests

#### [NEW] [test_mapper.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-bridge/tests/test_mapper.py)
Unit tests for field/status mapping and required-field validation.

#### [NEW] [test_bridge_idempotency.py](file:///d:/AIFramework/aureus/services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py)
Unit tests for duplicate `trace_id` handling and single-publish guarantees.

#### [MODIFY] [test_orders_events.py](file:///d:/AIFramework/aureus/services/aureus-signal/unittest/test_orders_events.py)
Only if needed: add a narrow assertion that intent event payload still retains required correlation fields for bridge processing.

## Verification Plan

### Automated Tests

Run in WSL (per repository runtime constraints):

1. Existing signal-order event regression check:
```powershell
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_orders_events.py"
```

2. Existing trade manager regression check:
```powershell
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus/services/aureus-signal && python unittest/test_trade_manager_events.py"
```

3. New mapper contract tests:
```powershell
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_mapper.py"
```

4. New bridge idempotency tests:
```powershell
wsl -d Ubuntu-24.04 -e bash -lc "cd /mnt/d/AIFramework/aureus && python services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py"
```

### Manual Verification

1. Start/refresh core services (if needed) in WSL and ensure no startup errors in logs.
2. Inject one synthetic order intent into `aureus:stream:{symbol}:orders`.
3. Verify exactly one corresponding execution event is published to `aureus:stream:{symbol}:execution`.
4. Re-send the same intent (`trace_id` unchanged) and verify no duplicate execution row is written.
5. Confirm persisted row exists in `aureus_execution_events` with expected `status`, `trace_id`, and `event_time`.
