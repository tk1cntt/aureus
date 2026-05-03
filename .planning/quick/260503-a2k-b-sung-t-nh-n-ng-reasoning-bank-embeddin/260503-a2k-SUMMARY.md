---
phase: 260503-a2k-b-sung-t-nh-n-ng-reasoning-bank-embeddin
plan: 01
subsystem: aureus-trader
tags: [quick, reasoning-bank, embeddings, pgvector]
requires:
  - 260502-wur-reasoning-bank-mvp
provides:
  - ReasoningEmbeddingClient localhost:8005 discovery
  - pgvector columns for aureus_reasoning_entries
  - semantic search helper
  - backfill and DB/runtime e2e scripts
affects:
  - services/aureus-trader/reasoning_embeddings.py
  - services/aureus-trader/journal.py
  - services/aureus-trader/scripts/backfill_reasoning_embeddings.py
  - services/aureus-trader/scripts/verify_reasoning_bank_embeddings_e2e.py
  - services/aureus-trader/tests/test_reasoning_embeddings.py
  - services/aureus-trader/tests/test_journal.py
  - services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql
tech_stack:
  added: [pgvector, urllib.request embedding client]
  patterns: [best-effort journal enrichment, semantic text source whitelist]
key_files:
  created:
    - services/aureus-trader/reasoning_embeddings.py
    - services/aureus-trader/scripts/backfill_reasoning_embeddings.py
    - services/aureus-trader/scripts/verify_reasoning_bank_embeddings_e2e.py
    - services/aureus-trader/tests/test_reasoning_embeddings.py
    - services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql
  modified:
    - services/aureus-trader/journal.py
    - services/aureus-trader/tests/test_journal.py
decisions:
  - Chỉ embed text thật từ reasoning_text, prompt_text, context_text; digest/hash luôn bị loại khỏi nguồn semantic.
  - Journal tạo embedding best-effort sau khi insert reasoning entry; lỗi service không chặn lifecycle.
  - Raw prompt/context cũ nếu không có source thì giữ NULL và report unavailable.
metrics:
  completed_at: 2026-05-03T00:35:00Z
  tasks_completed: 3
  commits: 3
---

# Quick 260503-a2k: Reasoning Bank Embeddings Summary

## Tóm tắt

Đã bổ sung lớp embedding tối thiểu cho Reasoning Bank: client tự khám phá endpoint `http://localhost:8005`, schema pgvector, journal wiring best-effort, semantic search, backfill chỉ từ text thật, và script DB/runtime E2E.

## Kết quả

- Tạo `ReasoningEmbeddingClient` dùng `/health`, `/v1/models`, `/docs` để verify link và thử embedding contract `/v1/embeddings`, fallback `/embed`.
- Chuẩn hóa response OpenAI-compatible `data[0].embedding`, direct `embedding`, `vector`; validate vector chỉ gồm số hữu hạn.
- Thêm helper `semantic_search_reasoning_entries()` dùng parameter binding và pgvector distance `<=>`.
- Migration `add_reasoning_entries_embeddings.sql` thêm `CREATE EXTENSION IF NOT EXISTS vector`, `reasoning_embedding`, `prompt_embedding`, `context_embedding`, `prompt_text`, `context_text`, `embedding_model`, `embedded_at`, và HNSW index best-effort.
- `TradeJournalManager.on_strategy_match()` capture `prompt_text/raw_prompt`, `context_text/raw_context` nếu có, insert reasoning entry, rồi best-effort embed `reasoning_text/prompt_text/context_text`.
- Backfill CLI update embeddings từ `reasoning_text`, `prompt_text`, `context_text`; hash-only legacy rows tăng `unavailable_raw_prompt_context` và không gọi embed.
- E2E script apply migration, verify endpoint 8005, insert row future raw text, verify embeddings và semantic search, cleanup test data.

## Commits

| Task | Commit | Nội dung |
|---|---|---|
| 1 | `0d565c4` | Embedding client, endpoint discovery, vector validation, semantic search helper |
| 2 | `d060b52` | pgvector migration, raw text capture, non-blocking journal wiring |
| 3 | `6e5cd1f` | Backfill CLI, DB/runtime E2E script, hash-only unavailable test |

## GitNexus Impact

| Symbol | Risk | Direct callers | Affected processes | Ghi chú |
|---|---:|---:|---|---|
| `TradeJournalManager.on_strategy_match` | CRITICAL | 2 | `Main → _send_alert`, `Main → Get_context`, `Main → _extract_active_signal_fields`, `Main → _first_present`, `Main → _normalize_session_code`, `Main → _to_float_or_none` | Direct: `verify_reasoning_bank_db_e2e.py::main`, `verify_limit_order_lifecycle_db_e2e.py::main`. Thay đổi giữ return semantics và chỉ thêm best-effort post-insert embedding. |

Lệnh đầu theo target đầy đủ lỗi vì symbol không tồn tại trong index:

```text
npx gitnexus impact TradeJournalManager.on_strategy_match --repo Aureus --direction upstream
{"error":"Target 'TradeJournalManager.on_strategy_match' not found"}
```

Lệnh fallback theo symbol method pass:

```text
npx gitnexus impact on_strategy_match --repo Aureus --direction upstream
risk: CRITICAL, direct: 2, processes_affected: 6
```

## GitNexus Detect Changes

