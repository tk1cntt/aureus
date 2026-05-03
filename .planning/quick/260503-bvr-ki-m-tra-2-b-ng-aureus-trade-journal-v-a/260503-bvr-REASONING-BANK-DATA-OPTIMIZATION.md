# Quick 260503-bvr: Kế hoạch tối ưu dữ liệu Reasoning Bank

## Phạm vi

Report này chỉ inspect schema/source hiện có và đề xuất kế hoạch tối ưu. Không implement DB/code change.

Giả định dùng bằng chứng từ các file:

- `services/aureus-db-writer/migrations/add_trade_journal.sql`
- `services/aureus-db-writer/migrations/add_trade_evaluations.sql`
- `services/aureus-db-writer/migrations/optimize_trade_signal_snapshots_storage.sql`
- `services/aureus-db-writer/migrations/add_reasoning_entries.sql`
- `services/aureus-db-writer/migrations/add_reasoning_entries_embeddings.sql`
- `services/aureus-trader/journal.py`
- `services/aureus-trader/reasoning_embeddings.py`
- `services/aureus-trader/scripts/verify_reasoning_bank_db_e2e.py`
- `services/aureus-trader/scripts/verify_reasoning_bank_embeddings_e2e.py`

## Kết luận ngắn

`aureus_reasoning_entries` không nên bị xoá toàn bộ. Bảng này vẫn là nơi lưu memory-specific fields mà `aureus_trade_journal` và `aureus_trade_signal_snapshots` không có: `reasoning_text`, `prompt_text`, `context_text`, `prompt_digest`, `decision_digest`, `input_context_hash`, `reasoning_embedding`, `prompt_embedding`, `context_embedding`, `embedding_model`, `embedded_at`, và semantic `reasoning_source`.

Tối ưu đúng hướng: giữ `aureus_reasoning_entries` mỏng hơn, dùng `trade_journal_id` và `signal_snapshot_id` để đọc strategy/lifecycle/outcome/signal context từ `aureus_trade_journal` và `aureus_trade_signal_snapshots`, không tiếp tục nhân bản các cột đó dài hạn.

## Bằng chứng schema/source hiện tại

### `aureus_trade_journal`

Migration `add_trade_journal.sql` tạo bảng lifecycle chính:

- Identity/join: `id`, `trace_id`
- Strategy plan: `strategy_name`, `strategy_id`, `direction`, `symbol`, `score`
- Signal context: `active_signals`, `context_filters`, `origin_timestamp`
- Order lifecycle: `status`, `ticket`, `pending_order_id`, `entry_deal_ticket`, `cmd_id`, `mt5_comment`, `entry_price`, `entry_time`, `position_id`, `lot_size`, `sl_initial`, `tp_initial`
- Exit/outcome: `exit_price`, `exit_time`, `exit_reason`, `duration_seconds`, `pnl`, `pnl_pips`, `commission`, `swap`, `result`
- Metadata: `created_at`, `updated_at`

Index hiện có cho strategy/symbol/status/result/pending/order/cmd và GIN cho `active_signals`, `context_filters`.

### `aureus_trade_signal_snapshots`

Migration `add_trade_evaluations.sql` tạo snapshot theo trade:

- Join/identity: `id`, `trade_journal_id`, `trace_id`, `ticket`
- Strategy/scope: `strategy_name`, `symbol`, `timeframe`, `signal_schema_version`
- Indicator context: `atr`, `ema_21`, `ema_34`, `ema_55`, `ema_89`, `ema_100`, `ema_200`, `vol_sma_20`, `session`, `candle_color_*`, `bb_*`, `cisd_*`
- Metadata: `created_at`

`trade_journal_id` là FK tới `aureus_trade_journal(id)`. Constraint hiện có trong base migration là `uq_trade_signal_snapshot_trade UNIQUE (trade_journal_id)`.

Migration `optimize_trade_signal_snapshots_storage.sql` cho thấy hướng storage mới từng loại bỏ các cột legacy `signal_snapshot`, `cisd_direction`, `ema21`, `ema55`, thêm `timeframe`, `signal_schema_version`, archive/prune, và unique `(trade_journal_id, signal_schema_version)`. Điều này củng cố việc snapshot là bảng context/indicator, không phải nơi lưu reasoning text.

### `aureus_reasoning_entries`

Migration `add_reasoning_entries.sql` tạo Reasoning Bank:

- Join: `trace_id`, `trade_journal_id`, `signal_snapshot_id`
- Cột đang duplicate journal: `strategy_id`, `strategy_name`, `symbol`, `timeframe`, `direction`, `active_signals`, `context_filters`, `ticket`, `pending_order_id`, `entry_time`, `exit_time`, `success`, `reward`, `pnl`, `pnl_pips`, `result`
- Memory fields: `reasoning_source`, `prompt_digest`, `decision_digest`, `input_context_hash`, `reasoning_text`, `decision_action`, `confidence`, `created_at`, `evaluated_at`, `updated_at`

Migration `add_reasoning_entries_embeddings.sql` bổ sung memory/search fields:

- `prompt_text`, `context_text`
- `reasoning_embedding`, `prompt_embedding`, `context_embedding`
- `embedding_model`, `embedded_at`
- HNSW indexes cho embedding columns khi pgvector hỗ trợ.

### Write-path trong `journal.py`

`TradeJournalManager.on_strategy_match()`:

- Insert `aureus_trade_journal` với strategy/signal context.
- Insert `aureus_reasoning_entries` với `trade_journal_id`, strategy fields, `active_signals`, `context_filters`, `reasoning_text`, `prompt_text`, `context_text`, `decision_action`.
- Gọi embedding trên text sources.

`TradeJournalManager.on_order_opened()`:

- Update `aureus_trade_journal` sang `EXECUTED`, set `ticket`, `entry_time`, order fields.
- Insert `aureus_trade_signal_snapshots` từ event/journal fallback.
- Update `aureus_reasoning_entries` set `trade_journal_id`, `signal_snapshot_id`, `ticket`, `pending_order_id`, `entry_time`.

`TradeJournalManager.on_order_closed()`:

- Update `aureus_trade_journal` sang `CLOSED`, set outcome fields.
- Update `aureus_reasoning_entries` set `success`, `reward`, `pnl`, `pnl_pips`, `result`, `exit_time`, `evaluated_at`.

### Read-path trong `reasoning_embeddings.py`

`fetch_strategy_reasoning_insights()` hiện đọc trực tiếp `strategy_name`, `symbol`, `direction`, `success`, `reward`, `pnl_pips`, `reasoning_text`, `reasoning_embedding` từ `aureus_reasoning_entries`. Đây là nơi chính cần đổi sang joined read model nếu giảm duplicate lifecycle/outcome fields.

`semantic_search_reasoning_entries()` hiện trả `id`, `trace_id`, `strategy_name`, `symbol`, `reasoning_text`, `distance` trực tiếp từ `aureus_reasoning_entries`. Khi strategy/symbol chuyển sang journal source-of-truth, semantic search caller nên join journal để lấy scope/display fields.

## Field reuse matrix

| Nhóm dữ liệu | Field | Source-of-truth nên dùng | Tình trạng hiện tại | Khuyến nghị |
|---|---|---|---|---|
| Join | `trace_id` | `aureus_trades`/journal/reasoning | Có ở cả 3 bảng | Giữ trong reasoning để trace/debug, nhưng join chính bằng id |
| Join | `trade_journal_id` | `aureus_trade_journal.id` | Có FK-like trong reasoning | Giữ, formalize/index nếu thiếu |
| Join | `signal_snapshot_id` | `aureus_trade_signal_snapshots.id` | Có trong reasoning nhưng migration chưa có FK/index rõ | Giữ, thêm FK/index trong future migration |
| Strategy | `strategy_id` | `aureus_trade_journal` | Duplicate trong reasoning | Đọc từ journal lâu dài |
| Strategy | `strategy_name` | `aureus_trade_journal` | Duplicate trong reasoning/snapshot | Đọc từ journal lâu dài; snapshot chỉ giữ denormalized audit nếu cần |
| Scope | `symbol` | `aureus_trade_journal` | Duplicate trong reasoning/snapshot | Đọc từ journal lâu dài |
| Scope | `direction` | `aureus_trade_journal` | Duplicate trong reasoning | Đọc từ journal lâu dài |
| Score/confidence | `score` / `confidence` | `aureus_trade_journal.score` hoặc reasoning confidence semantics | Similar but not identical | Nếu `confidence` là strategy score, join `score`; nếu model confidence khác, giữ `confidence` |
| Signal context | `active_signals` | `aureus_trade_journal` | Duplicate in reasoning | Đọc từ journal; không update duplicate dài hạn |
| Signal context | `context_filters` | `aureus_trade_journal` | Duplicate in reasoning | Đọc từ journal; không update duplicate dài hạn |
| Snapshot context | `timeframe` | `aureus_trade_signal_snapshots` | Duplicate/nullable in reasoning | Đọc từ snapshot |
| Snapshot context | `atr`, `ema_*`, `vol_sma_20`, `session`, `candle_color_*`, `bb_*`, `cisd_*` | `aureus_trade_signal_snapshots` | Không có trong reasoning | Join snapshot khi cần context |
| Order | `ticket` | `aureus_trade_journal` / snapshot audit | Duplicate in reasoning | Đọc từ journal; snapshot giữ ticket tại thời điểm snapshot |
| Order | `pending_order_id` | `aureus_trade_journal` | Duplicate in reasoning | Đọc từ journal |
| Lifecycle | `entry_time`, `exit_time` | `aureus_trade_journal` | Duplicate in reasoning | Đọc từ journal |
| Outcome | `pnl`, `pnl_pips`, `result` | `aureus_trade_journal` | Duplicate in reasoning | Đọc từ journal sau parity validation |
| Outcome-derived | `success`, `reward` | Derived from journal `result`/`pnl_pips`/`pnl` | Stored in reasoning | Prefer computed in read model; keep only during migration/parity |
| Memory | `reasoning_source` | `aureus_reasoning_entries` | Only reasoning | Giữ |
| Memory | `reasoning_text` | `aureus_reasoning_entries` | Only reasoning | Giữ |
| Memory | `prompt_text`, `context_text` | `aureus_reasoning_entries` | Only reasoning | Giữ, controlled access |
| Digest/hash | `prompt_digest`, `decision_digest`, `input_context_hash` | `aureus_reasoning_entries` | Only reasoning | Giữ |
| Embeddings | `reasoning_embedding`, `prompt_embedding`, `context_embedding` | `aureus_reasoning_entries` | Only reasoning | Giữ |
| Embedding metadata | `embedding_model`, `embedded_at` | `aureus_reasoning_entries` | Only reasoning | Giữ |
| Reasoning action | `decision_action` | `aureus_reasoning_entries` | Only reasoning | Giữ; có thể khác `direction` nếu future action không chỉ BUY/SELL |

