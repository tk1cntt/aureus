---
quick_id: 260430-uij
phase: quick-260430-uij-implement-optimized-mt5-order-dispatch-r
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-trader/dispatcher.py
  - services/aureus-trader/config.py
  - services/aureus-trader/main.py
  - services/aureus-gateway/main.py
  - mql5/AureusProvider_v2.mq5
autonomous: true
requirements:
  - QUICK-260430-UIJ
user_setup: []
must_haves:
  truths:
    - "SYMBOL_NOT_ALLOWED từ provider trả NACK rõ ràng, không còn silent return khiến trader chờ ACK timeout."
    - "Order ở lane độc lập symbol+magic+direction được publish sang MT5 mà không phải chờ order lane khác hết result_timeout/backoff."
    - "Mỗi lane symbol+magic+direction chỉ có một command active; order cùng lane không publish đồng thời."
    - "Dispatcher phân biệt NACK, ACK timeout, final failure, result timeout after ACK là ambiguous/reconcile-needed."
    - "Có log/metric lightweight theo cmd_id cho enqueue age, publish, ACK/result latency, gateway drain latency; không overbuild OS-process-per-order."
  artifacts:
    - path: "services/aureus-trader/dispatcher.py"
      provides: "Bounded lane scheduler, command state machine, timeout classification, lightweight dispatch metrics."
    - path: "services/aureus-trader/config.py"
      provides: "Configurable bounded in-flight limit/reconcile timeout defaults without DB changes."
    - path: "services/aureus-trader/main.py"
      provides: "Startup/shutdown wiring for scheduler tasks and logging of bounded dispatcher config."
    - path: "services/aureus-gateway/main.py"
      provides: "Gateway write/drain latency logging on command forwarding path."
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Explicit SYMBOL_NOT_ALLOWED NACK and provider receive/ACK/result timing logs."
  key_links:
    - from: "services/aureus-trader/main.py"
      to: "services/aureus-trader/dispatcher.py"
      via: "OrderDispatcher(r, config, journal_manager=journal) and dispatch_loop/event_listener tasks"
      pattern: "OrderDispatcher\\(r, config"
    - from: "services/aureus-trader/dispatcher.py"
      to: "aureus:mt5:commands"
      via: "redis.publish(COMMANDS_CHANNEL, json.dumps(mt5_order))"
      pattern: "publish\\(COMMANDS_CHANNEL"
    - from: "services/aureus-trader/dispatcher.py"
      to: "aureus:mt5:events"
      via: "event_listener resolves cmd_id state transitions"
      pattern: "subscribe\\(EVENTS_CHANNEL\\)"
    - from: "services/aureus-gateway/main.py"
      to: "mql5/AureusProvider_v2.mq5"
      via: "TCP writer.write/drain forwards command JSON to provider ProcessIncomingCommands/ExecuteOpenOrder"
      pattern: "writer\\.drain\\(\\)"
---

<objective>
Implement optimized MT5 order dispatch roadmap Phase 1-3 from `260430-u7c-REPORT.md`: observability/no-response hardening, bounded lane scheduler, and ACK/result state machine with reconcile-needed semantics.

Purpose: reduce head-of-line blocking so independent trading lanes can hand off to MT5 in the 1-2s target while preserving safety for same `symbol + magic + direction` lanes.

Output: surgical code changes in trader dispatcher/config/main, gateway logging, and provider NACK/logging. No database schema/data changes are expected; DB E2E is not required for this quick because dispatch state remains in process/Redis events and journal behavior should only be invoked through existing handlers.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/quick/260430-u7c-analyze-and-propose-optimized-mt5-order-/260430-u7c-REPORT.md
@D:/Aureus/services/aureus-trader/dispatcher.py
@D:/Aureus/services/aureus-trader/config.py
@D:/Aureus/services/aureus-trader/main.py
@D:/Aureus/services/aureus-gateway/main.py
@D:/Aureus/mql5/AureusProvider_v2.mq5

<interfaces>
Existing contracts to preserve:

- `OrderDispatcher.enqueue_order(order_cmd)` is called by `run_trader()` after idempotency. Keep the public method name and return bool semantics.
- `OrderDispatcher.dispatch_loop()` and `OrderDispatcher.event_listener()` are launched as long-running tasks in `services/aureus-trader/main.py`.
- Redis channels from `config.py`: `ORDER_QUEUE_KEY`, `COMMANDS_CHANNEL = "aureus:mt5:commands"`, `EVENTS_CHANNEL = "aureus:mt5:events"`, `SIGNALS_CHANNEL_PREFIX`.
- MT5 accepted final events already handled by dispatcher: `ORDER_OPENED`, `ORDER_PENDING_PLACED`, `ORDER_FILLED`; rejection/failure uses `NACK` and `ORDER_FAILED`.
- Provider duplicate safety is business-critical: `AureusProvider_v2.mq5::ExecuteOpenOrder()` rejects active same `symbol + magic + direction` positions/orders with `STRATEGY_ORDER_EXISTS`. Do not weaken this.
</interfaces>

<constraints>
- Mọi trao đổi và summary phải dùng tiếng Việt.
- Before editing each function/class/method symbol, run GitNexus impact analysis if available: `gitnexus_impact({target: "OrderDispatcher", direction: "upstream"})`, `gitnexus_impact({target: "dispatch_loop", direction: "upstream"})`, `gitnexus_impact({target: "dispatch_order", direction: "upstream"})`, `gitnexus_impact({target: "event_listener", direction: "upstream"})`, `gitnexus_impact({target: "TraderConfig", direction: "upstream"})`, `gitnexus_impact({target: "load_config", direction: "upstream"})`, `gitnexus_impact({target: "run_trader", direction: "upstream"})`, `gitnexus_impact({target: "run_command_subscriber", direction: "upstream"})`, `gitnexus_impact({target: "ExecuteOpenOrder", direction: "upstream"})`. Report blast radius before editing. If MCP GitNexus tools are unavailable in this executor environment, document the fallback in SUMMARY and run CLI/query fallback if present; do not silently skip.
- Before any commit, run `gitnexus_detect_changes()` if available. Do not commit `.log`, `.ex5`, `services/aureus-signal/scripts/snapshots/`, `stable/`, or `tmp/` artifacts.
- Keep implementation surgical. Implement Phase 1-3 now. Phase 4 is limited to lightweight metrics/log hooks in gateway/provider; do not implement one OS process per order or a process pool.
- No DB schema/data changes. If implementation unexpectedly touches DB schema or journal persistence contracts, stop and add DB E2E verification before proceeding.
</constraints>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add explicit provider/gateway observability and SYMBOL_NOT_ALLOWED NACK</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5, D:/Aureus/services/aureus-gateway/main.py</files>
  <behavior>
    - Test/inspect 1: `ExecuteOpenOrder()` path where `FindContextIndex(symbol) < 0` calls `SendNACK(cmdId, "SYMBOL_NOT_ALLOWED")` and returns before ACK/order side effects.
    - Test/inspect 2: `run_command_subscriber()` logs per-command gateway write/drain latency with `cmd_id`, `symbol`, and command type without changing routing semantics.
    - Test/inspect 3: Provider logs lightweight receive/ACK/result timing when debug is enabled; logs must not create files and must not require new external dependencies.
  </behavior>
  <action>Run GitNexus impact analysis for `ExecuteOpenOrder` and `run_command_subscriber` before edits. In `AureusProvider_v2.mq5`, replace the currently commented silent `SYMBOL_NOT_ALLOWED` branch with a real `PrintFormat` guarded consistently with nearby debug style and `SendNACK(cmdId, "SYMBOL_NOT_ALLOWED")`; return immediately before `SendACK`/`RecordCmdId`. Add only lightweight timing/debug prints around provider receive/ACK/result path if needed for Phase 1 metrics; avoid broad refactors. In gateway `run_command_subscriber()`, measure elapsed time around `writer.write(...)` + `await writer.drain()` using event-loop monotonic time, log `cmd_id`, `symbol`, command type, and drain latency. Do not change active connection selection/routing.</action>
  <verify>
    <automated>python -m py_compile D:/Aureus/services/aureus-gateway/main.py</automated>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/mql5/AureusProvider_v2.mq5')