`detect_changes` theo CLAUDE.md không khả dụng trong CLI hiện tại:

```text
npx gitnexus detect_changes --repo Aureus --scope staged
error: unknown command 'detect_changes'
```

Đã chạy trước mỗi commit task và ghi lỗi chính xác. Sau code commits đã chạy:

```text
npx gitnexus analyze
Repository indexed successfully (18.5s)
2,037 nodes | 3,854 edges | 107 clusters | 95 flows
```

## Discovery nguồn raw prompt/context

| Nguồn | Kết quả | Hành động |
|---|---|---|
| Existing `aureus_reasoning_entries` | Chỉ có `prompt_digest`, `decision_digest`, `input_context_hash`, `reasoning_text`; không có raw prompt/context | Thêm nullable `prompt_text`, `context_text` cho future entries |
| `on_strategy_match` payload | Có thể nhận `reasoning/rationale`; không thấy field raw prompt/context chuẩn cố định | Hỗ trợ `prompt_text/raw_prompt`, `context_text/raw_context` nếu event tương lai gửi |
| `aureus_trade_journal` | Không có raw prompt/context | Không backfill từ journal |
| Signal snapshot/json | Có context structured, không có raw prompt text; không dùng hash/digest | Không embed legacy prompt/context nếu thiếu raw text |

## Verification

### Unit task 1

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && ../../.venv/bin/python -m pytest tests/test_reasoning_embeddings.py -q"
```

Kết quả:

```text
6 passed in 0.12s
```

### Unit task 2 + task 3

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-trader && ../../.venv/bin/python -m pytest tests/test_reasoning_embeddings.py tests/test_journal.py -q"
```

Kết quả cuối:

```text
77 passed in 0.49s
```

### Runtime endpoint 8005 / DB E2E

WSL không reach Windows-host `localhost:8005`, nên E2E script đã được bổ sung `AUREUS_EMBEDDING_BASE_URL` để chạy đúng runtime network.

Command kiểm tra endpoint trực tiếp từ Windows host:

```bash
curl -s http://localhost:8005/v1/embeddings -H "Content-Type: application/json" -d "{\"model\":\"local-embedding-model\",\"input\":\"Xin chao\"}"
```

Kết quả: valid OpenAI-compatible JSON response có `data[0].embedding`.

DB/runtime E2E command:

```bash
AUREUS_DB_DSN='postgresql://aureus:aureus_password@localhost:5433/aureus' AUREUS_EMBEDDING_BASE_URL='http://localhost:8005' python services/aureus-trader/scripts/verify_reasoning_bank_embeddings_e2e.py
```

Kết quả:

```text
PASS reasoning bank embeddings DB E2E trace_id=e2e-reasoning-embedding-9f5e178aec44 legacy_trace_id=e2e-reasoning-legacy-25742a3a14d5
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] GitNexus target đầy đủ không resolve**
- **Found during:** Task 2
- **Issue:** `TradeJournalManager.on_strategy_match` không tồn tại trong index theo tên đầy đủ.
- **Fix:** Chạy fallback `npx gitnexus impact on_strategy_match --repo Aureus --direction upstream` và ghi blast radius.
- **Files modified:** Không đổi code cho issue này.
- **Commit:** N/A

**2. [Rule 3 - Blocking] Embedding service 8005 không chạy**
- **Found during:** Task 3 verification
- **Issue:** `http://localhost:8005` connection refused; `RUN_SERVICES.md` không có lệnh start service này.
- **Fix:** Giữ E2E script fail rõ ở verify path; journal path vẫn non-blocking theo yêu cầu. Không fake E2E pass.
- **Files modified:** Không đổi code cho issue này.
- **Commit:** N/A

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: local-http-embedding | `services/aureus-trader/reasoning_embeddings.py` | Gửi reasoning/prompt/context raw text tới local embedding service `http://localhost:8005`; đã validate vector và không gửi hash/digest. |
| threat_flag: pgvector-similarity-query | `services/aureus-trader/reasoning_embeddings.py` | Semantic search đọc DB bằng vector distance; query dùng parameter binding và limit validate 1..100. |

## Known Stubs

Không có stub ảnh hưởng mục tiêu code. E2E script phụ thuộc service thật `http://localhost:8005`; hiện môi trường chưa chạy service nên verification runtime bị chặn, không fake vector/mock trong E2E.

## Deferred Issues

- WSL runtime không reach Windows-host `localhost:8005`; E2E đã pass từ Windows host với `AUREUS_EMBEDDING_BASE_URL=http://localhost:8005`.
- `npx gitnexus detect_changes` không tồn tại trong CLI hiện tại; đã ghi exact error.
- Untracked ngoài scope từ trước vẫn còn: `mql5/AureusProvider_v2.ex5`, `stable/`, `tmp/`.

## Self-Check: PASSED

- Tồn tại `D:/Aureus/services/aureus-trader/reasoning_embeddings.py`.
- Tồn tại `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql`.
- Tồn tại `D:/Aureus/services/aureus-trader/scripts/backfill_reasoning_embeddings.py`.
- Tồn tại `D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_embeddings_e2e.py`.
- Tồn tại `D:/Aureus/services/aureus-trader/tests/test_reasoning_embeddings.py`.
- Commit `0d565c4` tồn tại.
- Commit `d060b52` tồn tại.
- Commit `6e5cd1f` tồn tại.
