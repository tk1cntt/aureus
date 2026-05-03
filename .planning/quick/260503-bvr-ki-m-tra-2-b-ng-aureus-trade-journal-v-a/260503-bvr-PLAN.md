---
phase: 260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md
autonomous: true
requirements:
  - QUICK-260503-BVR
must_haves:
  truths:
    - "Người dùng có report chỉ rõ field nào trong aureus_trade_journal có thể thay thế field trùng trong aureus_reasoning_entries."
    - "Người dùng có report chỉ rõ field nào trong aureus_trade_signal_snapshots có thể join để bổ sung context Reasoning Bank."
    - "Report không đề xuất xoá toàn bộ aureus_reasoning_entries khi chưa có bằng chứng; bảng này vẫn giữ memory-specific fields như reasoning_text, prompt_text, context_text, embeddings, digest/hash."
    - "Report có join keys, migration/refactor steps, E2E DB validation strategy, risk/tradeoffs cụ thể."
  artifacts:
    - path: ".planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md"
      provides: "Concrete Reasoning Bank data optimization plan from actual schema/source inspection"
      contains: "aureus_trade_journal"
    - path: "services/aureus-db-writer/migrations/add_trade_journal.sql"
      provides: "Source of truth for aureus_trade_journal fields"
      contains: "CREATE TABLE IF NOT EXISTS aureus_trade_journal"
    - path: "services/aureus-db-writer/migrations/add_trade_evaluations.sql"
      provides: "Original wide aureus_trade_signal_snapshots schema fields"
      contains: "CREATE TABLE IF NOT EXISTS aureus_trade_signal_snapshots"
    - path: "services/aureus-db-writer/migrations/add_reasoning_entries.sql"
      provides: "Reasoning Bank base table fields"
      contains: "CREATE TABLE IF NOT EXISTS aureus_reasoning_entries"
    - path: "services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql"
      provides: "Reasoning Bank embedding/text fields"
      contains: "reasoning_embedding"
  key_links:
    - from: "aureus_reasoning_entries.trade_journal_id"
      to: "aureus_trade_journal.id"
      via: "direct FK-like join for strategy/lifecycle/outcome reuse"
      pattern: "trade_journal_id.*aureus_trade_journal"
    - from: "aureus_reasoning_entries.signal_snapshot_id"
      to: "aureus_trade_signal_snapshots.id"
      via: "snapshot join for indicator context reuse"
      pattern: "signal_snapshot_id.*aureus_trade_signal_snapshots"
    - from: "services/aureus-trader/journal.py"
      to: "aureus_reasoning_entries"
      via: "on_strategy_match/on_order_opened/on_order_closed duplicate field writes"
      pattern: "UPDATE aureus_reasoning_entries|INSERT INTO aureus_reasoning_entries"
---

<objective>
Lập kế hoạch tối ưu Reasoning Bank để tận dụng dữ liệu đã lưu trong `aureus_trade_journal` và `aureus_trade_signal_snapshots`, thay vì tiếp tục nhân bản dữ liệu lifecycle/signal/outcome vào `aureus_reasoning_entries`.

