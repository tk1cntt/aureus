---
phase: quick-260503-nqu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
autonomous: true
requirements:
  - QUICK-260503-NQU
must_haves:
  truths:
    - "STRATEGY_MATCH không tạo aureus_reasoning_entries khi trace_id chưa có parent aureus_trades, nên không còn FK violation."
    - "ORDER_OPENED sau khi journal/snapshot đã có dữ liệu sẽ tạo hoặc cập nhật aureus_reasoning_entries hợp lệ, có trade_journal_id và signal_snapshot_id."
    - "Reasoning insert/enqueue lỗi vẫn chỉ warning và không block order/journal flow."
    - "Không fake reasoning data, không xóa FK, không làm yếu database integrity."
  artifacts:
    - path: "services/aureus-trader/journal.py"
      provides: "Safe parent-aware reasoning entry persistence in TradeJournalManager"
      contains: "aureus_trades"
    - path: "services/aureus-trader/tests/test_journal.py"
      provides: "Unit regression coverage for missing parent trace_id and delayed reasoning insert"
      contains: "FK"
    - path: "services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
      provides: "DB/runtime E2E proof for no-parent deferral and parent-valid insert"
      contains: "aureus_trades"
  key_links:
    - from: "services/aureus-trader/journal.py::on_strategy_match"
      to: "aureus_reasoning_entries"
      via: "skip/defer reasoning insert when aureus_trades parent missing"
      pattern: "aureus_trades"
    - from: "services/aureus-trader/journal.py::on_order_opened"
      to: "aureus_reasoning_entries"
      via: "insert/update after trade_journal_id and signal_snapshot_id exist and parent aureus_trades row is valid"
      pattern: "INSERT INTO aureus_reasoning_entries|UPDATE aureus_reasoning_entries"
---

<objective>
Fix Reasoning Bank FK violation when `on_strategy_match` tries inserting `aureus_reasoning_entries.trace_id` before matching parent row exists in `aureus_trades`.

Purpose: Preserve DB integrity and keep order flow non-blocking while still persisting real reasoning data once parent trade context is valid.
Output: One surgical journal fix, unit regression tests, DB/runtime E2E coverage.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_journal.py
@D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
@D:/Aureus/.planning/quick/260503-g9l-t-o-reasoning-text-sau-khi-aureus-trade-/260503-g9l-SUMMARY.md
@D:/Aureus/RUN_SERVICES.md

Assumptions:
- `aureus_reasoning_entries.trace_id` has FK to `aureus_trades.trace_id`; executor must confirm with DB/migration/schema before choosing exact SQL.
- Current failure happens because `on_strategy_match` inserts reasoning before `aureus_trades` parent exists.
- Preferred fix: defer reasoning insert until parent exists, or insert only after parent exists. Do not remove FK, disable constraints, or insert fake parent rows.

GitNexus requirement:
- Before editing `TradeJournalManager.on_strategy_match` or `TradeJournalManager.on_order_opened`, run GitNexus impact upstream for these symbols and report direct callers/affected flows/risk in execution notes.
- If GitNexus MCP/CLI command unavailable or target not found, document exact limitation and continue with source checks plus tests. Prior quick 260503-g9l saw `gitnexus impact` target issues and `detect-changes` CLI unavailable.
- Before commit, run `gitnexus_detect_changes()` if available; if unavailable, document fallback and use `git diff -- services/aureus-trader/journal.py services/aureus-trader/tests/test_journal.py services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py`.

