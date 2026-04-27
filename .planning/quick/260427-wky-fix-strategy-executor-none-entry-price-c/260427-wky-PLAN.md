---
phase: quick-260427-wky-fix-strategy-executor-none-entry-price-c
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/strategy_executor.py
  - services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py
autonomous: true
requirements:
  - QUICK-260427-WKY
must_haves:
  truths:
    - "Strategy executor không gọi float(None) khi entry_method trả None/rejected."
    - "Rejected/None entry result được skip/reject sạch bằng warning/log và message vẫn được ack, không crash toàn bộ xử lý entry."
    - "Các strategy result có entry_price hợp lệ vẫn publish/process như hiện tại."
  artifacts:
    - path: "services/aureus-signal/engine/strategy_executor.py"
      provides: "Guard tại bước publish/process strategy match để bỏ qua result có computed entry_price=None trước khi float()."
      contains: "computed_ep is None"
    - path: "services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py"
      provides: "Regression test chứng minh None entry_price không publish strategy match và không gọi float(None)."
  key_links:
    - from: "SimulatedTradeManager._calculate_entry_price"
      to: "strategy_executor publish_strategy_match loop"
      via: "computed_ep guard before _calculate_sl_tp and float(computed_ep)"
      pattern: "computed_ep.*is None"
---

<objective>
Fix runtime crash trong Strategy Executor khi `orders.py` trả `None` cho entry methods bị reject như `OB_EDGE` không có order blocks.

Purpose: `orders.py` đã chuyển các entry method không đủ dữ liệu sang reject sạch bằng `None`; executor phải tôn trọng contract này và không ép `float(None)`.
Output: Guard nhỏ trong executor và regression test nhắm đúng lỗi runtime `float() argument must be a string or a real number, not 'NoneType'`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/services/aureus-signal/engine/strategy_executor.py
@D:/Aureus/services/aureus-signal/engine/orders.py
@D:/Aureus/services/aureus-signal/tests/test_signal_event_publisher.py

<bug_evidence>
Runtime log after restart:
`engine.strategy_executor - ERROR - [EXECUTOR][USTEC] Error processing entry 1777306381628-0: float() argument must be a string or a real number, not 'NoneType'`
Traceback line: `/app/engine/strategy_executor.py`, line 648, `res['entry_price'] = float(computed_ep)`.

Root cause contract: `SimulatedTradeManager._calculate_entry_price(...)` can now return `None` for rejected entry methods. Example from `orders.py`: `[orders] OB_EDGE has no order blocks — order rejected`.
</bug_evidence>

