# Quick 260503-edn: Reasoning Text Data Flow Report

## Executive Conclusion

Kết luận chính: flow runtime hiện tại không tự sản xuất `reasoning_text`, `prompt_text`, `context_text` trong STRATEGY_MATCH payload construction. `publish_strategy_match()` chỉ build payload từ `strategy_result` và `active_signals`, không gán 3 field này. Journal ingestion chỉ copy/propagate nếu upstream payload đã có alias tương ứng. DB schema có cột lưu đủ 3 field; runtime DB hiện reachable nhưng bảng `aureus_reasoning_entries` đang có 0 rows.

Độ tin cậy/confidence: High cho source/schema/current DB. Medium cho producer absence ở toàn pipeline vì đã inspect source paths chính nhưng không có GitNexus MCP callable trong environment này; dùng ripgrep/source read thay thế.

## Field Producer Matrix

| Field | STRATEGY_MATCH payload construction | Journal ingestion | Redis embedding queue | DB persistence | Current DB data | Confidence |
|---|---|---|---|---|---|---|
| `reasoning_text` | Absent. `publish_strategy_match()` không set field này; payload chỉ có strategy/order/signal fields. Evidence: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:184-229`. | Copied/Propagated only. Journal reads `data.reasoning`, `data.rationale`, `match_data.reasoning`, `match_data.rationale`, then inserts as `reasoning_text`. Evidence: `D:/Aureus/services/aureus-trader/journal.py:282-307`. | Copied/Propagated only when non-empty. Evidence: `D:/Aureus/services/aureus-trader/journal.py:310-322`, `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:104-128`. | Persisted as nullable `TEXT`. Evidence: `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries.sql:3-18`. | DB reachable; total 0 rows, non-null count 0. Evidence: command output in Database/Schema Evidence. | High |
| `prompt_text` | Absent. `publish_strategy_match()` không set field này. Evidence: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:197-226`. | Copied/Propagated only. Journal reads `data.prompt_text`, `data.raw_prompt`, `match_data.prompt_text`, `match_data.raw_prompt`. Evidence: `D:/Aureus/services/aureus-trader/journal.py:284-307`. | Copied/Propagated only when non-empty; digest fields ignored. Evidence: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:104-128`. | Persisted as nullable `TEXT` added by embeddings migration. Evidence: `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql:5-12`. | DB reachable; total 0 rows, non-null count 0. Evidence: command output in Database/Schema Evidence. | High |
| `context_text` | Absent. `publish_strategy_match()` không set field này. Evidence: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:197-226`. | Copied/Propagated only. Journal reads `data.context_text`, `data.raw_context`, `match_data.context_text`, `match_data.raw_context`. Evidence: `D:/Aureus/services/aureus-trader/journal.py:284-307`. | Copied/Propagated only when non-empty; hash fields ignored. Evidence: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:104-128`. | Persisted as nullable `TEXT` added by embeddings migration. Evidence: `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql:5-12`. | DB reachable; total 0 rows, non-null count 0. Evidence: command output in Database/Schema Evidence. | High |

## End-to-End Flow Evidence

1. Strategy match publisher builds Redis payload via `publish_strategy_match(redis_client, symbol, strategy_result, active_signals)`.
   - Source: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:184-229`.
   - Payload wrapper `publish_signal_event()` sets `{type, symbol, t, data}` and publishes JSON to `aureus:signals:{symbol}`.
   - Source: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:155-173`.
2. Trader consumes Redis pub/sub, filters only `STRATEGY_MATCH`, validates, builds order command, attaches original event as `strategy_event`, enqueues dispatch.
   - Source: `D:/Aureus/services/aureus-trader/main.py:101-126`.
   - This path does not add `reasoning_text`, `prompt_text`, or `context_text`.
3. Journal ingestion persists trade journal row, then optional reasoning row if journal insert returns id.
   - Source: `D:/Aureus/services/aureus-trader/journal.py:265-307`.
4. Embedding enqueue only uses non-empty text sources selected by `TEXT_SOURCE_FIELDS = ("reasoning_text", "prompt_text", "context_text")`.
   - Source: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:10-15`, `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:104-128`.
