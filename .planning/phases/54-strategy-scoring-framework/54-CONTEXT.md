# Phase 54: Strategy Scoring Framework - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Chốt scoring framework đa tiêu chí cho strategy và chạy được end-to-end trước các phần mở rộng khác, bao gồm: công thức scoring rõ ràng theo các trụ (profit outcome, signal quality, timing quality, volatility/session context), hỗ trợ trọng số theo version để tái lập kết quả, tính ở cả per-trade và aggregate level, và persist breakdown từng tiêu chí để audit/giải thích.

Không mở rộng sang reporting engine đầy đủ hay Telegram delivery ở phase này.

</domain>

<decisions>
## Implementation Decisions

### Scoring Architecture
- **D-01:** Sử dụng kiến trúc **two-stage**: Stage 1 là quality gate, Stage 2 là weighted-sum scoring.
- **D-02:** Stage 2 áp dụng weighted-sum tuyến tính cho 4 trụ: profit outcome, signal quality, timing quality, volatility/session context.
- **D-03:** Quality gate là bắt buộc để loại các trade không đạt ngưỡng chất lượng tối thiểu trước khi vào tính điểm tổng hợp.

### Versioning & Reproducibility
- **D-04:** Dùng **semantic score_version** làm định danh version chính.
- **D-05:** Mỗi score_version phải đi kèm **immutable weights snapshot** để đảm bảo tái lập kết quả tuyệt đối.
- **D-06:** Bất kỳ thay đổi công thức/trọng số nào đều tạo version mới, không overwrite version cũ.

### Score Granularity
- **D-07:** Tính score ở cấp **per-trade** và **aggregate**.
- **D-08:** Aggregate level khóa theo bộ chiều: **strategy / symbol / timeframe**.

### Breakdown Persistence
- **D-09:** Persist breakdown theo định dạng **JSON breakdown** cho từng criterion, kèm normalization metadata.
- **D-10:** Bắt buộc có **missing-data policy explicit** trong payload để không mơ hồ khi criterion bị thiếu dữ liệu.
- **D-11:** Persist đầy đủ các trường phục vụ audit gồm score_total, score_breakdown, score_version và metadata liên quan normalization/weight snapshot.

### Claude's Discretion
- Thiết kế chi tiết công thức normalize cho từng criterion miễn vẫn tuân thủ contract versioning + breakdown đã khóa.
- Thiết kế mức precision (rounding/decimal) cụ thể miễn nhất quán và truy vết được.

### Folded Todos
- **Investigate missing OB events in signal_history_normalized** (todo: `2026-03-28-investigate-sweep-triggers-after-broken-pending.md`)
  - Vấn đề gốc: thiếu OB events trong normalized signal history.
  - Cách fold vào phase 54: được xem như ràng buộc chất lượng đầu vào cho trụ signal quality và quality gate, nhằm tránh scoring sai do dữ liệu tín hiệu thiếu.
- **Remove market_regime use htf_trend** (todo: `2026-03-28-remove-market-regime-use-htf-trend.md`)
  - Vấn đề gốc: logic market_regime hiện phụ thuộc htf_trend cần tách/điều chỉnh.
  - Cách fold vào phase 54: được xem như ràng buộc định nghĩa criterion volatility/session context để tránh trùng lặp hoặc méo nghĩa giữa regime và trend trong scoring framework.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and acceptance
- `.planning/ROADMAP.md` — Định nghĩa goal/success criteria của Phase 54 (SCOR-01→04, ACC-01).
- `.planning/REQUIREMENTS.md` — Requirements chính thức cho Scoring Framework (SCOR-01→04, ACC-01).
- `.planning/PROJECT.md` — Milestone objective v1.6 và boundary tổng thể.

### Existing scoring-related implementation context
- `services/aureus-signal/engine/strategies/template.py` — Mẫu scoring hiện có (min_score_threshold, sequence weights, context filters).
- `services/aureus-signal/engine/strategies/seed_strategies.py` — Seed strategy configs với trọng số/ngưỡng hiện hành.
- `services/aureus-signal/engine/strategy_executor.py` — Luồng strategy evaluation hiện tại, metadata enrichment và publish path.
- `services/aureus-dashboard/api/main.py` — Bối cảnh aggregate/performance API và fields breakdown liên quan (`algo_score`, `algo_breakdown`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TemplateStrategy` (`services/aureus-signal/engine/strategies/template.py`): đã có nền tảng sequence weight + min_score_threshold, phù hợp làm base cho Stage-2 weighted-sum.
- `seed_system_strategies` (`services/aureus-signal/engine/strategies/seed_strategies.py`): đã có config strategy với weights/threshold có thể map sang weight snapshot versioned.
- `strategy_executor` pipeline (`services/aureus-signal/engine/strategy_executor.py`): có sẵn đường dữ liệu để enrich metadata và phát hành kết quả đánh giá.
- Dashboard API fields `algo_score`/`algo_breakdown` (`services/aureus-dashboard/api/main.py`): pattern có thể tái sử dụng cho contract breakdown persistence.

### Established Patterns
- Python async services + Redis stream + asyncpg là pattern chuẩn cho ingestion/evaluation path.
- Cấu hình strategy theo JSON config và score threshold đã hiện diện; phase 54 nên mở rộng từ pattern này thay vì tạo cơ chế song song mới.

### Integration Points
- Điểm tích hợp chính nằm ở `aureus-signal` (strategy evaluation path) để tính và gắn score/per-trade breakdown.
- Điểm tích hợp downstream nằm ở lớp persist/query (Timescale/Postgres + dashboard API) để expose aggregate theo strategy/symbol/timeframe.

</code_context>

<specifics>
## Specific Ideas

- Yêu cầu explicit: đánh giá theo hướng kiến trúc độc lập, có phân tích neutral → trade-off → contextual recommendation → adversarial check trước khi khóa quyết định.
- Chốt kiến trúc ưu tiên tính auditability, traceability và khả năng tái lập kết quả hơn việc tối ưu thuật toán phức tạp ngay trong phase 54.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 54-strategy-scoring-framework*
*Context gathered: 2026-04-21*