<interfaces>
Key contracts:
```python
# services/aureus-signal/engine/orders.py
class SimulatedTradeManager:
    def _calculate_entry_price(self, side: str, state_obj: Any, entry_method: str = "CURRENT", entry_value: Any = None) -> Optional[float]: ...
    def _calculate_sl_tp(self, trigger: Dict[str, Any], state_obj: Any, config: Dict[str, Any], entry_price_override: float = None, recent_candles: Optional[List[Dict[str, Any]]] = None): ...

# services/aureus-signal/engine/strategy_executor.py current failing area
computed_ep = trade_manager._calculate_entry_price(_side, executor_state, entry_method, entry_value)
abs_sl, abs_tp = trade_manager._calculate_sl_tp(..., entry_price_override=computed_ep, ...)
res['entry_price'] = float(computed_ep)
await publish_strategy_match(r, symbol, res, active_signals=signals_snapshot)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regression test for None entry price rejection path</name>
  <files>services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py</files>
  <behavior>
    - Given a strategy result with `order_plan.entry_method="OB_EDGE"` and executor state without order blocks, the executor-side publish preparation must not call `float(None)`.
    - The rejected result must not call `publish_strategy_match`.
    - A warning/log path should make the skip observable with symbol, strategy, entry_method, and reason that entry price is unavailable.
  </behavior>
  <action>Create the smallest focused pytest regression around the strategy_executor helper/guard introduced in Task 2. If no helper exists yet, write the test against the intended small helper name first, then implement it. Follow existing test import style: insert `services/aureus-signal` onto `sys.path`, use `pytest`, `AsyncMock` if publish is async. Do not start Redis, Docker, or DB for this unit test.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py -q"</automated>
  </verify>
  <done>Test fails before the executor guard because the current path attempts `float(None)` or would publish an invalid result; after Task 2 it passes and asserts no publish on None entry price.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Guard strategy executor publish path when computed entry price is None</name>
  <files>services/aureus-signal/engine/strategy_executor.py, services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py</files>
  <behavior>
    - `computed_ep is None` must short-circuit before `_calculate_sl_tp(...)`, before `float(computed_ep)`, and before `publish_strategy_match(...)`.
    - The log should be warning-level and include `[EXECUTOR][{symbol}]`, strategy name/id if present, entry_method, and `ENTRY_PRICE_UNAVAILABLE` or equivalent explicit reason.
    - Valid numeric `computed_ep` behavior remains unchanged: SL/TP calculated, `entry_price` cast to float, indicator_snapshot set, and strategy match published.
  </behavior>
  <action>Before editing, run GitNexus impact analysis for the modified executor symbol(s), at minimum `run_strategy_executor`, and report direct callers/affected flows/risk in the execution summary. If GitNexus CLI/MCP is unavailable, document that limitation in the summary and proceed with targeted diff/tests. Implement a surgical guard in the existing `for res in strategy_results:` publish loop in `strategy_executor.py`: after `computed_ep = trade_manager._calculate_entry_price(...)`, if `computed_ep is None`, log warning and `continue`. Do not change `orders.py` rejection semantics and do not add fallback prices, because rejected entry methods must stay rejected cleanly.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py services/aureus-signal/tests/test_signal_event_publisher.py -q"</automated>
  </verify>
  <done>Executor no longer has a code path where `float(computed_ep)` can run with `computed_ep is None`; existing strategy match publisher tests still pass.</done>
</task>

<task type="auto">
  <name>Task 3: Verify scope and runtime-facing evidence</name>
  <files>services/aureus-signal/engine/strategy_executor.py, services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py</files>
  <action>Run `gitnexus_detect_changes()` before any commit if GitNexus is available; confirm only expected symbols/files changed. Then run a targeted diff review and the pytest command from Task 2. If services are running and runtime verification is practical, restart only `aureus-strategy-executor-dev` because Python files are volume-mounted, then inspect recent logs for absence of `float() argument ... NoneType` and presence of the new skip warning when a rejected entry occurs. Use RUN_SERVICES.md commands; do not rebuild unless requirements/Dockerfile changed.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py services/aureus-signal/tests/test_signal_event_publisher.py -q"</automated>
    <automated>npx gitnexus detect-changes || true</automated>
  </verify>
  <done>Targeted tests pass; GitNexus detect-changes or documented fallback confirms expected scope; executor runtime logs no longer show `float(None)` crash after rejected entry result.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis signal stream -> strategy executor | Payloads and strategy evaluation outputs may contain incomplete order plans or missing market structure data. |
| Strategy executor -> Redis pub/sub/orders stream | Only valid strategy matches should be published downstream; rejected/incomplete entries should not masquerade as executable orders. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260427-WKY-01 | D | strategy_executor publish loop | mitigate | Guard `computed_ep is None` before SL/TP calculation, `float()`, and publish so one rejected order plan cannot crash message processing. |
| T-260427-WKY-02 | T | strategy match payload | mitigate | Do not invent fallback entry_price; skip/reject invalid entry result so downstream MT5/trader never receives fabricated price. |
| T-260427-WKY-03 | R | rejection observability | mitigate | Warning log includes symbol/strategy/entry_method/reason for auditability of skipped strategy match. |
</threat_model>

<verification>
Run targeted unit/regression tests through WSL `.venv`:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_strategy_executor_entry_price_rejection.py services/aureus-signal/tests/test_signal_event_publisher.py -q"
```

Optional runtime check if services are up:

```bash
wsl -d Aureus -e bash -lc "docker restart aureus-strategy-executor-dev"
wsl -d Aureus -e bash -lc "docker logs --since 5m aureus-strategy-executor-dev 2>&1 | tail -n 200"
```
</verification>

<success_criteria>
- `strategy_executor.py` never executes `float(None)` for rejected entry methods.
- None entry_price result is skipped/rejected cleanly with warning/log and does not crash processing of the Redis entry.
- Valid entry_price strategy matches keep existing publish behavior.
- Regression test covers the None entry path.
- GitNexus impact/detect-changes gates are run, or limitation is documented with targeted diff/tests fallback.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260427-wky-fix-strategy-executor-none-entry-price-c/260427-wky-SUMMARY.md`.
</output>