s = p.read_text(encoding='utf-8', errors='ignore')
assert 'SendNACK(cmdId, "SYMBOL_NOT_ALLOWED")' in s
assert 'writer.drain' in Path('D:/Aureus/services/aureus-gateway/main.py').read_text(encoding='utf-8')
PY</automated>
  </verify>
  <done>Unsupported symbols receive explicit `NACK:SYMBOL_NOT_ALLOWED`; gateway logs command forwarding/drain latency; no `.ex5`/`.log`/generated artifacts are produced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement bounded lane scheduler in OrderDispatcher</name>
  <files>D:/Aureus/services/aureus-trader/dispatcher.py, D:/Aureus/services/aureus-trader/config.py, D:/Aureus/services/aureus-trader/main.py</files>
  <behavior>
    - Test 1: If lane A has an ACK/result timeout, lane B with different `(symbol, magic, direction)` is published without waiting for lane A final timeout/backoff.
    - Test 2: Two orders with identical `(symbol, magic, direction)` are never published concurrently; second order waits until lane active state is released or marked reconcile-needed.
    - Test 3: Global in-flight cap prevents unbounded `asyncio.create_task` growth and is configurable through env with a safe default of 3 or 4.
  </behavior>
  <action>Run GitNexus impact analysis for `OrderDispatcher`, `dispatch_loop`, `dispatch_order`, `event_listener`, `TraderConfig`, `load_config`, and `run_trader` before edits. Refactor `OrderDispatcher` from global FIFO `await dispatch_order(order)` into a bounded async lane scheduler keyed exactly by `f"{symbol}:{magic}:{direction}"`. Keep Redis list as ingress queue and preserve `enqueue_order()` API. Add config fields such as `max_in_flight_orders` and `scheduler_poll_interval` loaded from env. Use in-memory per-lane queues/active set plus a global semaphore/counter; do not create OS processes. `dispatch_loop()` should dequeue, assign to lane, and schedule ready lanes while continuing to poll. `dispatch_order()` may remain the per-order coroutine but must release the lane only through explicit state outcome rules from Task 3. Keep payload allowlist `_extract_mt5_execution_payload()` unchanged except where required for metrics. Ensure shutdown cancels child tasks cleanly when `stop()` is called.</action>
  <verify>
    <automated>python -m py_compile D:/Aureus/services/aureus-trader/dispatcher.py D:/Aureus/services/aureus-trader/config.py D:/Aureus/services/aureus-trader/main.py</automated>
    <automated>python - <<'PY'
from pathlib import Path
s = Path('D:/Aureus/services/aureus-trader/dispatcher.py').read_text(encoding='utf-8')
assert 'symbol' in s and 'magic' in s and 'direction' in s
assert 'create_task' in s
assert 'max_in_flight' in s or 'max_inflight' in s
PY</automated>
  </verify>
  <done>Independent lanes can dispatch concurrently within the cap; same lane remains serialized; existing `run_trader()` startup/shutdown still works; no DB changes are introduced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add ACK/result state machine and reconcile-needed timeout semantics</name>
  <files>D:/Aureus/services/aureus-trader/dispatcher.py</files>
  <behavior>
    - Test 1: `NACK:SYMBOL_NOT_ALLOWED`, `NACK:STRATEGY_ORDER_EXISTS`, and other non-retryable NACKs publish `ORDER_REJECTED` with the original event type/reason and release the lane.
    - Test 2: ACK timeout is classified as `ACK_TIMEOUT_NO_PROVIDER_RESPONSE`; retry uses the same `cmd_id` and bounded retry policy; after max retries it publishes rejection with that classification.
    - Test 3: After ACK, `ORDER_FAILED` final failure is handled as final failure/retryable by existing `is_retryable()` rules; successful `ORDER_OPENED`/`ORDER_PENDING_PLACED`/`ORDER_FILLED` still invokes existing journal handlers.
    - Test 4: Result timeout after ACK is classified as `RESULT_TIMEOUT_AFTER_ACK`, marked ambiguous/reconcile-needed, does not publish generic business rejection, and does not flood retry the same lane before reconcile classification.
    - Test 5: `NACK:DUPLICATE` after an ACK timeout is classified/logged as `ACK_LOST_DUPLICATE_RECOVERY` and triggers reconcile-needed instead of simple business rejection.
  </behavior>
  <action>Run GitNexus impact analysis for `dispatch_order`, `event_listener`, `_wait_for_response`, `_handle_rejection`, and `_handle_max_retries` before edits. Replace the implicit two-future wait with an explicit per-cmd state record (`PUBLISHED`, `ACKED`, `NACKED`, `FINAL_SUCCESS`, `FINAL_FAILED`, `ACK_TIMEOUT_NO_PROVIDER_RESPONSE`, `RESULT_TIMEOUT_AFTER_ACK`, `ACK_LOST_DUPLICATE_RECOVERY`, `RECONCILE_NEEDED`). Event listener should transition by `cmd_id` and accept late final results if the command is still known. Preserve current journal calls for success events by reusing `_prepare_journal_event()`. For reconcile in this quick, implement a lightweight hook that publishes/logs a `RECONCILE_NEEDED` alert/event with `cmd_id`, `trace_id`, `symbol`, `magic`, `direction`, and timeout class; do not build a full MT5 query engine unless existing REQUEST_* flow can be reused surgically. Update retry/release rules so lanes release on definitive NACK/final success/final non-retryable failure/max ACK retries, but ambiguous result timeout is explicitly marked and not treated as generic max retries rejection. Keep the implementation compact and avoid speculative persistence.</action>
  <verify>
    <automated>python -m py_compile D:/Aureus/services/aureus-trader/dispatcher.py</automated>
    <automated>python - <<'PY'