Purpose: giảm duplicate storage/write-path, tránh drift giữa journal/snapshot/reasoning, vẫn giữ dữ liệu memory-specific cần cho Reasoning Bank.
Output: report/plan `.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql
@D:/Aureus/services/aureus-db-writer/migrations/add_trade_evaluations.sql
@D:/Aureus/services/aureus-db-writer/migrations/optimize_trade_signal_snapshots_storage.sql
@D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries.sql
@D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/reasoning_embeddings.py
@D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_db_e2e.py
@D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_embeddings_e2e.py

<interfaces>
Schema facts from inspection:
- `aureus_trade_journal`: `id`, `trace_id`, `status`, `strategy_name`, `strategy_id`, `direction`, `symbol`, `score`, `active_signals`, `context_filters`, `ticket`, `pending_order_id`, `entry_time`, `exit_time`, `pnl`, `pnl_pips`, `result`, lifecycle timestamps.
- `aureus_trade_signal_snapshots`: joins to `aureus_trade_journal(id)` via `trade_journal_id`; stores `trace_id`, `ticket`, `strategy_name`, `symbol`, `timeframe`, `signal_schema_version`, and indicator columns: `atr`, `ema_21`, `ema_34`, `ema_55`, `ema_89`, `ema_100`, `ema_200`, `vol_sma_20`, `session`, candle colors, Bollinger bands, CISD states.
- `aureus_reasoning_entries`: currently duplicates journal lifecycle/outcome fields (`strategy_id`, `strategy_name`, `symbol`, `direction`, `active_signals`, `context_filters`, `ticket`, `pending_order_id`, `entry_time`, `exit_time`, `success`, `reward`, `pnl`, `pnl_pips`, `result`) and adds memory-specific fields (`reasoning_source`, `prompt_digest`, `decision_digest`, `input_context_hash`, `reasoning_text`, `decision_action`, `confidence`, `prompt_text`, `context_text`, `reasoning_embedding`, `prompt_embedding`, `context_embedding`, `embedding_model`, `embedded_at`).
- `journal.py` writes `aureus_reasoning_entries` at strategy match, updates join ids/ticket at order open, updates outcome fields at order close.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Inspect Reasoning Bank storage overlap and write optimization report</name>
  <files>.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md</files>
  <action>Create Vietnamese markdown report from actual inspected files only. Include sections: current schema/source evidence, field reuse matrix, recommended minimal `aureus_reasoning_entries` role, join keys, proposed query/view shape, migration/refactor steps, E2E DB validation strategy, risks/tradeoffs. Must state `aureus_reasoning_entries` should NOT be removed entirely because `reasoning_text`, `prompt_text`, `context_text`, digests/hashes, embeddings, embedding metadata, and reasoning-source semantics are not present in journal/snapshots. Recommend moving reads for strategy/lifecycle/outcome/signal context to joins against `aureus_trade_journal` and `aureus_trade_signal_snapshots`, not duplicating those columns long-term.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
p = Path('D:/Aureus/.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md')
text = p.read_text(encoding='utf-8')
required = ['aureus_trade_journal', 'aureus_trade_signal_snapshots', 'aureus_reasoning_entries', 'trade_journal_id', 'signal_snapshot_id', 'reasoning_text', 'prompt_text', 'context_text', 'reasoning_embedding', 'E2E', 'risk', 'tradeoff']
missing = [s for s in required if s not in text]
assert not missing, missing
assert 'xoá toàn bộ aureus_reasoning_entries' not in text.lower() or 'không' in text.lower()
print('PASS report coverage')
PY</automated>
  </verify>
  <done>Report maps reusable fields from journal/snapshots, lists fields that must remain in reasoning_entries, and gives concrete optimization/refactor plan without claiming full table removal.</done>
</task>

<task type="auto">
  <name>Task 2: Add concrete migration/refactor and DB E2E validation checklist</name>
  <files>.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md</files>
  <action>In same report, add executable follow-up plan. Migration/refactor steps must include: add or formalize FK/index for `signal_snapshot_id` if absent, create read model/view or query helper joining `reasoning_entries -> trade_journal -> trade_signal_snapshots`, refactor `fetch_strategy_reasoning_insights` and semantic search callers to use joined lifecycle/outcome fields, stop updating duplicated lifecycle/outcome fields after parity validation, then optionally deprecate duplicate columns only after backfill/audit. DB runtime E2E requirement must be explicit because future changes touch database: create trade row, journal row, snapshot row, reasoning row with only memory fields + join ids, close order, verify joined insight returns strategy stats/recent lessons/similar lessons and embeddings remain searchable.</action>
  <verify>
    <automated>python - <<'PY'
from pathlib import Path
text = Path('D:/Aureus/.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md').read_text(encoding='utf-8')
required = ['FK', 'index', 'view', 'fetch_strategy_reasoning_insights', 'semantic search', 'stop updating', 'deprecate', 'backfill', 'runtime E2E', 'joined insight']
missing = [s for s in required if s not in text]
assert not missing, missing
print('PASS implementation checklist')
PY</automated>
  </verify>
  <done>Report contains follow-up implementation sequence and DB E2E checklist suitable for next quick implementation task.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB persisted trade data -> Reasoning Bank report | Report consumes persisted fields that may contain strategy text/context; avoid suggesting raw prompt exposure beyond existing intended embedding use. |
| Future query/view -> Telegram insight | Joined Reasoning Bank data may flow to Telegram; report must preserve trimming/redaction behavior and avoid leaking raw prompt/context. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-bvr-01 | I | `prompt_text`, `context_text`, `reasoning_text` | mitigate | Report must keep these in `aureus_reasoning_entries` as controlled memory fields and state Telegram/read models should not expose raw prompt/context by default. |
| T-260503-bvr-02 | T | joined lifecycle/outcome stats | mitigate | Report must require DB E2E parity checks comparing joined stats with existing `aureus_reasoning_entries` duplicate stats before stopping duplicate updates. |
| T-260503-bvr-03 | R | future duplicate-column deprecation | mitigate | Report must require staged migration: add joins/read model first, validate parity, backfill/audit, then only deprecate duplicate columns in later task. |
</threat_model>

<verification>
Run both task automated checks. Confirm report cites actual source files and does not implement DB/code changes.
</verification>

<success_criteria>
- One report file exists at `.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-REASONING-BANK-DATA-OPTIMIZATION.md`.
- Report includes field reuse matrix for `aureus_trade_journal`, `aureus_trade_signal_snapshots`, and `aureus_reasoning_entries`.
- Report clearly says what stays in `aureus_reasoning_entries`: memory/source fields, digests/hashes, embeddings, embedding metadata, join ids.
- Report proposes join keys and read-model/query strategy.
- Report includes migration/refactor steps and DB runtime E2E validation strategy for future implementation.
</success_criteria>

<output>
After completion, create `.planning/quick/260503-bvr-ki-m-tra-2-b-ng-aureus-trade-journal-v-a/260503-bvr-SUMMARY.md`.
</output>
