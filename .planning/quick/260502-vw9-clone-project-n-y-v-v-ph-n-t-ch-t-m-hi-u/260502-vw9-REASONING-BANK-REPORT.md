# Reasoning Bank

## Tóm tắt kết luận

FenixAI_tradingBot có Reasoning Bank đủ rõ để tham khảo kiến trúc, nhưng không nên copy thẳng vào Aureus.

Kết luận chính:

- Reasoning Bank trong FenixAI là bộ nhớ kinh nghiệm cho agent LLM: lưu prompt, reasoning, action, confidence, backend, latency, metadata, embedding tùy chọn, outcome trade, judge feedback.
- Luồng chính gồm: agent tạo quyết định → lưu reasoning theo agent → lần quyết định sau truy hồi context tương tự → sau trade hoặc sau horizon evaluation thì cập nhật success/reward → thống kê pattern thành insight.
- Storage bản chính là JSONL theo agent trong `logs/reasoning_bank/`; bản tối ưu dùng SQLite trong cùng thư mục.
- Với Aureus, fit tốt nhất là làm layer research/analytics sau journal/order lifecycle, không nhúng trực tiếp vào hot path gửi lệnh MT5.
- Tích hợp nên bắt đầu bằng append-only storage trong database Aureus, liên kết `trace_id`, order lifecycle, signal snapshot, strategy id, Telegram insight. Sau đó mới thêm retrieval vào strategy evaluation intelligence.

## Evidence từ FenixAI_tradingBot

Repo clone:

- `D:/Aureus/stable/FenixAI_tradingBot/`
- Origin: `https://github.com/raftersvk/FenixAI_tradingBot`

Các file/module liên quan Reasoning Bank đã đọc:

| File | Vai trò |
|---|---|
| `src/memory/reasoning_bank.py` | Implementation chính: `ReasoningEntry`, `ReasoningBank`, JSONL storage, retrieval, outcome update, judge feedback, success pattern synthesis. |
| `src/memory/reasoning_bank_optimized.py` | Backend SQLite tối ưu: table `reasoning_entries`, index theo agent/digest/created_at, API tương tự bản JSONL. |
| `src/memory/trade_memory.py` | Lưu trade memory JSON và tự gắn outcome/reward vào Reasoning Bank sau khi có PnL. |
| `src/core/langgraph_orchestrator.py` | Luồng agent LangGraph: lấy historical context từ bank, store decision, inject context vào risk manager/final flow. |
| `src/inference/reasoning_judge.py` | LLM-as-a-judge đánh giá reasoning, trả structured verdict để attach vào entry. |
| `src/analysis/auto_evaluator.py` | Đánh giá pending reasoning theo biến động giá sau horizon, cập nhật success/reward. |
| `src/trading/engine.py` | Khi order success/fail, update outcome cho reasoning digest liên quan. |
| `src/api/server.py` | API query/search reasoning; một phần endpoint dùng DB `AgentOutput`, không hoàn toàn trùng với JSONL bank. |
| `config/fenix.yaml` | Config trading/agent/LLM/monitoring; không thấy config riêng Reasoning Bank, default nằm trong code. |
| `.gitignore` | Ignore `reasoning_bank/`, `llm_responses/`, cho thấy dữ liệu reasoning được xem là runtime/sensitive. |

Evidence cụ thể:

- `src/memory/reasoning_bank.py` định nghĩa `ReasoningEntry` gồm `agent`, `prompt_digest`, `prompt`, `reasoning`, `action`, `confidence`, `backend`, `latency_ms`, `metadata`, `created_at`, `embedding`, `success`, `reward`, `reward_signal`, `near_miss`, `trade_id`, `judge_*`.
- `ReasoningBank.store_entry()` tạo digest bằng SHA-256 từ prompt, extract action/confidence/reasoning từ normalized result, append vào `{agent}.jsonl`.
- `ReasoningBank.get_relevant_context()` lấy recent entries, tính similarity bằng embedding nếu có, fallback keyword/Jaccard nếu không có, boost entry `success=True` rồi trả top N.
- `ReasoningBank.update_entry_outcome()` cập nhật success/reward/trade_id/reward_signal/near_miss/reward_notes rồi rewrite JSONL agent file.
- `ReasoningBank.extract_success_patterns()` và `synthesize_strategies()` tạo insight từ success/fail, confidence bucket, action distribution, latency pattern.
- `get_reasoning_bank()` tắt embedding mặc định (`use_embeddings=False`) để tránh memory issue, dùng Jaccard fallback.
- `src/memory/reasoning_bank_optimized.py` thay JSONL rewrite bằng SQLite table `reasoning_entries`, có index `idx_agent`, `idx_digest`, `idx_created`, `idx_agent_created`.
- `src/core/langgraph_orchestrator.py` có `get_agent_context_from_bank()` tạo text `### Historical Context (similar past decisions):`, và `store_agent_decision()` lưu decision vào bank.
- `src/trading/engine.py` cập nhật outcome khi order execute success/fail bằng digest `_reasoning_digest` hoặc `reasoning_prompt_digest`.
- `src/analysis/auto_evaluator.py` đánh giá pending entries bằng Binance 1m klines sau horizon, tính success theo BUY/SELL/HOLD và update outcome.

