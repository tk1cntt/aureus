---
phase: quick-260504-pyn-remove-active-signals-from-reasoning-tex
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py
  - services/aureus-db-writer/migrations/add_reasoning_entries.sql
  - services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql
autonomous: true
requirements:
  - QUICK-260504-PYN
must_haves:
  truths:
    - "reasoning_text không còn chứa thông tin active_signals từ journal_row hoặc signal_snapshot."
    - "Bảng aureus_reasoning_entries trong DB thật không còn cột active_signals sau migration."
    - "Runtime DB thật không còn index idx_reasoning_entries_active_signals sau migration."
    - "Luồng ORDER_OPENED vẫn tạo được row aureus_reasoning_entries thật, có reasoning_text hợp lệ và link trade_journal_id/signal_snapshot_id."
  artifacts:
    - path: "services/aureus-trader/journal.py"
      provides: "Reasoning entry insert không ghi active_signals và generated reasoning_text loại bỏ active_signals."
    - path: "services/aureus-db-writer/migrations/add_reasoning_entries.sql"
      provides: "Schema nguồn aureus_reasoning_entries không khai báo active_signals hoặc GIN index liên quan."
    - path: "services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql"
      provides: "Migration idempotent xóa index/cột active_signals khỏi DB đang chạy."
    - path: "services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py"
      provides: "DB E2E tạo dữ liệu thật và assert cột active_signals cùng index idx_reasoning_entries_active_signals đã bị xóa."
  key_links:
    - from: "TradeJournalManager.on_order_opened"
      to: "aureus_reasoning_entries"
      via: "INSERT không có active_signals column"
      pattern: "INSERT INTO aureus_reasoning_entries"
    - from: "_build_reasoning_text"
      to: "reasoning_text"
      via: "snapshot/journal facts builder excludes active_signals"
      pattern: "active_signals"
    - from: "drop_reasoning_entries_active_signals.sql"
      to: "runtime Postgres"
      via: "psql migration before E2E"
      pattern: "DROP COLUMN IF EXISTS active_signals"
    - from: "verify_reasoning_bank_trigger_to_entry_e2e.py"
      to: "runtime Postgres metadata"
      via: "information_schema.columns plus pg_indexes/pg_class assertions"
      pattern: "pg_indexes|pg_class"
---

<objective>
Xóa active_signals khỏi Reasoning Bank persistence.

Purpose: user muốn active_signals không còn nằm trong reasoning_text và không còn lưu trong bảng aureus_reasoning_entries.
Output: code insert đã sửa, schema source đã sửa, migration drop column/index, unit tests và DB E2E thật pass.
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
@D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py
@D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries.sql