5. Worker embeds selected source texts and updates embedding columns; it does not create raw text.
   - Source: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:288-347`.

## STRATEGY_MATCH Payload Construction

`publish_strategy_match()` constructs `data` with `trace_id`, `symbol`, `strategy`, `strategy_id`, `strategy_name`, `side`, order fields, `reason_code`, `origin_timestamp`, `direction`, `active_signals`, `signal_snapshot`, and score/schema fields. Evidence: `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:197-226`.

Producer absence:

- No `reasoning`, `rationale`, `reasoning_text`, `prompt_text`, `raw_prompt`, `context_text`, or `raw_context` assignment in this payload construction block.
- Therefore current source producer for 3 report fields is absent at STRATEGY_MATCH construction stage.
- Confidence: High for inspected function; Medium for broader upstream `strategy_result` because this report did not inspect every strategy evaluator that may place arbitrary extra fields in `strategy_result`, but publisher only whitelists fields listed above.

## Journal Ingestion

Journal copies aliases from payload:

- `reasoning_text = data.get("reasoning", data.get("rationale", match_data.get("reasoning", match_data.get("rationale"))))` at `D:/Aureus/services/aureus-trader/journal.py:284`.
- `prompt_text = data.get("prompt_text", data.get("raw_prompt", match_data.get("prompt_text", match_data.get("raw_prompt"))))` at `D:/Aureus/services/aureus-trader/journal.py:285`.
- `context_text = data.get("context_text", data.get("raw_context", match_data.get("context_text", match_data.get("raw_context"))))` at `D:/Aureus/services/aureus-trader/journal.py:286`.
- Insert persists aliases into `aureus_reasoning_entries(reasoning_text, prompt_text, context_text)` at `D:/Aureus/services/aureus-trader/journal.py:287-309`.

Classification per field at journal stage:

| Field | Stage status | Evidence | Confidence |
|---|---|---|---|
| `reasoning_text` | Copied/Propagated from `reasoning`/`rationale`; not generated | `D:/Aureus/services/aureus-trader/journal.py:284-305` | High |
| `prompt_text` | Copied/Propagated from `prompt_text`/`raw_prompt`; not generated | `D:/Aureus/services/aureus-trader/journal.py:285-306` | High |
| `context_text` | Copied/Propagated from `context_text`/`raw_context`; not generated | `D:/Aureus/services/aureus-trader/journal.py:286-307` | High |

## Redis/DB Persistence

DB raw text insert:

- Journal inserts 3 raw text values directly into `aureus_reasoning_entries`. Evidence: `D:/Aureus/services/aureus-trader/journal.py:287-309`.
- If insert succeeds, journal selects embedding sources from same values plus digest fields. Evidence: `D:/Aureus/services/aureus-trader/journal.py:310-318`.

Redis embedding enqueue:

- `select_embedding_sources()` only returns non-empty string values for `reasoning_text`, `prompt_text`, `context_text`. Evidence: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:104-110`.
- `enqueue_reasoning_embedding_job()` writes JSON with `entry_id`, `trace_id`, `sources` to Redis stream/list key `aureus:reasoning:embedding_jobs`. Evidence: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:113-128`.

Worker persistence:

- `ReasoningEmbeddingWorker.process_once()` reads queued job, selects sources again, then calls `embed_reasoning_entry()`. Evidence: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:288-315`.
- `embed_reasoning_entry()` embeds present source text and updates `reasoning_embedding`, `prompt_embedding`, `context_embedding`; no raw text update occurs. Evidence: `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:318-347`.

DB persistence classification:

| Field | Raw text persistence | Embedding persistence | Producer? | Confidence |
|---|---|---|---|---|
| `reasoning_text` | Persisted if copied value exists | `reasoning_embedding` generated from it | No, copied only | High |
| `prompt_text` | Persisted if copied value exists | `prompt_embedding` generated from it | No, copied only | High |
| `context_text` | Persisted if copied value exists | `context_embedding` generated from it | No, copied only | High |

## Tests/E2E Evidence

Unit tests:

- Journal test injects `reasoning`, `prompt_text`, `context_text` into event data and asserts DB args/sources contain raw text. This proves copy behavior, not producer behavior. Evidence: `D:/Aureus/services/aureus-trader/tests/test_journal.py:241-266`.
- Embedding source test asserts digest/hash fields are skipped and only 3 raw text fields become sources. Evidence: `D:/Aureus/services/aureus-trader/tests/test_reasoning_embeddings.py:80-97`.
- Backfill test shows hash-only prompt/context are unavailable and not reconstructed. Evidence: `D:/Aureus/services/aureus-trader/tests/test_reasoning_embeddings.py:120-158`.

E2E scripts:

- Reuse E2E manually builds STRATEGY_MATCH event containing `reasoning`, `prompt_text`, `context_text`, then asserts persisted row has all three. Evidence: `D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py:65-81`, `D:/Aureus/services/aureus-trader/scripts/verify_reasoning_bank_reuse_e2e.py:133-154`.
- Worker E2E inserts `reasoning_text` directly into DB, enqueues `{"reasoning_text": "worker e2e reasoning"}`, then asserts `reasoning_embedding` exists. Evidence: `D:/Aureus/services/aureus-trader/scripts/verify_reasoning_embedding_worker_e2e.py:31-60`.

