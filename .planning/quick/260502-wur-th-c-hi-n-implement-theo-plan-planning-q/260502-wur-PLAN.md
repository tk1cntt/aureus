---
phase: 260502-wur-reasoning-bank-mvp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-db-writer/migrations/add_reasoning_entries.sql
  - services/aureus-trader/journal.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-trader/scripts/verify_reasoning_bank_db_e2e.py
autonomous: true
requirements:
  - QUICK-260502-WUR
must_haves:
  truths:
    - "Sau STRATEGY_MATCH có trace_id hợp lệ, hệ thống tạo 1 reasoning entry append-only trong DB, không chặn dispatch/order lifecycle nếu insert lỗi."
    - "Reasoning entry liên kết được với trade journal qua trace_id, strategy, symbol, direction và signal context tối thiểu."
    - "Khi ORDER_OPENED hoặc ORDER_FILLED chạy, reasoning entry được gắn ticket/pending_order_id/signal_snapshot_id nếu có, không tạo entry mới."
    - "Khi ORDER_CLOSED chạy, reasoning entry được attach outcome success/reward/pnl và evaluated_at theo trace_id."
    - "Runtime DB E2E chứng minh migration tạo table, strategy match ghi row, opened/closed update row, cleanup test data thành công."
  artifacts:
    - path: "services/aureus-db-writer/migrations/add_reasoning_entries.sql"
      provides: "DB table aureus_reasoning_entries append-only base + indexes theo trace_id/strategy/symbol/created_at"
      contains: "CREATE TABLE IF NOT EXISTS aureus_reasoning_entries"
    - path: "services/aureus-trader/journal.py"
      provides: "Minimal integration points trong TradeJournalManager cho write/link/outcome Reasoning Bank"
      exports:
        - "TradeJournalManager"
    - path: "services/aureus-trader/tests/test_journal.py"
      provides: "Unit coverage cho non-blocking reasoning insert, link opened, attach closed outcome"
    - path: "services/aureus-trader/scripts/verify_reasoning_bank_db_e2e.py"
      provides: "Runtime DB E2E verification tạo data thật và xoá data test"
  key_links:
    - from: "services/aureus-trader/journal.py::on_strategy_match"
      to: "aureus_reasoning_entries"
      via: "INSERT sau journal insert, try/except không làm on_strategy_match trả False khi reasoning insert lỗi"
      pattern: "INSERT INTO aureus_reasoning_entries"
    - from: "services/aureus-trader/journal.py::on_order_opened"
      to: "aureus_reasoning_entries"
      via: "UPDATE theo trace_id để set ticket/pending_order_id/signal_snapshot_id"
      pattern: "UPDATE aureus_reasoning_entries"
    - from: "services/aureus-trader/journal.py::on_order_closed"
      to: "aureus_reasoning_entries"
      via: "UPDATE theo trace_id để set success/reward/pnl/evaluated_at"
      pattern: "success = CASE"
---

<objective>
Tạo MVP Reasoning Bank append-only theo report FenixAI: DB-backed `aureus_reasoning_entries`, ghi decision trace sau strategy match, link lifecycle order, attach outcome khi close.

Purpose: Đóng vòng `strategy evaluation -> order lifecycle -> outcome` để dùng cho analytics/Telegram insight sau này, không inject retrieval vào live decision.
Output: Migration DB, integration tối thiểu trong `TradeJournalManager`, unit tests, DB E2E script.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/.planning/STATE.md
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/quick/260502-vw9-clone-project-n-y-v-v-ph-n-t-ch-t-m-hi-u/260502-vw9-REASONING-BANK-REPORT.md
@D:/Aureus/services/aureus-trader/journal.py
@D:/Aureus/services/aureus-trader/tests/test_journal.py
@D:/Aureus/services/aureus-trader/scripts/verify_limit_order_lifecycle_db_e2e.py
@D:/Aureus/services/aureus-db-writer/migrations/add_trade_journal.sql

<interfaces>
Key existing contracts:

`TradeJournalManager.on_strategy_match(event) -> bool`
- Creates `aureus_trade_journal` row.
- Must stay non-blocking: catches exceptions and returns False only for journal core failure.
- Existing insert fields: `trace_id, strategy_name, strategy_id, direction, symbol, score, active_signals, context_filters, origin_timestamp`.

`TradeJournalManager.on_order_opened(event) -> bool`
- Updates journal from TRIGGERED to EXECUTED.
- Inserts `aureus_trade_signal_snapshots` and has `snapshot_insert_result` plus `trade_journal_id` inside transaction.
- Use same transaction for reasoning link update after signal snapshot insert.

`TradeJournalManager.on_order_closed(event) -> bool`
- Resolves trace_id from ticket if needed.
- Computes `result` from pnl: WIN/LOSS/BE.
- Updates journal CLOSED with `pnl`, `pnl_pips`, `exit_time`, `result`.
- Use same trace_id to attach reasoning outcome after journal close.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Tạo schema append-only Reasoning Bank và unit tests đỏ</name>
  <files>services/aureus-db-writer/migrations/add_reasoning_entries.sql, services/aureus-trader/tests/test_journal.py</files>
  <behavior>
    - Test 1: `on_strategy_match` insert journal xong sẽ gọi thêm `INSERT INTO aureus_reasoning_entries` với trace_id/strategy_name/strategy_id/symbol/direction/confidence/active_signals/context_filters.
    - Test 2: Nếu insert reasoning lỗi, `on_strategy_match` vẫn trả True khi journal insert thành công; lỗi chỉ log warning/exception, không chặn hot path.
    - Test 3: `on_order_opened` update `aureus_reasoning_entries` theo trace_id để gắn ticket/pending_order_id/signal_snapshot_id khi có journal row.
    - Test 4: `on_order_closed` update `aureus_reasoning_entries` theo trace_id để set success/reward/pnl/evaluated_at.
  </behavior>
  <action>
    Trước khi sửa test quanh symbol hiện có, chạy GitNexus impact bắt buộc: `gitnexus_impact({target: "TradeJournalManager", direction: "upstream"})`, `gitnexus_impact({target: "on_strategy_match", direction: "upstream"})`, `gitnexus_impact({target: "on_order_opened", direction: "upstream"})`, `gitnexus_impact({target: "on_order_closed", direction: "upstream"})`; báo blast radius trong summary. Tạo migration `add_reasoning_entries.sql` với table `aureus_reasoning_entries`: `id BIGSERIAL PRIMARY KEY`, `trace_id TEXT NOT NULL REFERENCES aureus_trades(trace_id) ON DELETE CASCADE`, `trade_journal_id BIGINT REFERENCES aureus_trade_journal(id) ON DELETE SET NULL`, `signal_snapshot_id BIGINT`, `strategy_id BIGINT`, `strategy_name TEXT NOT NULL`, `symbol TEXT NOT NULL`, `timeframe TEXT`, `direction VARCHAR(10) NOT NULL CHECK (direction IN ('BUY','SELL'))`, `reasoning_source TEXT NOT NULL DEFAULT 'strategy_match'`, `prompt_digest TEXT`, `decision_digest TEXT`, `input_context_hash TEXT`, `reasoning_text TEXT`, `decision_action TEXT`, `confidence DOUBLE PRECISION`, `active_signals JSONB`, `context_filters JSONB`, `ticket BIGINT`, `pending_order_id BIGINT`, `entry_time TIMESTAMPTZ`, `exit_time TIMESTAMPTZ`, `success BOOLEAN`, `reward DOUBLE PRECISION`, `pnl DOUBLE PRECISION`, `pnl_pips DOUBLE PRECISION`, `result VARCHAR(10)`, `created_at TIMESTAMPTZ DEFAULT now()`, `evaluated_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ DEFAULT now()`. Thêm indexes `trace_id`, `(strategy_id, direction)`, `symbol`, `created_at DESC`, `success`, GIN cho `active_signals` và `context_filters`. Không thêm retrieval, embedding, judge, LLM fields ngoài schema tối thiểu. Viết unit tests trước, kỳ vọng đỏ trước khi production code đổi.
  </action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-trader && python -m pytest tests/test_journal.py -k "reasoning or TJ_IN_01_valid_strategy_match_creates_entry or order_filled_executes_with_position_and_deal_ticket or TJ_IN_12_invalid_exit_reason_normalized" -x</automated>
  </verify>
  <done>Migration có table/index tối thiểu; tests mô tả đúng MVP append-only/link/outcome và fail trước khi sửa `journal.py`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Tích hợp Reasoning Bank tối thiểu vào TradeJournalManager</name>
  <files>services/aureus-trader/journal.py, services/aureus-trader/tests/test_journal.py</files>
  <behavior>
    - `on_strategy_match` ghi reasoning entry sau journal insert thành công, không ghi nếu journal insert không tạo/không tồn tại.
    - Reasoning insert failure không đổi return True của strategy match khi journal insert thành công.
    - `on_order_opened` chỉ update existing reasoning entry theo trace_id, không insert mới.
    - `on_order_closed` set `success=True` khi result WIN, `False` khi LOSS, `None` khi BE/unknown; `reward` dùng `pnl_pips` nếu có, fallback `pnl`.
  </behavior>
  <action>
    Sửa `TradeJournalManager` tối thiểu. Trong `on_strategy_match`, sau journal insert/duplicate handling, gọi helper private mới ví dụ `_append_reasoning_entry(conn_or_pool...)` hoặc inline small query để insert `aureus_reasoning_entries`; nếu dùng helper method thì helper cũng cần GitNexus impact nếu sửa lại sau. `reasoning_text` lấy từ `data.get("reasoning")`, `data.get("rationale")`, hoặc `match_data.get(...)`; nếu không có thì NULL, không hardcode fake text. `decision_action` lấy direction. `confidence` dùng score. `active_signals/context_filters` reuse JSON đã normalize. Wrap reasoning insert riêng bằng try/except để không chặn hot path, log warning/exception. Trong `on_order_opened`, sau snapshot insert, update reasoning row: `trade_journal_id`, `signal_snapshot_id` nếu lấy được id; nếu insert snapshot đang dùng `execute`, đổi sang `fetchval RETURNING id` hoặc query id sau insert trong cùng transaction, nhưng giữ `ON CONFLICT (trade_journal_id) DO NOTHING` semantic. Trong `on_order_closed`, sau journal close success, update reasoning outcome theo trace_id. Không thêm retrieval/LLM judge/embedding/API endpoint. Không refactor ngoài vùng này.
  </action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-trader && python -m pytest tests/test_journal.py -k "reasoning or TestOnStrategyMatchInputValidation or TestPendingOrderLifecycle or TestOnOrderClosedInputValidation" -x</automated>
  </verify>
  <done>All targeted unit tests pass; existing journal lifecycle behavior không đổi; reasoning write/link/outcome non-blocking và trace_id-based.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Thêm DB E2E runtime verification và chạy detect changes</name>
  <files>services/aureus-trader/scripts/verify_reasoning_bank_db_e2e.py, services/aureus-db-writer/migrations/add_reasoning_entries.sql, services/aureus-trader/journal.py</files>
  <behavior>
    - Script tạo schema bằng migration SQL hoặc `_ensure_schema`, tạo `aureus_trades` test row, gọi `on_strategy_match`, xác nhận 1 row trong `aureus_reasoning_entries`.
    - Script gọi `on_order_filled` hoặc `on_order_opened`, xác nhận ticket/trade_journal_id/signal_snapshot_id được link nếu snapshot table tồn tại.
    - Script gọi `on_order_closed`, xác nhận `success`, `reward`, `pnl`, `evaluated_at` được set.
    - Script cleanup `aureus_reasoning_entries`, `aureus_trade_signal_snapshots`, `aureus_trade_journal`, `aureus_trades` theo trace_id test.
  </behavior>
  <action>
    Tạo `verify_reasoning_bank_db_e2e.py` dựa phong cách `verify_limit_order_lifecycle_db_e2e.py`. Dùng `load_config()` và `AUREUS_DB_DSN`. Script phải tự đảm bảo schema bằng cách chạy SQL migration mới hoặc `_ensure_schema` idempotent, vì rule project yêu cầu DB runtime/e2e khi đổi database. In `PASS reasoning bank DB E2E trace_id=...` khi thành công. Sau khi tests/E2E pass, chạy `gitnexus_detect_changes({scope: "all"})` trước khi kết thúc để xác nhận scope chỉ gồm migration/journal/tests/script. Nếu command lỗi do service chưa chạy, đọc `D:/Aureus/RUN_SERVICES.md` và chạy đúng service DB trước khi retry.
  </action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-trader && python -m pytest tests/test_journal.py -k reasoning -x && python scripts/verify_reasoning_bank_db_e2e.py</automated>
  </verify>
  <done>Unit tests reasoning pass; DB E2E tạo và xác nhận row thật; cleanup xong; `gitnexus_detect_changes({scope: "all"})` reported expected files/flows only.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| STRATEGY_MATCH event -> trader DB | Event payload có thể thiếu/sai kiểu, đi vào DB JSONB/text fields. |