## Cách Reasoning Bank hoạt động

### 1. Data model

FenixAI dùng entry dạng kinh nghiệm agent:

- Identity: `agent`, `prompt_digest`, `created_at`.
- Input/output: `prompt`, `reasoning`, `action`, `confidence`, `raw_response` gián tiếp qua reasoning fallback.
- Runtime metadata: `backend`, `latency_ms`, `metadata`.
- Retrieval: `embedding` tùy chọn; nếu không có embedding thì keyword overlap/Jaccard.
- Outcome: `success`, `reward`, `reward_signal`, `near_miss`, `evaluated_at`, `trade_id`, `reward_notes`.
- Judge: `judge_verdict`, `judge_score`, `judge_confidence`, `judge_notes`, `judge_tags`, `judge_metadata`, `judge_success_estimate`, `judged_at`.

Điểm đáng chú ý: entry không chỉ là log. Nó là unit học kinh nghiệm vì có đủ decision trace + outcome + feedback.

### 2. Storage

Có 2 implementation:

1. JSONL default trong `src/memory/reasoning_bank.py`
   - Thư mục mặc định: `logs/reasoning_bank`.
   - Mỗi agent có một file `{agent}.jsonl`.
   - `index.json` lưu stats tổng quát.
   - Insert append nhanh, nhưng update outcome phải rewrite file agent.

2. SQLite optimized trong `src/memory/reasoning_bank_optimized.py`
   - DB: `logs/reasoning_bank/reasoning_bank.db`.
   - Table: `reasoning_entries`.
   - Index: `agent`, `prompt_digest`, `created_at`, `(agent, created_at)`.
   - Insert/update/query ổn hơn cho production.

### 3. Write path

Luồng ghi chính:

1. Agent trong `langgraph_orchestrator.py` tạo prompt và gọi LLM.
2. Response được validate và normalize.
3. `store_agent_decision()` gọi `reasoning_bank.store_entry()`.
4. Bank tạo `prompt_digest`, extract `action`, `confidence`, `reasoning`.
5. Entry được append vào storage.
6. Digest được trả về để gắn vào decision/order lifecycle.

FenixAI lưu reasoning cho nhiều agent: technical, sentiment, visual, QABBA, decision, risk manager.

### 4. Read/retrieval path

Luồng đọc chính:

1. Agent chuẩn bị prompt mới.
2. `get_agent_context_from_bank()` gọi `get_relevant_context(agent_name, current_prompt)`.
3. Bank lấy recent entries của agent.
4. Tính similarity:
   - Nếu có embedding: cosine similarity.
   - Nếu không: keyword overlap/Jaccard.
5. Lọc theo `min_similarity`.
6. Boost entry thành công (`success=True`) nếu `prefer_successful=True`.
7. Trả về context text gồm action, success/fail marker, confidence, reasoning snippet.
8. Context được inject vào prompt tiếp theo.

### 5. Scoring/ranking

Ranking trong bản chính:

- `score = entry.similarity_score(current_prompt, current_embedding)`.
- Nếu entry thành công và `prefer_successful=True`, `score *= 1.5`.
- Sort giảm dần, lấy top N.

Điểm yếu thấy được:

- Nếu embedding disabled, Jaccard trên prompt thô khá nông.
- Không có filter mạnh theo symbol/timeframe/regime trong core ranking.
- Context truncation cứng `reasoning[:100]` có thể mất evidence quan trọng.

### 6. Lifecycle update sau trade

Có 3 đường cập nhật outcome:

1. `TradeMemory.save_trade()` trong `trade_memory.py`
   - Lưu trade vào `logs/trade_memory.json`.
   - Tìm recent entries theo agent.
   - Gắn success/reward/trade_id/reward_signal/near_miss.

2. `TradingEngine` trong `trading/engine.py`
   - Khi order success: update reasoning digest thành `success=True`, reward `0.0`, attach order id.
   - Khi order fail: update `success=False`, reward `0.0`.

3. `AutoEvaluator` trong `analysis/auto_evaluator.py`
   - Sau horizon, lấy Binance klines.
   - BUY thành công nếu price change > 0.05%.
   - SELL thành công nếu price change < -0.05%.
   - HOLD thành công nếu biến động nhỏ.
   - Update success/reward/reward_notes.

