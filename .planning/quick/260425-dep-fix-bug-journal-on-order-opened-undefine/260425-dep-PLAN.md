---
phase: quick-260425-dep-fix-bug-journal-on-order-opened-undefine
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-trader/tests/conftest.py
autonomous: true
requirements:
  - QUICK-260425-DEP
must_haves:
  truths:
    - "ORDER_OPENED no longer queries nonexistent aureus_trade_journal.timeframe column."
    - "Snapshot/evaluation timeframe still comes from event payload when present, and existing fallback semantics are preserved when missing."
    - "Fix is surgical: no database migration and no new timeframe column dependency."
  artifacts:
    - path: "services/aureus-trader/journal.py"
      provides: "TradeJournalManager.on_order_opened UPDATE ... RETURNING clause and timeframe fallback fix"
      contains: "RETURNING id, strategy_name, symbol, active_signals, context_filters"
    - path: "services/aureus-trader/tests/test_journal.py"
      provides: "Regression test proving ORDER_OPENED SQL does not RETURN timeframe"
      contains: "RETURNING"
    - path: "services/aureus-trader/tests/conftest.py"
      provides: "Mock DB row matching production table without timeframe"
  key_links:
    - from: "services/aureus-trader/journal.py"
      to: "aureus_trade_journal"
      via: "UPDATE ... RETURNING in on_order_opened"
      pattern: "RETURNING id, strategy_name, symbol, active_signals, context_filters(?!, timeframe)"
    - from: "services/aureus-trader/tests/test_journal.py"
      to: "services/aureus-trader/journal.py"
      via: "pytest regression around captured SQL"
      pattern: "assert .*timeframe.* not in"
---

<objective>
Fix the production ORDER_OPENED journal crash caused by `TradeJournalManager.on_order_opened` returning a nonexistent `timeframe` column from `aureus_trade_journal`.

Purpose: Restore journal update + signal snapshot persistence for opened orders without changing the database schema.
Output: Surgical code change and regression coverage that prevent SQL from referencing `aureus_trade_journal.timeframe`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_journal.py
@D:/Aureus/services/aureus-trader/tests/conftest.py

Runtime error:
`UndefinedColumnError: column "timeframe" does not exist` at `services/aureus-trader/journal.py` inside `TradeJournalManager.on_order_opened`, introduced by recent quick task `260425-ch4` adding `timeframe` to `UPDATE aureus_trade_journal ... RETURNING`.

Constraints:
- Do not add a database migration for `timeframe`.
- Do not add a `timeframe` column to `aureus_trade_journal`.
- Preserve `trace_id` behavior and `_build_signal_snapshot_columns` mapping.
- Preserve event timeframe/default semantics: use `event.get("timeframe", "")`; downstream snapshot behavior may continue to default to `M1` if that is already the existing behavior.
- Project rule: before editing symbols, run GitNexus impact analysis and report blast radius. Before any commit, run `gitnexus_detect_changes()`.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regression coverage for ORDER_OPENED SQL compatibility</name>
  <files>services/aureus-trader/tests/test_journal.py, services/aureus-trader/tests/conftest.py</files>
  <behavior>
    - Test 1: calling `TradeJournalManager.on_order_opened(valid_order_opened_event)` captures an `UPDATE aureus_trade_journal ... RETURNING ...` SQL statement that does not contain `timeframe` in the RETURNING projection.
    - Test 2: the mocked journal row returned by `MockDBConnection.fetchrow` should not require or include a `timeframe` key, matching production schema compatibility.
  </behavior>
  <action>Run GitNexus impact analysis before editing: `gitnexus_impact({target: "TradeJournalManager.on_order_opened", direction: "upstream"})`; if modifying test fixture classes/methods, also run impact for the affected fixture symbol if GitNexus indexes it. Report direct callers, affected processes, and risk level. Then add a focused regression assertion in `TestOutboundOrderOpened` that inspects `mock_db_pool._conn.queries[0][1]` after `on_order_opened` and proves the `RETURNING` clause excludes `timeframe`. Adjust `MockDBConnection.fetchrow` default return in `tests/conftest.py` to remove the `"timeframe": None` key so tests catch accidental `journal_row.get("timeframe")` reliance only if code still asks for it. Do not broaden fixtures or refactor unrelated tests.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-trader && pytest tests/test_journal.py::TestOutboundOrderOpened -q</automated>
  </verify>
  <done>Regression test fails before the production fix because SQL still returns `timeframe`, and fixture row no longer models a journal table with `timeframe`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Remove nonexistent timeframe dependency from on_order_opened</name>
  <files>services/aureus-trader/journal.py</files>
  <behavior>
    - `UPDATE aureus_trade_journal` still updates order-open fields and returns `id`, `strategy_name`, `symbol`, `active_signals`, and `context_filters` only.
    - When a journal row is found, `strategy_name` and `symbol` can still fall back to returned row values.
    - `timeframe` is derived from `event.get("timeframe", "")` and never from `journal_row.get("timeframe")`.
  </behavior>
  <action>In `TradeJournalManager.on_order_opened`, remove `timeframe` from the SQL `RETURNING` clause. In the `journal_row` branch, replace `timeframe = event.get("timeframe", journal_row.get("timeframe", ""))` with event-only fallback `timeframe = event.get("timeframe", "")`. Keep all surrounding transaction, trace_id, `_build_signal_snapshot_columns`, evaluation insert, and snapshot insert behavior unchanged. Do not create migrations or schema changes.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-trader && pytest tests/test_journal.py::TestOutboundOrderOpened tests/test_journal.py::TestOnOrderOpenedInputValidation -q</automated>
  </verify>
  <done>ORDER_OPENED no longer references nonexistent `aureus_trade_journal.timeframe`; opened order flow still returns True for valid event and keeps event timeframe semantics.</done>