from pathlib import Path
s = Path('D:/Aureus/services/aureus-trader/dispatcher.py').read_text(encoding='utf-8')
for token in ['RESULT_TIMEOUT_AFTER_ACK', 'ACK_TIMEOUT_NO_PROVIDER_RESPONSE', 'ACK_LOST_DUPLICATE_RECOVERY', 'RECONCILE_NEEDED']:
    assert token in s, token
assert 'ORDER_OPENED' in s and 'ORDER_PENDING_PLACED' in s and 'ORDER_FILLED' in s
PY</automated>
  </verify>
  <done>Dispatcher has explicit ACK/result state classification, preserves successful journal behavior, avoids treating post-ACK timeout as ordinary rejection, and emits reconcile-needed signal/log for ambiguous cases.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis signals -> trader | Strategy events are consumed from pub/sub and converted into order commands. |
| Trader -> Redis commands -> gateway | Order command JSON crosses service boundary and must stay allowlisted/idempotent. |
| Gateway -> MT5 TCP provider | Command JSON crosses into MT5 terminal/EA where trading side effects occur. |
| MT5 provider -> Redis events -> trader | ACK/NACK/result events drive state transitions and journal side effects. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260430-uij-01 | Tampering | `AureusProvider_v2.mq5::ExecuteOpenOrder` | mitigate | Keep required-field validation, provider idempotency, and add explicit `SYMBOL_NOT_ALLOWED` NACK before ACK/order side effects. |
| T-260430-uij-02 | Denial of Service | `OrderDispatcher.dispatch_loop` lane scheduler | mitigate | Bounded `max_in_flight_orders`; same-lane serialization; no unbounded tasks or OS-process-per-order. |
| T-260430-uij-03 | Repudiation | ACK/result state handling | mitigate | Log/metric every state transition by `cmd_id`, symbol, magic, direction, and timeout class. |
| T-260430-uij-04 | Elevation of Privilege | MT5 command payload | mitigate | Preserve `_extract_mt5_execution_payload()` allowlist; do not forward internal `strategy_event` to MT5. |
| T-260430-uij-05 | Information Disclosure | Logs | accept | Logs contain order metadata already present in existing operational logs; do not log secrets/env vars or full strategy snapshots. |
</threat_model>

<verification>
Run the automated checks in all tasks. Additionally run whichever project tests already exist for trader dispatch if discoverable without broad refactor. If GitNexus is available, run `gitnexus_detect_changes()` before finishing/committing and confirm only the planned dispatch/gateway/provider symbols changed.

No DB E2E needed because this plan does not change schema, database writes, or journal table contracts. If the executor changes DB-related code unexpectedly, stop and add DB E2E with real database before claiming done.
</verification>

<success_criteria>
- `SYMBOL_NOT_ALLOWED` no longer causes ACK timeout; provider sends NACK.
- Global head-of-line blocking is removed for independent `symbol + magic + direction` lanes with bounded concurrency.
- Same-lane safety is preserved.
- ACK timeout, NACK, final failure, result timeout after ACK, duplicate-after-ACK-timeout recovery are distinct in code/logs/alerts.
- Phase 4 is not overbuilt: only lightweight gateway/provider metrics hooks are added unless metrics prove bottleneck later.
- No generated `.ex5`, `.log`, snapshots, `stable/`, or `tmp/` files are committed.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260430-uij-implement-optimized-mt5-order-dispatch-r/260430-uij-SUMMARY.md` in Vietnamese with GitNexus impact/detect_changes results, files changed, verification commands, and whether any DB E2E was needed.
</output>