### 7. Judge feedback

`ReasoningLLMJudge` tạo đánh giá độc lập cho reasoning:

- Input: agent name, prompt, normalized result, raw response, backend, metadata, latency.
- Output strict JSON: verdict approve/reject/inconclusive, score, confidence, critique, risks, improvements, tags, success_estimate.
- `attach_judge_feedback()` lưu verdict vào entry.

Đây là phần hữu ích cho Aureus Telegram insight vì có thể tách “agent nói gì” khỏi “judge đánh giá reasoning đó ra sao”.

### 8. Dependencies/external services/env

FenixAI liên quan:

- `sentence-transformers` tùy chọn cho embedding; default singleton tắt embedding để tránh memory issue.
- LangGraph/LangChain cho orchestrator.
- LLM provider config trong `config/fenix.yaml`, `config/llm_providers.yaml`, `.env.example`.
- Binance public klines trong `AutoEvaluator`.
- Runtime logs local trong `logs/`.

Không ghi secrets trong report. Chỉ ghi tên nhóm env/config, không copy values.

## Mapping sang Aureus

### Khái niệm FenixAI → Aureus

| FenixAI | Aureus tương ứng | Nhận xét |
|---|---|---|
| Agent reasoning entry | Strategy evaluation intelligence | Aureus cần lưu evaluation rationale theo `trace_id`, strategy id, signal snapshot. |
| `prompt_digest` | `trace_id` + deterministic decision digest | Aureus đã có trace_id trong journal/order lifecycle; nên dùng trace_id làm khóa chính nghiệp vụ. |
| `action/confidence/reasoning` | Strategy match, signal confidence, Telegram reasoning | Fit với signal pipeline và insight delivery. |
| `success/reward/trade_id` | Journal order lifecycle, entry/exit/PnL | Aureus có lifecycle MT5/order DB tốt hơn FenixAI; nên link outcome từ journal. |
| `get_relevant_context()` | Strategy evaluator retrieval context | Có thể dùng sau, nhưng không đặt trong path gửi order ban đầu. |
| `ReasoningLLMJudge` | Telegram insight / offline evaluator | Hợp với milestone Telegram insight, giải thích vì sao trade tốt/xấu. |
| SQLite/JSONL local | Timescale/Postgres/Aureus DB | Aureus nên dùng DB chính, không JSONL runtime cho production. |

### Liên hệ STATE hiện tại

STATE nhấn mạnh v1.6 là `Strategy Evaluation & Insight Delivery`, gồm:

- Strategy scoring/report.
- Journal/order lifecycle.
- Signal pipeline.
- Telegram insight delivery.

Reasoning Bank phù hợp như “experience layer” nằm giữa journal lifecycle và strategy evaluation intelligence:

1. Signal pipeline tạo signal snapshot.
2. Strategy evaluation tạo decision/rationale.
3. Order lifecycle ghi actual execution/result/PnL.
4. Reasoning Bank lưu decision trace + outcome.
5. Telegram insight đọc Reasoning Bank để giải thích hiệu quả strategy theo ngữ cảnh.

## Phương án tích hợp đề xuất

### Đề xuất chính: DB-backed Reasoning Experience Store

Không copy JSONL/SQLite FenixAI. Dùng FenixAI làm reference pattern rồi thiết kế store riêng trong Aureus DB.

Bảng/khái niệm đề xuất cho plan sau:

- `aureus_reasoning_entries`
  - `id`
  - `trace_id`
  - `strategy_id` / `strategy_name`
  - `symbol`, `timeframe`, `direction`
  - `agent_type` hoặc `reasoning_source`
  - `prompt_digest` / `decision_digest`
  - `input_context_hash`
  - `reasoning_text`
  - `decision_action`
  - `confidence`
  - `signal_snapshot_id`
  - `journal_trade_id` / `order_ticket` / `pending_order_id`
  - `entry_time`, `exit_time`
  - `success`, `reward`, `pnl`, `pnl_pct`, `r_multiple`
  - `market_regime/tpo_shape/htf_trend` nếu đã có trong snapshot
  - `judge_score`, `judge_verdict`, `judge_notes`
  - `created_at`, `evaluated_at`

### Data flow đề xuất

1. **Write decision trace**
   - Sau khi strategy match có `trace_id`, ghi reasoning entry append-only.
   - Không chặn gửi lệnh MT5 nếu ghi reasoning fail; log và retry/outbox nếu cần.

2. **Link order lifecycle**
   - Khi ORDER_OPENED/ORDER_PENDING_PLACED/ORDER_FILLED có ticket/pending id, cập nhật link vào reasoning entry qua `trace_id`.

3. **Attach outcome**
   - Khi ORDER_CLOSED có PnL, cập nhật success/reward.
   - Reward nên dùng `R-multiple` hoặc normalized PnL thay vì raw money.