## Vai trò tối thiểu khuyến nghị cho `aureus_reasoning_entries`

Giữ bảng này làm memory index mỏng:

- Identity/join: `id`, `trace_id`, `trade_journal_id`, `signal_snapshot_id`
- Memory/source semantics: `reasoning_source`, `decision_action`, `confidence` nếu khác `journal.score`
- Text: `reasoning_text`, `prompt_text`, `context_text`
- Digests/hashes: `prompt_digest`, `decision_digest`, `input_context_hash`
- Embeddings/search: `reasoning_embedding`, `prompt_embedding`, `context_embedding`, `embedding_model`, `embedded_at`
- Lifecycle metadata riêng của memory: `created_at`, `evaluated_at`, `updated_at`

Không đưa raw `prompt_text`/`context_text` ra Telegram/read model mặc định. Telegram insights chỉ nên dùng trimmed `reasoning_text` hoặc lessons đã redact/trim như `_trim_lesson()` hiện làm.

## Join keys

| From | To | Mục đích | Ghi chú |
|---|---|---|---|
| `aureus_reasoning_entries.trade_journal_id` | `aureus_trade_journal.id` | Reuse strategy/lifecycle/outcome | Join chính, tránh drift |
| `aureus_reasoning_entries.signal_snapshot_id` | `aureus_trade_signal_snapshots.id` | Reuse indicator context | Cần FK/index formal trong future migration nếu hiện chưa có |
| `aureus_trade_signal_snapshots.trade_journal_id` | `aureus_trade_journal.id` | Snapshot theo trade | Đã có FK trong migrations |
| `trace_id` | across tables | Debug/fallback/audit | Không nên là join primary nếu đã có id |

## Query/read-model shape đề xuất

Tạo view hoặc query helper kiểu `reasoning_entries -> trade_journal -> trade_signal_snapshots`:

```sql
SELECT
    re.id AS reasoning_entry_id,
    re.trace_id,
    re.reasoning_source,
    re.reasoning_text,
    re.prompt_digest,
    re.decision_digest,
    re.input_context_hash,
    re.decision_action,
    re.confidence,
    re.reasoning_embedding,
    re.prompt_embedding,
    re.context_embedding,
    re.embedding_model,
    re.embedded_at,
    tj.strategy_id,
    tj.strategy_name,
    tj.direction,
    tj.symbol,
    tj.score,
    tj.active_signals,
    tj.context_filters,
    tj.ticket,
    tj.pending_order_id,
    tj.entry_time,
    tj.exit_time,
    tj.pnl,
    tj.pnl_pips,
    tj.result,
    CASE WHEN tj.result = 'WIN' THEN TRUE WHEN tj.result = 'LOSS' THEN FALSE ELSE NULL END AS success,
    COALESCE(tj.pnl_pips, tj.pnl) AS reward,
    ts.timeframe,
    ts.signal_schema_version,
    ts.atr,
    ts.ema_21,
    ts.ema_34,
    ts.ema_55,
    ts.ema_89,
    ts.ema_100,
    ts.ema_200,
    ts.vol_sma_20,
    ts.session,
    ts.cisd_m5,
    ts.cisd_m15,
    ts.cisd_m30,
    ts.cisd_h1
FROM aureus_reasoning_entries re
LEFT JOIN aureus_trade_journal tj ON tj.id = re.trade_journal_id
LEFT JOIN aureus_trade_signal_snapshots ts ON ts.id = re.signal_snapshot_id;
```

Nếu chọn SQL view: đặt tên ví dụ `aureus_reasoning_entries_enriched`. Nếu chọn Python helper: dùng cùng projection trong `fetch_strategy_reasoning_insights()` và `semantic_search_reasoning_entries()`.

## Migration/refactor steps đề xuất

1. Formalize `signal_snapshot_id` relation nếu thiếu: add FK từ `aureus_reasoning_entries.signal_snapshot_id` tới `aureus_trade_signal_snapshots(id)` và index cho `trade_journal_id`, `signal_snapshot_id`.
2. Tạo read model/view hoặc Python query helper join `reasoning_entries -> trade_journal -> trade_signal_snapshots`.
3. Refactor `fetch_strategy_reasoning_insights()` để filter/group bằng `tj.strategy_name`, `tj.symbol`, `tj.direction`, tính stats từ `tj.result`, `tj.pnl_pips`, `tj.pnl`.
4. Refactor `semantic_search_reasoning_entries()` và caller để lấy display scope từ joined journal, còn embedding/text từ reasoning.
5. Chạy parity validation giữa old duplicate fields và joined fields.
6. Sau parity pass, stop updating duplicate lifecycle/outcome fields trong `aureus_reasoning_entries` write path.
7. Chỉ deprecate duplicate columns ở task sau, sau backfill/audit và có rollback plan.

## DB runtime E2E validation strategy cho future DB change

Do future work chạm database, phải test E2E với DB runtime thật:

1. Apply migrations lên DB test/dev.
2. Insert `aureus_trades` row.
3. Gọi `TradeJournalManager.on_strategy_match()` tạo `aureus_trade_journal` và `aureus_reasoning_entries` với memory fields + join ids.
4. Gọi `on_order_opened()` tạo `aureus_trade_signal_snapshots` và link `signal_snapshot_id`.
5. Gọi `on_order_closed()` đóng journal.
6. Query joined insight/read model xác nhận strategy stats, recent lessons, similar lessons dùng joined lifecycle/outcome fields.
7. Chạy semantic search xác nhận `reasoning_embedding` vẫn searchable.
8. So sánh parity: stats old duplicate columns vs stats joined journal trước khi stop duplicate updates.
9. Xác nhận Telegram/read model không expose raw `prompt_text`/`context_text` mặc định.

## Risks/tradeoffs

Từ khoá kiểm chứng: risk, tradeoff.

| Risk | Tradeoff | Mitigation |
|---|---|---|
| Join phức tạp hơn read path | Giảm duplicate write/drift nhưng tăng query complexity | Dùng view/query helper + indexes |
| Existing consumers phụ thuộc duplicate fields | Refactor phải staged | Giữ duplicate columns qua parity window |
| `signal_snapshot_id` chưa formal FK/index | Add constraint có thể fail nếu dữ liệu orphan | Audit/backfill trước migration |
| Raw prompt/context sensitive | Memory search cần text, nhưng Telegram không nên lộ raw prompt/context | Keep controlled fields trong reasoning, redact/trim read model |
| Outcome parity lệch | `success/reward` trong reasoning có thể khác computed từ journal | E2E parity checks trước khi stop updating |
| Snapshot schema version thay đổi | Join by `signal_snapshot_id` ổn định hơn `trade_journal_id` nếu nhiều schema version | Preserve explicit `signal_snapshot_id` |

## Không nên làm ngay

- Không xoá toàn bộ `aureus_reasoning_entries`.
- Không drop duplicate columns ngay trong cùng bước refactor read path.
- Không expose `prompt_text`/`context_text` ra Telegram để debug.
- Không dùng `trace_id` làm join chính khi đã có `trade_journal_id`/`signal_snapshot_id`.
