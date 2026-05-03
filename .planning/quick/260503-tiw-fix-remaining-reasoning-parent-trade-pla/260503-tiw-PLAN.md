---
phase: 260503-tiw-fix-remaining-reasoning-parent-trade-pla
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
  - services/aureus-db-writer/main.py
  - services/aureus-db-writer/tests/test_order_buffer.py
autonomous: true
requirements:
  - QUICK-260503-TIW
must_haves:
  truths:
    - "Reasoning insert never depends on hardcoded MARKET parent row when actual order data contains LIMIT or STOP."
    - "journal.py parent aureus_trades upsert uses available order fields from ORDER_OPENED/ORDER_FILLED instead of inserting trace_id + MARKET placeholder only."
    - "db-writer keeps canonical aureus_trades persistence and later order events enrich placeholder rows without losing existing non-null data."
    - "Real DB E2E creates aureus_trades, aureus_trade_journal, aureus_trade_signal_snapshots, aureus_reasoning_entries, and persisted reasoning_text for no-parent lifecycle."
  artifacts:
    - path: "services/aureus-trader/journal.py"
      provides: "FK-safe parent trade upsert with real entry_type/direction/symbol/ticket/price/volume/sl/tp/payload when available"
      contains: "INSERT INTO aureus_trades"
    - path: "services/aureus-db-writer/main.py"
      provides: "ON CONFLICT enrichment for all canonical aureus_trades fields from db-writer order events"
      contains: "ON CONFLICT (trace_id) DO UPDATE SET"
    - path: "services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
      provides: "Runtime DB proof for reasoning_text persistence and placeholder enrichment behavior"
      contains: "reasoning_text"
    - path: "services/aureus-db-writer/tests/test_order_buffer.py"
      provides: "Unit regression proving placeholder row gets enriched by canonical order payload"
      contains: "placeholder"
  key_links:
    - from: "services/aureus-trader/journal.py:on_order_opened"
      to: "aureus_trades"
      via: "parent upsert before aureus_reasoning_entries insert"
      pattern: "INSERT INTO aureus_trades"
    - from: "services/aureus-db-writer/main.py:process_batch"
      to: "aureus_trades"
      via: "ON CONFLICT update fills canonical fields"
      pattern: "COALESCE\\(EXCLUDED\\.symbol, aureus_trades\\.symbol\\)"
    - from: "services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
      to: "TimescaleDB dev database"
      via: "asyncpg real DB lifecycle assertions"
      pattern: "SELECT .* FROM aureus_trades"
---

<objective>
Sửa rủi ro còn lại sau Reasoning FK parent upsert: bỏ hardcoded `entry_type='MARKET'` trong `journal.py` bằng cách dùng dữ liệu order thật có sẵn, đồng thời giữ vai trò canonical persistence của db-writer và cho phép db-writer enrich placeholder row đầy đủ khi canonical order event đến sau.

Purpose: bảo toàn FK-safe Reasoning Bank mà không làm sai dữ liệu trade canonical, đặc biệt LIMIT/STOP.
Output: sửa nhỏ trong `journal.py` + `aureus-db-writer/main.py`, unit regressions, real DB E2E proof.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_journal.py
@D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
@D:/Aureus/services/aureus-db-writer/main.py
@D:/Aureus/services/aureus-db-writer/tests/test_order_buffer.py

Architecture choice locked for this quick plan:
- Safest least-impact option: keep db-writer canonical trade persistence. Do not remove db-writer role.
- `journal.py` parent insert exists only to satisfy FK before reasoning insert. Make it an idempotent parent upsert populated from available ORDER_OPENED/ORDER_FILLED fields, not canonical replacement.
- `db-writer` remains canonical and must enrich any placeholder/partial row on later order event by updating all canonical nullable fields with `COALESCE(EXCLUDED.field, aureus_trades.field)` and status/payload merge behavior.
- Reason: removing db-writer persistence has broader stream/reconciliation blast radius; surgical compatibility touches only parent upsert and conflict update semantics.

