---
phase: 260425-duy-xoa-trade-evaluations
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-db-writer/migrations/add_trade_evaluations.sql
  - services/aureus-db-writer/tests/test_evaluation_migration.py
  - services/aureus-trader/journal.py
  - services/aureus-trader/recompute_evaluations.py
  - services/aureus-trader/tests/test_evaluation_pipeline.py
  - services/aureus-trader/tests/test_evaluation_recompute.py
  - services/aureus-trader/tests/test_signal_snapshot_pipeline.py
  - services/aureus-trader/tests/test_signal_snapshot_recompute.py
  - services/aureus-trader/scripts/verify_phase55_runtime_evidence.py
  - docs/system-design-strategy-trigger-data-flow.md
  - .planning/REQUIREMENTS.md
  - RUN_SERVICES.md
  - scripts/dev-service.sh
autonomous: true
requirements:
  - QUICK-260425-DUY
must_haves:
  truths:
    - "Runtime DB không còn yêu cầu hoặc tạo bảng aureus_trade_evaluations."
    - "ORDER_OPENED vẫn persist aureus_trade_journal và aureus_trade_signal_snapshots, nhưng không insert evaluation rows."
    - "Source, tests, và active runtime docs không còn mô tả aureus_trade_evaluations là bảng hiện hành."
  artifacts:
    - path: "services/aureus-db-writer/migrations/add_trade_evaluations.sql"
      provides: "Migration schema còn lại chỉ cho bảng runtime cần giữ, không tạo aureus_trade_evaluations"
      contains_not: "aureus_trade_evaluations"
    - path: "services/aureus-trader/journal.py"
      provides: "ORDER_OPENED persistence không gọi INSERT INTO aureus_trade_evaluations"
      contains_not: "INSERT INTO aureus_trade_evaluations"
    - path: "services/aureus-trader/recompute_evaluations.py"
      provides: "Không còn recompute script ghi vào bảng đã xóa hoặc file được xóa nếu chỉ phục vụ evaluations"
      contains_not: "aureus_trade_evaluations"
  key_links:
    - from: "services/aureus-trader/journal.py"
      to: "aureus_trade_signal_snapshots"
      via: "ORDER_OPENED lifecycle"
      pattern: "INSERT INTO aureus_trade_signal_snapshots"
    - from: "services/aureus-db-writer/migrations/add_trade_evaluations.sql"
      to: "runtime TimescaleDB"
      via: "migration/script execution"
      pattern: "aureus_trade_signal_snapshots"
---

<objective>
Xóa bảng `aureus_trade_evaluations` khỏi runtime schema và loại bỏ toàn bộ source code, tests, active docs đang phụ thuộc trực tiếp vào bảng này.

Purpose: User đã quyết định bỏ bảng evaluations; codebase không được tiếp tục tạo, insert, recompute, verify, hoặc document bảng này như một phần runtime flow.
Output: Migration/schema/test/docs đã được chỉnh surgical; ORDER_OPENED vẫn lưu journal/signal snapshot; DB/E2E verification chứng minh runtime không còn bảng evaluations và vẫn tạo data cần giữ.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/services/aureus-db-writer/migrations/add_trade_evaluations.sql
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/recompute_evaluations.py
@D:/Aureus/docs/system-design-strategy-trigger-data-flow.md

<constraints>
- Mọi trao đổi và summary dùng tiếng Việt.
- Đây là thay đổi liên quan database: bắt buộc chạy DB/E2E verification với database. Nếu command lỗi hoặc infra chưa chạy, tham khảo `D:/Aureus/RUN_SERVICES.md`, thử khởi động đúng service, rồi document blocker chính xác nếu vẫn không chạy được.
- Trước khi sửa function/class/method nào, phải chạy GitNexus impact cho symbol đó, tối thiểu: `journal.py:on_order_opened` và mọi helper/recompute function bị sửa/xóa. Báo blast radius trong summary.
- Trước commit phải chạy `npx gitnexus detect_changes` nếu CLI hỗ trợ. Nếu command không tồn tại, document fallback đã dùng (ví dụ MCP `gitnexus_detect_changes()` hoặc `git diff --stat`).
- Chỉ xóa phần liên quan trực tiếp `aureus_trade_evaluations`. Không refactor scoring/strategy logic khác, không xóa historical `.planning/quick/*` artifacts cũ.
</constraints>