Test conclusion:

- Tests confirm persistence and enqueue behavior when input text exists.
- Tests do not prove runtime STRATEGY_MATCH publisher produces these texts.
- Confidence: High.

## Database/Schema Evidence

Schema supports storage:

- Initial reasoning table has nullable `reasoning_text TEXT`. Evidence: `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries.sql:3-18`.
- Embeddings migration adds nullable `prompt_text TEXT`, `context_text TEXT`, and embedding columns. Evidence: `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql:5-12`.
- Comments state `prompt_text`/`context_text` are raw capture only and never derived from digest/hash. Evidence: `D:/Aureus/services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql:41-45`.

DB reachable: yes.

Read-only command executed:

```bash
wsl -d Aureus -e bash -lc "docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='aureus_reasoning_entries' AND column_name IN ('reasoning_text','prompt_text','context_text','reasoning_embedding','prompt_embedding','context_embedding') ORDER BY column_name; SELECT COUNT(*) AS total, COUNT(reasoning_text) AS reasoning_non_null, COUNT(prompt_text) AS prompt_non_null, COUNT(context_text) AS context_non_null FROM aureus_reasoning_entries; SELECT id, trace_id, reasoning_text IS NOT NULL AS has_reasoning, prompt_text IS NOT NULL AS has_prompt, context_text IS NOT NULL AS has_context, created_at FROM aureus_reasoning_entries ORDER BY created_at DESC LIMIT 5;\""
```

Output:

```text
     column_name     |  data_type   
---------------------+--------------
 context_embedding   | USER-DEFINED
 context_text        | text
 prompt_embedding    | USER-DEFINED
 prompt_text         | text
 reasoning_embedding | USER-DEFINED
 reasoning_text      | text
(6 rows)

 total | reasoning_non_null | prompt_non_null | context_non_null 
-------+--------------------+-----------------+------------------
     0 |                  0 |               0 |                0
(1 row)

 id | trace_id | has_reasoning | has_prompt | has_context | created_at 
----+----------+---------------+------------+-------------+------------
(0 rows)
```

DB conclusion:

- Schema exists and can store all 3 raw fields plus embeddings.
- Current DB has no `aureus_reasoning_entries` data to validate non-null runtime producer behavior.
- Confidence: High for schema; High for current empty DB; no runtime non-null evidence available.

## Gaps/Unknowns

- GitNexus MCP tools were required by project instruction, but no `gitnexus_*` MCP tool namespace was available in this execution environment. Substitute evidence came from direct source reads and content search.
- No production source edited.
- Current runtime DB has zero rows in `aureus_reasoning_entries`, so report cannot prove live producer presence from stored data.
- Upstream strategy evaluator may have internal rationale concepts, but `publish_strategy_match()` whitelisted payload does not propagate `reasoning_text`, `prompt_text`, or `context_text` unless source code is changed.

## Confidence Levels

| Conclusion | Confidence | Basis |
|---|---|---|
| `publish_strategy_match()` does not include `reasoning_text`, `prompt_text`, `context_text` | High | Direct source evidence `D:/Aureus/services/aureus-signal/engine/signal_event_publisher.py:197-226` |
| Journal does not generate these fields; it copies aliases if present | High | Direct source evidence `D:/Aureus/services/aureus-trader/journal.py:284-307` |
| Redis embedding queue carries only non-empty copied source texts | High | Direct source evidence `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:104-128` |
| Worker persists embeddings, not raw text producers | High | Direct source evidence `D:/Aureus/services/aureus-trader/reasoning_embeddings.py:318-347` |
| DB schema supports all 3 raw fields | High | Migration evidence and live schema query |
| Current DB contains no persisted examples | High | Live read-only query returned total 0 rows |
| End-to-end runtime has no actual producer for these fields today | Medium | Strong publisher/journal/source evidence plus empty DB; reduced only because GitNexus MCP unavailable and no live strategy event sample existed |

## Self-Check

- Covered STRATEGY_MATCH payload construction: yes.
- Covered journal ingestion: yes.
- Covered Redis/DB persistence: yes.
- Covered tests/E2E: yes.
- Covered current database/schema: yes, DB reachable and queried read-only.
- Identified exact producer/absence for `reasoning_text`: copied from upstream aliases only; no current publisher producer.
- Identified exact producer/absence for `prompt_text`: copied from upstream aliases only; no current publisher producer.
- Identified exact producer/absence for `context_text`: copied from upstream aliases only; no current publisher producer.
- Production source changes: none intended.