Key current facts:
- `services/aureus-trader/journal.py` has `_build_reasoning_text(journal_row, snapshot_columns, signal_snapshot)` and `TradeJournalManager.on_order_opened()`.
- Current `on_order_opened()` inserts `active_signals, context_filters, reasoning_text, decision_action` into `aureus_reasoning_entries` around lines 636-653.
- Current source migration `add_reasoning_entries.sql` defines `active_signals JSONB` and `idx_reasoning_entries_active_signals`.
- `services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py` already starts from dispatcher path, uses runtime Postgres via `AUREUS_DB_DSN`, creates real rows, and asserts linked `aureus_reasoning_entries`.
- Existing uncommitted user work exists in `services/aureus-trader/journal.py`, `mql5/AureusProvider_v2.mq5`, plus untracked `mql5/AureusProvider_v2.ex5`, `stable/`. Executor must inspect `git diff -- services/aureus-trader/journal.py` before editing and preserve unrelated hunks. Do not touch MQL5 or stable files.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Remove active_signals from reasoning insert and text expectations</name>
  <files>services/aureus-trader/journal.py, services/aureus-trader/tests/test_journal.py</files>
  <behavior>
    - Test: post-snapshot generated reasoning_text includes strategy_name/symbol/direction/context_filters/snapshot facts, but not active_signals JSON or active signal tags.
    - Test: ORDER_OPENED reasoning insert SQL column list does not include active_signals and insert args no longer include active_signals payload.
  </behavior>
  <action>Before editing, run `git diff -- services/aureus-trader/journal.py services/aureus-trader/tests/test_journal.py` and preserve all unrelated user hunks. Run GitNexus blast radius before symbol edits: `gitnexus_impact({target: "_build_reasoning_text", direction: "upstream"})` and `gitnexus_impact({target: "TradeJournalManager.on_order_opened", direction: "upstream"})`; report direct callers/processes/risk in execution notes. Then update tests first. In `journal.py`, remove active_signals from `aureus_reasoning_entries` insert column list and args. Keep context_filters column unchanged. Keep active_signals in `aureus_trade_journal` and signal snapshot pipeline unchanged; user only requested Reasoning Bank removal. Ensure `_build_reasoning_text` cannot include active_signals from `journal_row` or raw `signal_snapshot`; remove any dead/commented active_signals text block if present, without broad refactor.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-trader/tests/test_journal.py -q</automated>
  </verify>
  <done>Unit tests pass; generated reasoning_text has no active_signals content; `INSERT INTO aureus_reasoning_entries` no longer references active_signals while journal/signal snapshot active_signals behavior remains intact.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add DB migration and update source schema</name>
  <files>services/aureus-db-writer/migrations/add_reasoning_entries.sql, services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql</files>
  <behavior>
    - Migration can run repeatedly without error.
    - Runtime schema after migration has no `aureus_reasoning_entries.active_signals` column and no `idx_reasoning_entries_active_signals` index.
  </behavior>
  <action>Update `add_reasoning_entries.sql` so new installs no longer create `active_signals JSONB` or `idx_reasoning_entries_active_signals`. Create `drop_reasoning_entries_active_signals.sql` with idempotent SQL: drop index if exists, then `ALTER TABLE aureus_reasoning_entries DROP COLUMN IF EXISTS active_signals;`. Do not remove `context_filters` or its index. Do not edit unrelated migrations. Prove idempotency by running this migration twice against same `AUREUS_DB_DSN`. After second run, query runtime Postgres metadata and assert both: `information_schema.columns` has no `active_signals` for `aureus_reasoning_entries`, and `pg_indexes` or `pg_class` has no `idx_reasoning_entries_active_signals`.</action>
  <verify>
    <automated>cd D:/Aureus && psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql && psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql && psql "$AUREUS_DB_DSN" -v ON_ERROR_STOP=1 -Atc "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'aureus_reasoning_entries' AND column_name = 'active_signals';" | grep -qx "0" && psql "$AUREUS_DB_DSN" -v ON_ERROR_STOP=1 -Atc "SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'idx_reasoning_entries_active_signals';" | grep -qx "0"</automated>
  </verify>
  <done>Source schema and migration agree; migration is idempotent over two consecutive runs; runtime aureus_reasoning_entries no longer has active_signals column or idx_reasoning_entries_active_signals index; context_filters remains present.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Prove runtime DB E2E creates reasoning row without column or index</name>
  <files>services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py</files>
  <behavior>
    - E2E applies/assumes migration, creates real dispatcher-triggered journal/snapshot/reasoning rows in Postgres, and asserts `information_schema.columns` has no active_signals for aureus_reasoning_entries.
    - E2E asserts `pg_indexes` or `pg_class` has no `idx_reasoning_entries_active_signals` for aureus_reasoning_entries.
    - E2E asserts reasoning_text is non-empty and does not contain `active_signals` or known active signal tag from test payload.
  </behavior>
  <action>Update existing DB E2E script so after setup it queries runtime Postgres metadata and asserts `aureus_reasoning_entries.active_signals` is absent and `idx_reasoning_entries_active_signals` is absent via `pg_indexes` or `pg_class`. Keep E2E starting from `OrderDispatcher.dispatch_order()`; do not insert/update aureus_reasoning_entries directly. Keep cleanup safe. Add assertions that generated `reasoning_text` does not include literal `active_signals` and does not include test active signal tag such as `cisd_bull`, while existing strategy/symbol/direction/session/CISD facts still pass. Run migration against the same DSN twice before E2E to prove idempotency: `psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql` repeated two times. If DB command fails due services not running, consult `RUN_SERVICES.md` before retry. Before finishing, run `gitnexus_detect_changes({scope: "all"})` and confirm only expected symbols/files/flows changed.</action>
  <verify>
    <automated>cd D:/Aureus && psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql && psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql && python services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py</automated>
  </verify>
  <done>Runtime Postgres has no aureus_reasoning_entries.active_signals column and no idx_reasoning_entries_active_signals index; migration succeeds twice; E2E prints PASS and creates then verifies one real linked reasoning row without active_signals in reasoning_text.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Strategy/MT5 event to trader service | Untrusted event payload crosses into journal persistence and reasoning text generation. |
| Trader service to Postgres | Application SQL mutates schema/data in runtime DB. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260504-PYN-01 | I | `_build_reasoning_text` | mitigate | Exclude active_signals from reasoning_text and add unit/E2E assertions for absent literal/tag. |
| T-260504-PYN-02 | T | `drop_reasoning_entries_active_signals.sql` | mitigate | Use idempotent `DROP INDEX IF EXISTS` and `DROP COLUMN IF EXISTS`; run twice against configured `AUREUS_DB_DSN`; E2E checks column and index absence after migration. |
| T-260504-PYN-03 | D | `on_order_opened` reasoning insert | mitigate | Keep non-blocking existing try/except around reasoning insert; unit and E2E ensure row still created after column/index removal. |
</threat_model>

<verification>
Run:
1. `cd D:/Aureus && python -m pytest services/aureus-trader/tests/test_journal.py -q`
2. `cd D:/Aureus && psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql && psql "$AUREUS_DB_DSN" -f services/aureus-db-writer/migrations/drop_reasoning_entries_active_signals.sql && psql "$AUREUS_DB_DSN" -v ON_ERROR_STOP=1 -Atc "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'aureus_reasoning_entries' AND column_name = 'active_signals';" | grep -qx "0" && psql "$AUREUS_DB_DSN" -v ON_ERROR_STOP=1 -Atc "SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'idx_reasoning_entries_active_signals';" | grep -qx "0" && python services/aureus-trader/scripts/verify_reasoning_bank_trigger_to_entry_e2e.py`
3. `gitnexus_detect_changes({scope: "all"})`
</verification>

<success_criteria>
- active_signals not present in reasoning_text.
- active_signals not present in aureus_reasoning_entries schema source or runtime DB.
- idx_reasoning_entries_active_signals not present in schema source or runtime DB.
- Drop migration runs twice successfully against same DB.
- Existing journal active_signals capture outside Reasoning Bank remains untouched.
- Real DB E2E creates data successfully and verifies linked reasoning row.
- Unrelated uncommitted files/hunks are preserved.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260504-pyn-remove-active-signals-from-reasoning-tex/260504-pyn-SUMMARY.md`.
</output>