<discovery_notes>
Initial grep found active references in:
- `D:/Aureus/services/aureus-db-writer/migrations/add_trade_evaluations.sql`
- `D:/Aureus/services/aureus-db-writer/tests/test_evaluation_migration.py`
- `D:/Aureus/services/aureus-trader/journal.py`
- `D:/Aureus/services/aureus-trader/recompute_evaluations.py`
- `D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py`
- `D:/Aureus/services/aureus-trader/tests/test_evaluation_recompute.py`
- `D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
- `D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_recompute.py`
- `D:/Aureus/services/aureus-trader/scripts/verify_phase55_runtime_evidence.py`
- `D:/Aureus/docs/system-design-strategy-trigger-data-flow.md`
- `D:/Aureus/.planning/REQUIREMENTS.md`, `D:/Aureus/RUN_SERVICES.md`, `D:/Aureus/scripts/dev-service.sh`
Historical phase/quick artifacts may mention the old table; leave them unless they are current runtime docs or verification docs actively used by commands.
</discovery_notes>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Remove runtime schema and writer code for aureus_trade_evaluations</name>
  <files>D:/Aureus/services/aureus-db-writer/migrations/add_trade_evaluations.sql, D:/Aureus/services/aureus-trader/journal.py, D:/Aureus/services/aureus-trader/recompute_evaluations.py, D:/Aureus/services/aureus-db-writer/tests/test_evaluation_migration.py</files>
  <behavior>
    - Migration no longer creates table/indexes/constraints for `aureus_trade_evaluations`.
    - `on_order_opened` no longer validates evaluation-only core fields or inserts into `aureus_trade_evaluations`; it must still update `aureus_trade_journal` and insert `aureus_trade_signal_snapshots` when applicable.
    - `recompute_evaluations.py` is removed if it only exists to backfill `aureus_trade_evaluations`; otherwise strip table writes/reads surgically and rename only if GitNexus rename workflow is used.
    - Migration tests should assert absence of `aureus_trade_evaluations` and continued validity of `aureus_trade_signal_snapshots` schema, not preserve old evaluation-table expectations.
  </behavior>
  <action>First run GitNexus discovery/impact for affected symbols before editing: use `gitnexus_query` for `aureus_trade_evaluations journal evaluation recompute`, then `gitnexus_impact({target: "on_order_opened", direction: "upstream"})` and impact for any recompute/helper symbol modified or deleted. Then remove only the schema/code paths that create/read/write `aureus_trade_evaluations`. Keep journal lifecycle and signal snapshot persistence intact. If deleting `recompute_evaluations.py`, also remove only references that invoke that file; do not delete unrelated scoring modules.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-db-writer/tests/test_evaluation_migration.py services/aureus-trader/tests/test_signal_snapshot_pipeline.py services/aureus-trader/tests/test_signal_snapshot_recompute.py -x</automated>
    <automated>cd D:/Aureus && python -m pytest services/aureus-trader/tests/test_evaluation_pipeline.py services/aureus-trader/tests/test_evaluation_recompute.py -x</automated>
    <automated>cd D:/Aureus && python - <<'PY'
from pathlib import Path
active = [
  'services/aureus-db-writer/migrations/add_trade_evaluations.sql',
  'services/aureus-trader/journal.py',
  'services/aureus-trader/recompute_evaluations.py',
]
for rel in active:
    p = Path(rel)
    if p.exists() and 'aureus_trade_evaluations' in p.read_text(encoding='utf-8'):
        raise SystemExit(f'still references aureus_trade_evaluations: {rel}')
print('runtime source/schema clean')
PY</automated>
  </verify>
  <done>No runtime schema/source path creates, queries, updates, or inserts `aureus_trade_evaluations`; retained ORDER_OPENED behavior for journal and signal snapshots is covered by passing tests.</done>
</task>

<task type="auto">
  <name>Task 2: Clean active tests, scripts, and docs that require the removed table</name>
  <files>D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py, D:/Aureus/services/aureus-trader/tests/test_evaluation_recompute.py, D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py, D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_recompute.py, D:/Aureus/services/aureus-trader/scripts/verify_phase55_runtime_evidence.py, D:/Aureus/docs/system-design-strategy-trigger-data-flow.md, D:/Aureus/.planning/REQUIREMENTS.md, D:/Aureus/RUN_SERVICES.md, D:/Aureus/scripts/dev-service.sh</files>
  <action>Remove or rewrite active assertions/scripts/docs that treat `aureus_trade_evaluations` as required runtime state. Delete evaluation-only tests if their only purpose is asserting inserts into the removed table; update mixed signal snapshot tests to assert no evaluation insert is attempted while snapshot inserts still happen. Update `verify_phase55_runtime_evidence.py`, `RUN_SERVICES.md`, and `scripts/dev-service.sh` so runtime checks no longer SELECT from the removed table. Update active system design docs to describe `TradeJournalManager` as persisting `aureus_trade_journal` + `aureus_trade_signal_snapshots` only. Do not edit old `.planning/quick/*` or phase historical summaries unless they are current task artifacts.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-trader/tests -x</automated>
    <automated>cd D:/Aureus && python - <<'PY'
from pathlib import Path
allowed_parts = {'.planning/quick', '.planning/phases', '.planning/milestones', '.planning/archive'}
violations = []
for p in Path('.').rglob('*'):
    if not p.is_file() or '.git' in p.parts:
        continue
    rel = p.as_posix()
    if any(rel.startswith(part) for part in allowed_parts):
        continue
    try:
        text = p.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        continue
    if 'aureus_trade_evaluations' in text:
        violations.append(rel)
if violations:
    raise SystemExit('active references remain:\n' + '\n'.join(violations))
print('active references clean')
PY</automated>
  </verify>
  <done>Active tests/scripts/docs no longer require `aureus_trade_evaluations`; repository-wide active-reference scan only permits historical planning artifacts.</done>
</task>

<task type="auto">
  <name>Task 3: Run database/E2E verification and final GitNexus scope check</name>
  <files>D:/Aureus/RUN_SERVICES.md, D:/Aureus/.planning/quick/260425-duy-xo-a-ba-ng-aureus-trade-evaluations-va-s/260425-duy-SUMMARY.md</files>
  <action>Run the strongest database-backed verification available. Use `RUN_SERVICES.md` if services are down. Verify in TimescaleDB that `aureus_trade_evaluations` is absent after applying the updated migration/drop path, and verify an ORDER_OPENED/journal path still creates or can create required retained data (`aureus_trade_journal` update and/or `aureus_trade_signal_snapshots` insert). If a destructive DROP is needed for dev DB, limit it to `DROP TABLE IF EXISTS aureus_trade_evaluations` and document it; do not drop unrelated tables. Before commit, run `npx gitnexus detect_changes`; if unsupported, document exact failure and fallback. Create the summary with commands run, DB evidence, GitNexus blast radius, and remaining references if only historical artifacts remain.</action>
  <verify>
    <automated>cd D:/Aureus && python -m pytest services/aureus-trader/tests services/aureus-db-writer/tests -x</automated>
    <automated>cd D:/Aureus && wsl -d Aureus -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename = 'aureus_trade_evaluations';\""</automated>
    <automated>cd D:/Aureus && wsl -d Aureus -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('aureus_trade_journal','aureus_trade_signal_snapshots') ORDER BY tablename;\""</automated>
    <automated>cd D:/Aureus && npx gitnexus detect_changes</automated>
  </verify>
  <done>Tests pass, DB evidence shows `aureus_trade_evaluations` absent and retained journal/snapshot tables usable, GitNexus scope check is recorded, and `260425-duy-SUMMARY.md` exists.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5/strategy payload -> trader journal DB writes | External/runtime event payload crosses into DB persistence code. |
| Migration scripts -> TimescaleDB schema | SQL files mutate runtime database schema. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-DUY-01 | T | `journal.py:on_order_opened` | mitigate | Remove only evaluation-table write path; keep tests proving retained journal/snapshot writes are unchanged. |
| T-260425-DUY-02 | D | TimescaleDB migration/drop verification | mitigate | Limit destructive DB action to `DROP TABLE IF EXISTS aureus_trade_evaluations`; verify retained tables still exist. |
| T-260425-DUY-03 | R | Docs/scripts verification | mitigate | Update active verification commands so future evidence cannot falsely require or query the removed table. |
</threat_model>

<verification>
Overall verification requires: unit tests for affected migration/journal paths; active-reference scan excluding historical planning artifacts; database-backed check proving removed table is absent; database-backed check proving retained tables remain; GitNexus detect_changes/fallback recorded before commit.
</verification>

<success_criteria>
- `aureus_trade_evaluations` is absent from active runtime schema/source/tests/docs/scripts.
- ORDER_OPENED journal + signal snapshot behavior remains tested and working.
- DB/E2E verification against TimescaleDB is run or exact infra blocker is documented after consulting `RUN_SERVICES.md`.
- GitNexus impact and detect_changes requirements from `CLAUDE.md` are satisfied or fallback is explicitly documented.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-duy-xo-a-ba-ng-aureus-trade-evaluations-va-s/260425-duy-SUMMARY.md`.
</output>