Interfaces:
- `TradeJournalManager.on_strategy_match(event: dict) -> bool` creates `aureus_trade_journal` and currently attempts early `aureus_reasoning_entries` insert.
- `TradeJournalManager.on_order_opened(event: dict) -> bool` updates journal to EXECUTED, inserts `aureus_trade_signal_snapshots`, then updates missing reasoning text/link fields.
- `select_embedding_sources(payload: dict)` returns sources for embedding enqueue; enqueue failures must remain warning-only.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regression tests for missing aureus_trades parent</name>
  <files>services/aureus-trader/tests/test_journal.py</files>
  <behavior>
    - Test 1: `on_strategy_match` with valid journal payload but no `aureus_trades` parent returns True and does not execute early `INSERT INTO aureus_reasoning_entries`.
    - Test 2: same path logs/records non-blocking deferral/skip behavior, not an exception that breaks caller.
    - Test 3: `on_order_opened` path still writes or links `aureus_reasoning_entries` only after `trade_journal_id`/`signal_snapshot_id` exist and parent validity can be checked.
  </behavior>
  <action>Add focused unit tests around existing `TestReasoningBank`. Use existing mock DB style. Tests must fail against current code because `on_strategy_match` still attempts early reasoning insert. Do not broaden fixture design. Do not change production code in this task.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py::TestReasoningBank -q"</automated>
  </verify>
  <done>Regression tests prove current FK-risky early reasoning insert behavior is gone and deferred/parent-aware behavior is expected.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Make reasoning entry persistence parent-aware and non-blocking</name>
  <files>services/aureus-trader/journal.py, services/aureus-trader/tests/test_journal.py</files>
  <behavior>
    - `on_strategy_match` creates `aureus_trade_journal` as before, but does not insert `aureus_reasoning_entries` when `aureus_trades` lacks matching `trace_id`.
    - If executor chooses to keep early insert for cases where parent exists, SQL must explicitly check parent first inside same acquired connection and still be warning-only.
    - `on_order_opened` creates or updates exactly one reasoning entry after journal/snapshot link exists and parent `aureus_trades` row is present; existing upstream reasoning text must not be overwritten.
    - Missing parent or reasoning insert error never breaks main order flow; return values remain aligned with journal update result.
  </behavior>
  <action>Run GitNexus impact first for `on_strategy_match` and `on_order_opened`. Then change only necessary reasoning persistence code. Prefer moving initial `aureus_reasoning_entries` creation out of `on_strategy_match` and into the post-snapshot/parent-valid `on_order_opened` path, using real fields already available (`trace_id`, `trade_journal_id`, `strategy_id`, `strategy_name`, `symbol`, `direction`, `confidence`, `active_signals`, `context_filters`, generated/upstream reasoning text, prompt/context aliases). Use `ON CONFLICT` or update pattern only if schema supports it; do not create duplicate reasoning rows. Keep Redis embedding enqueue warning-only. Do not fake reasoning data, do not insert placeholder parent `aureus_trades`, do not remove/weaken FK.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py -q"</automated>
  </verify>
  <done>No FK-risky early reasoning insert remains; normal strategy/order lifecycle still links reasoning entry and snapshot; all journal tests pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extend DB/runtime E2E to prove FK-safe lifecycle</name>
  <files>services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py, services/aureus-trader/journal.py, services/aureus-trader/tests/test_journal.py</files>
  <behavior>
    - E2E first calls `on_strategy_match` for a fresh trace_id with no `aureus_trades` parent and proves no `aureus_reasoning_entries` row exists and no exception occurs.
    - E2E then creates valid parent `aureus_trades` row for another trace_id, runs `on_strategy_match` plus `on_order_opened`, and proves exactly one linked `aureus_reasoning_entries` row exists.
    - E2E cleanup deletes reasoning, snapshots, journal, and trades rows for generated trace_ids.
  </behavior>
  <action>Update existing E2E script minimally using current `_cleanup` and `_ensure_schema` helpers. Add no-parent regression section before existing happy path. Keep data real and deterministic. If DB/services are down, follow `RUN_SERVICES.md`; document blocker only after attempting prescribed startup. After tests, run GitNexus detect changes if available and document exact scope.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"</automated>
  </verify>
  <done>DB E2E proves missing parent no longer causes FK violation and valid parent lifecycle still creates linked reasoning row.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis event to trader journal | Untrusted event payload fields become DB values. |
| Trader service to Postgres | Journal/reasoning persistence must preserve FK integrity. |
| Trader service to Redis embedding queue | Optional enqueue must not block order lifecycle. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-NQU-01 | Tampering | `on_strategy_match` reasoning insert | mitigate | Require parent-aware insert/defer; never create fake parent rows or weaken FK. |
| T-260503-NQU-02 | Denial of Service | Reasoning insert/enqueue | mitigate | Keep all reasoning persistence/enqueue failures warning-only so main journal/order flow continues. |
| T-260503-NQU-03 | Information Disclosure | Reasoning text fields | accept | No new fields or endpoints; preserve existing prompt/context copy-only behavior from prior quick 260503-g9l. |
</threat_model>

<verification>
Run in order:
1. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py -q"`
2. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && AUREUS_DB_DSN=postgresql://aureus:aureus_password@localhost:5433/aureus ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"`
3. GitNexus detect changes if available; otherwise record exact unavailable command/tool result plus git diff scope.
</verification>

<success_criteria>
- FK violation `aureus_reasoning_entries_trace_id_fkey` cannot occur from `on_strategy_match` when `aureus_trades` parent is absent.
- Valid parent lifecycle creates exactly one reasoning entry linked to journal and snapshot.
- Order/journal flow remains non-blocking on reasoning persistence and embedding errors.
- No FK removal, no fake reasoning data, no fake parent rows.
- Unit and DB/runtime E2E verification pass or DB blocker is documented after `RUN_SERVICES.md` attempt.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-nqu-fixbug-journal-reasoning-entry-insert-fa/260503-nqu-SUMMARY.md`.
</output>