</task>

<task type="auto">
  <name>Task 3: Run targeted DB-related verification and scope checks</name>
  <files>services/aureus-trader/journal.py, services/aureus-trader/tests/test_journal.py, services/aureus-trader/tests/conftest.py</files>
  <action>Run the targeted unit regression first. Because this is DB-related, also run the best available E2E database-backed test for trader/journal if local services are available. Prefer `pytest tests/test_e2e_trader.py -q` from `services/aureus-trader`; if it fails due unavailable DB/service setup, read `D:/Aureus/RUN_SERVICES.md` and either start the documented services or record the exact infrastructure limitation in the SUMMARY while keeping the targeted regression as the blocking proof for the SQL bug. Finally run `gitnexus_detect_changes()` before any commit and verify only expected journal/test symbols and execution flows changed.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-trader && pytest tests/test_journal.py::TestOutboundOrderOpened tests/test_journal.py::TestOnOrderOpenedInputValidation -q</automated>
    <automated>cd D:/Aureus/services/aureus-trader && pytest tests/test_e2e_trader.py -q</automated>
  </verify>
  <done>Targeted tests pass; DB E2E passes or SUMMARY documents concrete environment blocker after consulting RUN_SERVICES.md; GitNexus change detection confirms expected scope.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5/dispatcher event → journal persistence | ORDER_OPENED event data crosses from external execution flow into database writes. |
| application SQL → PostgreSQL schema | Application query must match deployed production schema. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-dep-01 | D | `TradeJournalManager.on_order_opened` | mitigate | Remove nonexistent `timeframe` from `RETURNING` so one order-opened event cannot repeatedly fail journal persistence. |
| T-260425-dep-02 | T | `timeframe` value used for snapshots/evaluation | mitigate | Use event-provided `timeframe` only; do not trust a schema field that does not exist in production. |
| T-260425-dep-03 | R | Regression evidence | mitigate | Add SQL assertion proving `RETURNING` excludes `timeframe`; run targeted tests and best available DB E2E. |
</threat_model>

<verification>
1. GitNexus impact analysis is run and blast radius is reported before editing `TradeJournalManager.on_order_opened`.
2. `pytest tests/test_journal.py::TestOutboundOrderOpened tests/test_journal.py::TestOnOrderOpenedInputValidation -q` passes.
3. `pytest tests/test_e2e_trader.py -q` passes, or the SUMMARY records exact unavailable infrastructure and RUN_SERVICES.md guidance attempted.
4. `gitnexus_detect_changes()` confirms only expected journal/test scope changed before committing.
</verification>

<success_criteria>
- Production SQL no longer includes `RETURNING ... timeframe` for `aureus_trade_journal`.
- Code no longer reads `journal_row.get("timeframe")` in `on_order_opened`.
- Event timeframe/default behavior remains intact.
- No migration or schema addition for `timeframe` is introduced.
- Regression test protects against reintroducing the nonexistent column reference.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-dep-fix-bug-journal-on-order-opened-undefine/260425-dep-SUMMARY.md`.
</output>
