---
phase: 260503-sxx-fix-aureus-reasoning-entries-fk-blocking
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
  - QUICK-260503-SXX
must_haves:
  truths:
    - "Khi ORDER_OPENED tạo reasoning entry mà aureus_trades chưa có parent trace_id, hệ thống vẫn persist aureus_reasoning_entries với reasoning_text thật."
    - "FK từ aureus_reasoning_entries.trace_id sang aureus_trades(trace_id) không còn chặn Reasoning Bank insert trong lifecycle hợp lệ."
    - "Giải pháp ưu tiên giữ DB-consistency bằng minimal parent aureus_trades row, không loosen/remove FK trừ khi schema runtime chứng minh không thể tạo parent hợp lệ."
    - "Real DB E2E chứng minh row aureus_reasoning_entries tồn tại và reasoning_text persisted cho scenario trước đây fail FK."
  artifacts:
    - path: "services/aureus-trader/journal.py"
      provides: "Production fix tạo/đảm bảo parent aureus_trades trước reasoning insert"
      contains: "aureus_trades"
    - path: "services/aureus-trader/tests/test_journal.py"
      provides: "Unit regression coverage cho parent ensure trước reasoning insert"
      contains: "INSERT INTO aureus_trades"
    - path: "services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
      provides: "Real DB E2E scenario no-parent phải có reasoning row và reasoning_text"
      contains: "no_parent_reasoning_count == 1"
  key_links:
    - from: "services/aureus-trader/journal.py:on_order_opened"
      to: "aureus_trades"
      via: "minimal parent upsert before aureus_reasoning_entries insert"
      pattern: "INSERT INTO aureus_trades"
    - from: "services/aureus-trader/journal.py:on_order_opened"
      to: "aureus_reasoning_entries"
      via: "reasoning insert after parent exists"
      pattern: "INSERT INTO aureus_reasoning_entries"
    - from: "services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
      to: "runtime TimescaleDB"
      via: "asyncpg real DB assertions"
      pattern: "SELECT COUNT\\(\\*\\) FROM aureus_reasoning_entries"
---

<objective>
Fix Reasoning Bank FK-blocking bug by making production lifecycle persist reasoning entries even when parent trade row is missing at reasoning time.

Purpose: user corrected previous work: catching E2E failure is not enough. System must INSERT data into aureus_reasoning_entries; FK must not silently suppress real reasoning persistence.
Output: surgical journal.py fix, unit regression, real DB E2E proving no-parent scenario persists reasoning_text.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_journal.py
@D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
@D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries.sql

Important current behavior observed in journal.py:
- on_order_opened currently checks `SELECT 1 FROM aureus_trades WHERE trace_id = $1` before reasoning insert.
- If parent missing, code logs deferral and skips INSERT INTO aureus_reasoning_entries.
- Migration has `trace_id TEXT NOT NULL REFERENCES aureus_trades(trace_id) ON DELETE CASCADE`, so raw reasoning insert fails unless parent exists.
- Existing E2E currently expects no-parent reasoning_count == 0; this expectation is now wrong per user correction.

Implementation preference:
- Prefer DB-consistent minimal parent creation in aureus_trades before reasoning insert if runtime schema allows required columns.
- Do not remove/loosen FK unless executor proves minimal parent cannot satisfy schema. If schema change becomes necessary, add exact migration/source file and explain evidence in SUMMARY.