| MT5 order lifecycle event -> reasoning outcome | ORDER_OPENED/ORDER_CLOSED có ticket/pnl/time từ runtime MT5/gateway, update reasoning analytics. |
| Reasoning DB -> future Telegram/analytics | Stored reasoning/context có thể lộ dữ liệu nhạy cảm nếu copy raw prompt/account/secrets. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260502-wur-01 | Tampering | `on_strategy_match` event payload | mitigate | Reuse existing validation for trace_id/strategy_name/direction/symbol; store only normalized active_signals/context_filters; no raw prompt dump. |
| T-260502-wur-02 | Information Disclosure | `aureus_reasoning_entries.reasoning_text/context_filters` | mitigate | Do not store env/secrets/account identifiers; only strategy rationale fields present in event and normalized JSON context. |
| T-260502-wur-03 | Denial of Service | Reasoning insert on hot path | mitigate | Wrap insert/update in try/except; failures log only and must not block journal/order dispatch. |
| T-260502-wur-04 | Repudiation | Outcome update attribution | mitigate | Link all updates by trace_id plus trade_journal_id/ticket; timestamps `created_at/evaluated_at/updated_at`. |
| T-260502-wur-05 | Elevation of Privilege | Future retrieval/LLM judge | accept | Retrieval/LLM judge explicitly out of scope; no new external API or decision injection in MVP. |
</threat_model>

