---
phase: 260503-sai
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
  - QUICK-260503-SAI
must_haves:
  truths:
    - "Reasoning Bank không còn log lỗi FK trace_id BTCUSD:1391:1777825080 khi parent trade chưa tồn tại hoặc chưa khớp khóa ngoại."
    - "ORDER_OPENED/ORDER_FILLED tạo được aureus_reasoning_entries sau khi aureus_trade_journal và aureus_trade_signal_snapshots tồn tại."
    - "aureus_reasoning_entries.reasoning_text được insert vào DB, không rỗng, có strategy_name, symbol, direction, context/signals/snapshot facts."
    - "DB E2E tạo data thật và xác nhận reasoning_text đã persist trong aureus_reasoning_entries."
  artifacts:
    - path: "services/aureus-trader/journal.py"
      provides: "Lifecycle insert Reasoning Bank FK-safe và reasoning_text persistence"
      contains: "INSERT INTO aureus_reasoning_entries"
    - path: "services/aureus-trader/tests/test_journal.py"
      provides: "Regression unit tests cho FK-safe Reasoning Bank insert và reasoning_text"
      contains: "reasoning_text"
    - path: "services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py"
      provides: "DB E2E xác nhận data thật được tạo và reasoning_text được insert"
      contains: "reasoning_text"
  key_links:
    - from: "TradeJournalManager.on_strategy_match"
      to: "aureus_trade_journal"
      via: "INSERT TRIGGERED only; no early aureus_reasoning_entries insert before parent trade exists"
      pattern: "INSERT INTO aureus_trade_journal"
    - from: "TradeJournalManager.on_order_opened"
      to: "aureus_trade_signal_snapshots"
      via: "snapshot insert within transaction before reasoning entry insert"
      pattern: "INSERT INTO aureus_trade_signal_snapshots"
    - from: "TradeJournalManager.on_order_opened"
      to: "aureus_reasoning_entries.reasoning_text"
      via: "build reasoning_text after journal_row and snapshot_columns exist"
      pattern: "reasoning_text = _build_reasoning_text"
---

# Objective

Phân tích nguyên nhân lỗi `Reasoning entry FK trace_id BTCUSD:1391:1777825080` và fix bug `reasoning_text` chưa insert DB.

Purpose: Reasoning Bank phải chỉ insert khi FK hợp lệ, không chặn luồng MT5, và có text tái sử dụng thật trong DB.

Output: sửa nhỏ trong journal lifecycle, regression unit tests, DB E2E xác nhận data thật.

# Execution Context

- `D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md`
- `D:/Aureus/.claude/get-shit-done/templates/summary.md`

# Context

- `D:/Aureus/.planning/STATE.md`
- `D:/Aureus/CLAUDE.md`
- `D:/Aureus/services/aureus-trader/journal.py`
- `D:/Aureus/services/aureus-trader/tests/test_journal.py`
- `D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py`

Key current facts:

- `on_strategy_match()` currently inserts only `aureus_trade_journal`, then logs reasoning deferred. Keep this FK-safe behavior unless root cause proves otherwise.
- `on_order_opened()` updates journal, inserts `aureus_trade_signal_snapshots`, then conditionally inserts `aureus_reasoning_entries` only if `aureus_trades` parent exists for same `trace_id`.
- Current E2E already expects `reasoning_text` non-empty and no-parent case creates zero reasoning rows.
- DB-related change must run real DB E2E and prove row/data created.
- CLAUDE.md constraints for executor: run GitNexus impact before editing symbols. If GitNexus CLI/MCP unavailable or symbol missing, document limitation and fallback before edits. Run `gitnexus_detect_changes()` before commit.

# Tasks

## Task 1: Reproduce and isolate Reasoning FK/text lifecycle

Type: auto, TDD: true

Files:

- `services/aureus-trader/tests/test_journal.py`
- `services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py`

Behavior:

- Unit regression: no Reasoning entry insert occurs before parent `aureus_trades` row exists.
- Unit regression: when parent exists and snapshot exists, insert args include non-empty `reasoning_text` at correct column position.
- E2E regression: a trace without parent trade creates zero `aureus_reasoning_entries`; a trace with parent trade creates exactly one row with `reasoning_text` populated.

Action:

1. Before editing test functions or E2E script functions, run GitNexus impact on target symbols if indexed: `TradeJournalManager.on_strategy_match`, `TradeJournalManager.on_order_opened`, and E2E `run_e2e`. Report direct callers, affected processes, risk. If GitNexus unavailable/symbol missing, write note in summary and continue with file-local analysis.
2. Add or tighten focused regression tests in `test_journal.py` around current failure mode: FK-safe deferral and `reasoning_text` insert. Do not add broad refactors or unrelated coverage.
3. Tighten `verify_reasoning_bank_reuse_e2e.py` to assert real DB data exists for created trace: one journal row, one snapshot row, one reasoning row, `trade_journal_id` not null, `signal_snapshot_id` not null, `reasoning_text` not null/empty and contains strategy, symbol, direction, and snapshot fact like `cisd_m15=1`.
4. If E2E already covers some assertions, keep existing shape and add only missing assertions. No schema change unless Task 2 proves FK/table design impossible.

Verify:

Automated:

```bash
cd D:/Aureus && pytest services/aureus-trader/tests/test_journal.py -k "ReasoningBank or reasoning" -q
```

Done:

- Tests fail before production fix if current bug is reproducible, or executor documents why current tests already expose expected behavior.
- Unit tests explicitly assert no early Reasoning insert and non-empty `reasoning_text` on valid insert.
- E2E script contains DB assertions proving created data and `reasoning_text` persistence.

## Task 2: Fix FK-safe Reasoning entry insert and reasoning_text persistence

Type: auto, TDD: true

Files:

- `services/aureus-trader/journal.py`
- `services/aureus-trader/tests/test_journal.py`

Behavior:

- For trace `BTCUSD:1391:1777825080` style values, code never attempts invalid child insert unless referenced parent row exists under DB constraints.
- `on_strategy_match()` remains non-blocking and does not insert `aureus_reasoning_entries` before parent trade exists.
- `on_order_opened()` creates/uses journal row and snapshot row, then inserts `aureus_reasoning_entries` with populated `reasoning_text` when parent exists.
- Reasoning insert failure remains non-blocking for order lifecycle, but logs enough root-cause detail: trace_id and exception.

Action:

1. Run GitNexus impact before editing `TradeJournalManager.on_strategy_match`, `TradeJournalManager.on_order_opened`, and helper `_build_reasoning_text`. Report blast radius. If GitNexus unavailable/symbol missing, document limitation and use direct tests as fallback.
2. Inspect actual FK direction in migrations for `aureus_reasoning_entries` before changing code. If FK references `aureus_trades(trace_id)`, keep explicit parent existence check or change it to the exact referenced table/key. If FK references journal/snapshot IDs only, remove wrong parent check and rely on returned IDs. Make smallest DB-consistent change.
3. Ensure `reasoning_text` is built after `journal_row`, `snapshot_columns`, and `signal_snapshot` are available, then passed into `INSERT INTO aureus_reasoning_entries` column `reasoning_text`.
4. If duplicate insert is possible on repeated ORDER_OPENED/ORDER_FILLED, add targeted idempotency matching existing DB constraints: prefer `ON CONFLICT` only if migration has matching unique constraint; otherwise select existing row and do not duplicate. Do not introduce broad dedupe abstractions.
5. Keep exception handling non-blocking, but do not swallow root-cause evidence: log `trace_id` and exception message.

Verify:

Automated:

```bash
cd D:/Aureus && pytest services/aureus-trader/tests/test_journal.py -k "ReasoningBank or reasoning" -q
```

Done:

- Regression tests pass.
- No early invalid Reasoning child insert happens before required parent exists.
- Valid lifecycle inserts `aureus_reasoning_entries.reasoning_text` with non-empty generated text.
- Code changes are surgical and limited to journal lifecycle/test coverage unless migration inspection proves schema fix is needed.

## Task 3: Run full verification with DB E2E and change-scope check

Type: auto

Files:

- `services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py`
- `services/aureus-trader/journal.py`
- `services/aureus-trader/tests/test_journal.py`

Action:

1. Run focused unit tests and then the DB E2E against configured DB. Use `AUREUS_DB_DSN` if needed. If command fails due service startup/DSN, consult `D:/Aureus/RUN_SERVICES.md` before retrying.
2. DB E2E must create fresh unique trace IDs, insert required parent trade row for valid trace, verify created journal/snapshot/reasoning rows, verify `reasoning_text` inserted, then clean up test rows.
3. Run broader journal tests if focused tests pass.
4. Run `gitnexus_detect_changes()` before any commit to verify expected symbols/flows only changed. If GitNexus unavailable, document fallback: `git diff -- services/aureus-trader/journal.py services/aureus-trader/tests/test_journal.py services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py`.

Verify:

Automated:

```bash
cd D:/Aureus && pytest services/aureus-trader/tests/test_journal.py -q && python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
```

Done:

- Unit suite passes.
- DB E2E prints PASS and verifies `aureus_reasoning_entries.reasoning_text` persisted for created trace.
- No FK error remains for Reasoning entry lifecycle.
- `gitnexus_detect_changes()` or documented fallback confirms only expected files/symbols changed.

# Threat Model

## Trust Boundaries

| Boundary | Description |
|---|---|
| Redis/MT5 event to trader DB writer | Event payload fields are untrusted runtime input before DB persistence. |
| Trader service to PostgreSQL | SQL writes must preserve FK integrity and avoid corrupt duplicate reasoning rows. |
| Reasoning text to embeddings worker | Persisted text becomes embedding input; should not include raw prompt/context secrets unless intentionally selected. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|---|---|---|---|
| T-260503-sai-01 | Tampering | `TradeJournalManager.on_order_opened` | mitigate | Use existing parameterized asyncpg queries; no string formatting SQL. |
| T-260503-sai-02 | Denial of Service | Reasoning insert path | mitigate | Keep reasoning insert exceptions non-blocking so order lifecycle continues. |
| T-260503-sai-03 | Information Disclosure | `reasoning_text` | mitigate | Build from journal/snapshot facts only; tests must confirm raw `prompt_text`/`context_text` are not required for `reasoning_text`. |
| T-260503-sai-04 | Repudiation | FK failure logs | mitigate | Log `trace_id` and exception message when reasoning insert fails. |
| T-260503-sai-05 | Tampering | FK parent linkage | mitigate | Check actual FK target table/key before code change; DB E2E must prove valid parent linkage. |

# Verification

Overall commands:

```bash
cd D:/Aureus && pytest services/aureus-trader/tests/test_journal.py -k "ReasoningBank or reasoning" -q
cd D:/Aureus && pytest services/aureus-trader/tests/test_journal.py -q
cd D:/Aureus && python services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py
```

If DB command fails because services are down, read `D:/Aureus/RUN_SERVICES.md`, start required DB service per project instructions, then rerun E2E.

# Success Criteria

- Root cause documented in summary: exact FK target and why `BTCUSD:1391:1777825080` failed.
- Fix is minimal and DB-consistent.
- `reasoning_text` persists in `aureus_reasoning_entries` for a real DB-created trace.
- No parentless Reasoning row gets inserted.
- Unit tests and DB E2E pass.
- GitNexus impact and detect_changes requirements are satisfied or limitation documented.

# Output

After completion, create:

`D:/Aureus/.planning/quick/260503-sai-ph-n-ti-ch-chi-ti-t-nguy-n-nh-n-l-i-reas/260503-sai-SUMMARY.md`