Project rules:
- Mọi trao đổi và SUMMARY dùng tiếng Việt markdown, không HTML.
- Backend commands via WSL only: `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ..."`.
- Python tests use `./.venv/bin/python -m pytest`.
- DB behavior change requires real DB E2E proving data created.
- Before editing journal.py symbols, run GitNexus impact. If GitNexus CLI/MCP unavailable, document limitation in SUMMARY and do not pretend it ran.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regression tests for no-parent reasoning persistence</name>
  <files>D:/Aureus/services/aureus-trader/tests/test_journal.py, D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py</files>
  <behavior>
    - Unit: on_order_opened with journal_row and snapshot should issue minimal parent `INSERT INTO aureus_trades` before `INSERT INTO aureus_reasoning_entries` when parent is missing.
    - Unit: reasoning insert remains non-blocking if parent ensure or reasoning insert fails, but success path must no longer skip insert because parent was absent.
    - E2E: no_parent_trace_id scenario must produce exactly 1 aureus_reasoning_entries row with non-empty reasoning_text containing strategy_name, symbol, direction, session/facts after ORDER_OPENED, without pre-inserting aureus_trades manually.
  </behavior>
  <action>Update tests before production code. In test_journal.py, replace stale assertions that no-parent strategy only defers reasoning with assertions around on_order_opened query order: parent ensure/upsert into aureus_trades must happen before reasoning insert. Keep on_strategy_match behavior as journal-only if no snapshot exists. In verify_reasoning_bank_reuse_e2e.py, change no_parent_trace_id flow to call on_strategy_match then on_order_opened for that trace without manual aureus_trades insert; assert aureus_trade_journal count == 1, aureus_trade_signal_snapshots count == 1, aureus_reasoning_entries count == 1, reasoning_text is non-empty and contains no-parent strategy/symbol/direction/context facts. Preserve cleanup order deleting reasoning/snapshot/journal/trades.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py -q"</automated>
  </verify>
  <done>Tests fail before production fix for missing parent behavior, then pass after Task 2. No test expects no_parent_reasoning_count == 0.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ensure minimal aureus_trades parent before reasoning insert</name>
  <files>D:/Aureus/services/aureus-trader/journal.py</files>
  <behavior>
    - Given ORDER_OPENED has valid trace_id/ticket/price/time and matching journal row, on_order_opened creates/ensures aureus_trades row for trace_id before reasoning insert.
    - Parent row uses available safe values: trace_id, symbol, direction, entry_type, entry_price, status, and ticket if schema accepts it. Use existing aureus_trades defaults for other columns.
    - Existing parent row must not be overwritten destructively. Use `ON CONFLICT (trace_id) DO NOTHING` or equivalent no-op/upsert compatible with existing unique constraint.
    - Reasoning insert writes real generated reasoning_text, not placeholder/static text.
  </behavior>
  <action>Run GitNexus impact before editing: `npx gitnexus impact --target TradeJournalManager --direction upstream` or available GitNexus MCP equivalent; include blast radius in SUMMARY. In journal.py on_order_opened, remove skip branch that only checks parent_exists and logs deferral. Inside same transaction, before INSERT INTO aureus_reasoning_entries, execute minimal parent insert/upsert into aureus_trades for trace_id. Prefer SQL like `INSERT INTO aureus_trades (trace_id, symbol, direction, entry_type, entry_price, status, ticket) VALUES (...) ON CONFLICT (trace_id) DO NOTHING`, but first inspect runtime/schema expectations from existing migrations/tests if needed; omit ticket column if aureus_trades does not have it. Keep FK intact in add_reasoning_entries.sql unless evidence proves parent cannot be created. Keep reasoning embedding enqueue behavior unchanged after successful reasoning insert. Keep exception handling non-blocking but log concrete failure.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py -q"</automated>
  </verify>
  <done>on_order_opened no longer skips reasoning insert solely because aureus_trades parent is absent; unit tests show parent ensure precedes reasoning insert; existing journal lifecycle tests pass.</done>
</task>

<task type="auto">
  <name>Task 3: Prove runtime DB persistence for previous FK failure</name>
  <files>D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py, D:/Aureus/.planning/quick/260503-sxx-fix-aureus-reasoning-entries-fk-blocking/260503-sxx-SUMMARY.md</files>
  <action>Run real DB E2E through WSL per RUN_SERVICES.md. If services are down, start core backend with `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./scripts/dev-service.sh"` then rerun. Execute `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"`. After E2E, run GitNexus detect changes before any commit: `npx gitnexus detect-changes` or available MCP equivalent; document limitations if unavailable. Create SUMMARY with exact commands, pass/fail evidence, trace_ids printed by script, and whether FK was preserved or schema changed.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"</automated>
  </verify>
  <done>Real DB E2E exits 0 and proves no-parent scenario has aureus_reasoning_entries row with persisted reasoning_text. SUMMARY exists and records evidence plus GitNexus impact/detect status.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis event to trader DB writer | Event payload supplies trace_id, symbol, direction, strategy data used for DB writes. |
| Trader service to TimescaleDB | Service writes journal, parent trade, snapshot, reasoning rows. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-sxx-01 | Tampering | on_order_opened parent ensure | mitigate | Use parameterized asyncpg SQL only; never format trace_id/symbol/direction into SQL strings. |
| T-260503-sxx-02 | Integrity | aureus_trades minimal parent row | mitigate | Use ON CONFLICT DO NOTHING to avoid overwriting existing real trade data. Populate only schema-required safe fields from validated ORDER_OPENED/journal data. |
| T-260503-sxx-03 | Denial of Service | Reasoning insert path | mitigate | Preserve existing non-blocking exception handling so trade dispatch lifecycle does not fail if reasoning write/enqueue fails. |
| T-260503-sxx-04 | Information Disclosure | reasoning_text | mitigate | Continue generating reasoning_text from journal/snapshot facts only; do not persist prompt_text/context_text/raw secrets in reasoning entry. |
</threat_model>

<verification>
Overall commands:
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py -q"`
- `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"`
- GitNexus impact before journal.py edit; GitNexus detect changes before commit/finish.
</verification>

<success_criteria>
- Production source fix exists in journal.py, not only test tightening.
- FK remains preserved unless executor documents concrete schema evidence requiring migration.
- No-parent reasoning lifecycle creates/ensures aureus_trades parent and then inserts aureus_reasoning_entries.
- reasoning_text is generated from persisted journal/snapshot data and persists in real DB.
- Unit tests and real DB E2E both pass.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-sxx-fix-aureus-reasoning-entries-fk-blocking/260503-sxx-SUMMARY.md`.
</output>