<verification>
1. Unit: `cd D:/Aureus/services/aureus-trader && python -m pytest tests/test_journal.py -k reasoning -x`
2. Regression subset: `cd D:/Aureus/services/aureus-trader && python -m pytest tests/test_journal.py -k "TestOnStrategyMatchInputValidation or TestPendingOrderLifecycle or TestOnOrderClosedInputValidation" -x`
3. DB runtime/e2e: `cd D:/Aureus/services/aureus-trader && python scripts/verify_reasoning_bank_db_e2e.py`
4. GitNexus scope: run `gitnexus_detect_changes({scope: "all"})` before completion.
</verification>

<success_criteria>
- `aureus_reasoning_entries` exists with trace_id-based append-only decision row.
- Strategy match creates reasoning row without blocking dispatch on failure.
- Order opened/filled links execution identifiers to existing reasoning row.
- Order closed attaches outcome metrics to existing reasoning row.
- No retrieval, no embedding, no LLM judge, no API endpoint in this MVP.
- DB E2E creates and validates real data, then cleans up.
</success_criteria>

<output>
Sau khi hoàn tất, tạo `D:/Aureus/.planning/quick/260502-wur-th-c-hi-n-implement-theo-plan-planning-q/260502-wur-SUMMARY.md`.
</output>