4. **Generate insight**
   - Offline evaluator hoặc Telegram insight đọc entries đã evaluated.
   - Tạo summary: strategy nào thắng/thua theo symbol/timeframe/regime/signal confluence.

5. **Retrieval later**
   - Chỉ sau khi data đủ, thêm retrieval vào strategy evaluation.
   - Bắt đầu bằng rule/filter deterministic: cùng symbol/timeframe/strategy/direction + similar TPO/trend/session.
   - Embedding/vector chỉ thêm nếu deterministic retrieval không đủ.

### Vì sao không nên copy thẳng

- FenixAI JSONL rewrite outcome không hợp production với order lifecycle nhiều event.
- Agent naming không nhất quán (`decision_agent`, `Decision Agent`, `technical_agent`, `technical_analyst`) dễ miss update.
- Retrieval fallback có bug/điểm yếu ở optimized version: `_calculate_similarity()` dùng `current_embedding` thay text khi không có embedding, làm keyword fallback không đúng ý.
- API server có endpoint reasoning đọc `AgentOutput` DB, trong khi core ReasoningBank lại đọc JSONL/SQLite riêng; source of truth bị tách.
- Aureus đã có trace_id/journal/signal snapshot nên nên lấy lifecycle DB làm nguồn sự thật.

## Rủi ro và tradeoff

| Rủi ro | Mức | Giảm thiểu |
|---|---:|---|
| Reasoning storage làm chậm order hot path | Cao | Ghi async/outbox, không block dispatch MT5. |
| Lưu prompt/raw context chứa secrets hoặc data nhạy cảm | Cao | Chỉ lưu normalized context, redact env/secrets/account info. |
| Retrieval sai làm bias strategy decision | Cao | Ban đầu dùng insight/offline, chưa inject vào live decision. |
| Reward raw PnL lệch theo lot/symbol | Trung bình | Dùng R-multiple, pct, normalized reward theo risk. |
| Data model trùng với journal/snapshot | Trung bình | Reasoning entry chỉ link tới source tables, không copy toàn bộ snapshot. |
| Embedding dependency nặng | Trung bình | Phase đầu dùng deterministic filters; embedding là phase riêng. |
| Judge LLM hallucination | Trung bình | Judge feedback là advisory, không tự động thay đổi strategy. |

## Kế hoạch triển khai sau này

### Phase 1: Research-to-schema plan

- Thiết kế schema DB `aureus_reasoning_entries` và migration.
- Xác định khóa liên kết với `trace_id`, journal trade, signal snapshot.
- Viết threat model riêng vì đây là trust boundary mới: LLM reasoning ↔ trading decision ↔ DB.

### Phase 2: Append-only capture

- Ghi reasoning entry sau strategy match/evaluation.
- Không retrieval, không ảnh hưởng live decision.
- Verify e2e với database theo rule project vì có DB change.

### Phase 3: Outcome linker

- Update reasoning entry khi order opened/filled/closed.
- Chuẩn hóa reward bằng R-multiple/PnL pct.
- Backfill một số trade gần nhất nếu có trace_id đủ.

### Phase 4: Telegram insight

- Telegram summary đọc Reasoning Bank:
  - Vì sao trade được vào.
  - Outcome có khớp reasoning ban đầu không.
  - Strategy/signal nào đang có win/loss pattern.

### Phase 5: Retrieval thử nghiệm offline

- Chạy backtest/replay retrieval context ngoài live execution.
- So sánh quyết định có/không có context.
- Chỉ nếu cải thiện rõ mới cân nhắc inject vào live evaluation.

## Không thực hiện trong quick task này

- Không sửa source Aureus.
- Không thêm migration/database table.
- Không chạy code FenixAI_tradingBot.
- Không copy implementation FenixAI vào Aureus.
- Không cấu hình LLM/API key.
- Không bật embedding/vector search.
- Không thay đổi signal pipeline, journal lifecycle, Telegram handler.

## Verify đã chạy

- Clone/xác nhận repo: `test -d D:/Aureus/stable/FenixAI_tradingBot/.git && git -C D:/Aureus/stable/FenixAI_tradingBot remote get-url origin`.
- Phân tích source bằng đọc file trực tiếp và search keyword local.
- Không chạy code repo bên thứ ba.

## Kết luận tích hợp

Reasoning Bank đáng tích hợp vào Aureus, nhưng nên tích hợp như `Reasoning Experience Store` dựa trên DB và trace_id, không copy JSONL module từ FenixAI. Lợi ích lớn nhất cho Aureus là đóng vòng `strategy evaluation → order lifecycle → outcome → Telegram insight`, rồi sau đó mới dùng retrieval để cải thiện decision quality.