Known current risks from read files:
- `journal.py:on_order_opened` inserts parent with `entry_type` hardcoded to `'MARKET'` and only `trace_id, symbol, direction, entry_price, status, ticket`.
- `services/aureus-db-writer/main.py:process_batch` conflict update currently updates ticket/status/exit/profit/closed_at/payload only, so placeholder rows keep stale/missing symbol, direction, entry_type, entry_price, sl, tp, volume, magic_number, strategy fields.
- `verify_reasoning_bank_reuse_e2e.py` already proves no-parent reasoning_text, but does not yet prove parent enrichment from placeholder to canonical row.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regressions for real entry_type parent and db-writer enrichment</name>
  <files>services/aureus-trader/tests/test_journal.py, services/aureus-db-writer/tests/test_order_buffer.py</files>
  <behavior>
    - In `test_journal.py`, add/adjust test around `on_order_opened` parent `INSERT INTO aureus_trades` asserting event `entry_type='LIMIT'` persists as LIMIT, not MARKET. Also assert available `sl`, `tp`, `volume`, `strategy_name`, and JSON payload are passed if implementation adds them.
    - In `test_order_buffer.py`, add regression where existing DB status is `OPEN` or `SENT` and incoming canonical order payload has `symbol`, `magic_number`, `strategy_id`, `strategy_name`, `direction`, `entry_type='LIMIT'`, `entry_price`, `sl`, `tp`, `volume`; assert generated `ON CONFLICT` query updates all canonical fields, not just ticket/status/exit/profit.
  </behavior>
  <action>
    Before editing any symbol, run GitNexus impact for `TradeJournalManager.on_order_opened` and `DBWriter.process_batch` if MCP available; report direct callers/processes/risk in summary. If GitNexus unavailable, document limitation and continue with direct file-scoped tests.

    Write failing tests first. Keep tests surgical and close to existing `TestReasoningBank.test_on_order_opened_ensures_parent_trade_before_reasoning_insert` and `TestOrderBufferConflictUpdate`. Do not add broad fixtures or new dependencies. Avoid changing unrelated expected behavior.
  </action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py::TestReasoningBank -q"</automated>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-db-writer/tests/test_order_buffer.py::TestOrderBufferConflictUpdate -q"</automated>
  </verify>
  <done>Tests fail on current code for hardcoded MARKET and incomplete db-writer conflict enrichment, without unrelated failures caused by new tests.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Enrich journal parent upsert and db-writer conflict update</name>
  <files>services/aureus-trader/journal.py, services/aureus-db-writer/main.py</files>
  <behavior>
    - `journal.py:on_order_opened` parent upsert must derive `entry_type` from event fields (`entry_type`, `order_type`, `type`) and allow only `MARKET`, `LIMIT`, `STOP`; default to `MARKET` only when event lacks a valid entry type, because existing ORDER_OPENED market events may not include it.
    - Parent upsert must include available canonical fields: `ticket`, `symbol`, `direction`, `entry_type`, `entry_price`, `sl`, `tp`, `volume`, `strategy_name`, and payload JSON containing source `journal_parent_upsert` plus event data safe for JSON serialization.
    - Parent upsert must be idempotent and must not overwrite canonical non-null fields with null/placeholder values. Use `ON CONFLICT (trace_id) DO UPDATE SET` with `COALESCE(EXCLUDED.field, aureus_trades.field)` for nullable fields; do not downgrade canonical `entry_type` to default MARKET if existing row already has LIMIT/STOP.
    - `db-writer:process_batch` conflict update must fill canonical fields from canonical order events: `ticket`, `symbol`, `magic_number`, `strategy_id`, `strategy_name`, `direction`, `entry_type`, `status`, `entry_price`, `exit_price`, `sl`, `tp`, `volume`, `commission`, `swap`, `profit`, `filled_at`, `closed_at`, `payload`. Preserve existing non-null values when incoming value is null. Keep `payload = aureus_trades.payload || EXCLUDED.payload`.
  </behavior>
  <action>
    Implement smallest compatible change. Do not remove db-writer persistence. Do not relax strict timestamp validation. Do not change state machine rules except if test proves existing placeholder status blocks safe canonical enrichment; if so, make narrow transition allowance only for placeholder statuses created by journal parent upsert and document in summary.

    In `journal.py`, prefer local helpers inside `on_order_opened` only if needed; avoid new module-wide abstraction unless tests require reuse. Use existing imports; add only if necessary.

    In `main.py`, update only order-buffer `ON CONFLICT` SQL and related unit assertions. Keep ACK behavior unchanged.
  </action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py::TestReasoningBank -q"</automated>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-db-writer/tests/test_order_buffer.py -q"</automated>
  </verify>
  <done>`journal.py` no longer hardcodes MARKET for all parent rows; db-writer conflict update can enrich placeholder/partial rows fully; unit tests prove both.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extend real DB E2E and run full verification gates</name>
  <files>services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py</files>
  <behavior>
    - Real DB E2E must create no-parent reasoning lifecycle and assert `reasoning_text` persisted as before.
    - Real DB E2E must prove placeholder/enrichment behavior where practical: insert or create a partial parent row, then run canonical enrichment path through SQL/db-writer-compatible event or direct DB writer unit path if runtime service not used; assert final `aureus_trades.entry_type='LIMIT'` (or chosen non-MARKET), `symbol`, `direction`, `entry_price`, `sl`, `tp`, `volume`, `ticket`, and payload are populated.
    - Real DB E2E must clean up created trace IDs.
  </behavior>
  <action>
    Extend existing `verify_reasoning_bank_reuse_e2e.py` rather than creating a new script. Keep cleanup for every trace_id. If invoking live db-writer service is impractical in E2E, use direct asyncpg SQL shaped exactly like db-writer conflict statement and document limitation in summary; still unit-test `DBWriter.process_batch` in Task 2.

    Run required WSL commands only. If service/start command fails, consult `RUN_SERVICES.md`, start required dev services, restart changed Python containers only if needed (`aureus-trader-dev`, `aureus-db-writer-dev`). Before finishing, run GitNexus `detect_changes()` if available; if unavailable, document limitation.
  </action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py services/aureus-db-writer/tests/test_order_buffer.py -q"</automated>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"</automated>
  </verify>
  <done>Unit suite passes; real DB E2E exits 0 and prints PASS with trace IDs; data created and cleaned; reasoning_text persisted; placeholder/enrichment assertions pass.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Redis order stream to db-writer | Untrusted/producer-controlled order payload crosses into canonical DB persistence. |
| MT5/trader event to journal.py | Runtime order event crosses into FK parent upsert and reasoning insert path. |
| App code to TimescaleDB | SQL writes affect canonical `aureus_trades` and Reasoning FK integrity. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-TIW-01 | Tampering | `DBWriter.process_batch` order payload | mitigate | Keep parameterized SQL; validate `direction` and `entry_type`; preserve strict `open_time` rejection. |
| T-260503-TIW-02 | Tampering | `journal.py` parent upsert | mitigate | Normalize `entry_type` to `MARKET/LIMIT/STOP`; use `COALESCE` conflict updates to avoid overwriting canonical non-null values with placeholder/null. |
| T-260503-TIW-03 | Repudiation | Placeholder to canonical enrichment | mitigate | Preserve merged JSON payload with source markers and canonical event data; tests assert payload merge remains. |
| T-260503-TIW-04 | Denial of Service | Reasoning insert path | accept | Existing code catches reasoning insert/enqueue failures non-blocking; plan keeps behavior unchanged. |
| T-260503-TIW-05 | Information Disclosure | Payload JSON | accept | Existing order payload already persisted by db-writer; plan does not add secrets or new external output. |
</threat_model>

<verification>
Run in order:
1. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-trader/tests/test_journal.py services/aureus-db-writer/tests/test_order_buffer.py -q"`
2. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"`
3. GitNexus detect changes if available before any commit: `gitnexus_detect_changes({scope: "all"})`; document unavailable tool limitation if MCP absent.
</verification>

<success_criteria>
- Hardcoded universal `entry_type='MARKET'` in `journal.py` parent insert is gone or limited to explicit fallback only when event lacks valid entry type.
- db-writer `ON CONFLICT` fills all canonical trade fields from later canonical order event while preserving existing non-null values when incoming fields are null.
- No db-writer canonical persistence role removed.
- Unit tests and real DB E2E pass via WSL `.venv` commands.
- Summary records architecture decision, GitNexus impact/detect_changes status, E2E evidence, and any limitation.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-tiw-fix-remaining-reasoning-parent-trade-pla/260503-tiw-SUMMARY.md`
</output>
