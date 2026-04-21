# Phase 55: Evaluation Data Model & Pipeline - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Thiết kế schema DB chuẩn hóa và pipeline ingestion/compute/persist cho evaluation records theo từng trade/strategy, bao gồm cơ chế backfill/recompute theo score_version và data quality guards (idempotency, uniqueness, null/constraint checks).

Phase này tập trung vào lớp dữ liệu và pipeline persist; không mở rộng sang reporting UI/engine hay Telegram insight delivery.

</domain>

<decisions>
## Implementation Decisions

### Data model strategy
- **D-01:** Ưu tiên tận dụng và mở rộng từ **Trade Execution Journal** hiện có thay vì tạo data model rời hoàn toàn mới.
- **D-02:** Evaluation schema phải thiết kế bám theo khóa/quan hệ hiện tại của Trade Execution Journal để giảm độ cầu kỳ migration và giữ traceability theo vòng đời lệnh.

### Versioning & recompute
- **D-03:** Chính sách versioning/recompute sẽ được khóa dựa trên cấu trúc thực tế của Trade Execution Journal (trade identity, lifecycle fields, timestamps) trước khi chốt DDL chi tiết.
- **D-04:** Recompute phải giữ được lịch sử version phục vụ truy vết, nhưng cách biểu diễn (append/version rows vs extension pattern) phải tương thích với Journal schema hiện hữu.

### Idempotency & uniqueness
- **D-05:** Guardrails idempotency/uniqueness cho evaluation pipeline phải dựa trên khóa tự nhiên và ràng buộc đã có trong Trade Execution Journal.
- **D-06:** Tránh tạo cơ chế idempotency tách rời không map được về Journal records; mọi chống duplicate phải truy hồi được về execution journal lineage.

### Pipeline trigger & boundary
- **D-07:** Điểm trigger persist evaluation bắt đầu **sau khi gửi lệnh lên MT5 thành công**.
- **D-08:** Pipeline phải ghi nhận evaluation data vào DB từ thời điểm lệnh được xác nhận thành công, rồi tiếp tục cập nhật/bổ sung theo lifecycle dữ liệu liên quan nếu cần.

### Claude's Discretion
- Cách cụ thể để map Trade Execution Journal fields sang evaluation schema trung gian/final.
- Cấu trúc migration chi tiết (naming/indexing/constraint expression) miễn tuân thủ các quyết định D-01→D-08.
- Cơ chế orchestration cho recompute jobs (batch windowing/chunking) miễn không phá vỡ traceability với Journal.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and requirements
- `.planning/ROADMAP.md` — Định nghĩa goal/success criteria Phase 55 (EVAL-01→04).
- `.planning/REQUIREMENTS.md` — Requirements chính thức cho data model & pipeline (EVAL-01→04).
- `.planning/PROJECT.md` — Boundary milestone v1.6 và định hướng ưu tiên evaluation intelligence.

### Upstream scoring context (phase 54)
- `.planning/phases/54-strategy-scoring-framework/54-CONTEXT.md` — Quyết định D-13 về temporary persistence contract và handoff sang Phase 55.
- `services/aureus-signal/engine/strategy_executor.py` — Điểm phát scoring metadata hiện tại cần map sang persistence pipeline.
- `services/aureus-signal/engine/scoring/compute.py` — Contract scoring output fields cần được persist.
- `services/aureus-signal/engine/scoring/aggregate.py` — Aggregate semantics strategy/symbol/timeframe làm đầu vào cho mô hình evaluation.

### Execution journal baseline
- `.planning/milestones/v1.5-phases/37-trade-execution-journal/PLAN.md` — Thiết kế baseline Trade Execution Journal cần được tái sử dụng/mở rộng.
- `.planning/milestones/v1.5-phases/37-trade-execution-journal/PLAN-SUMMARY.md` — Tóm tắt cấu trúc và boundary của execution journal phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/aureus-signal/engine/strategy_executor.py`: đã có scoring contract fields (`score_total`, `score_breakdown`, `score_version`, `weights_snapshot`, `missing_data_policy`) để làm input persist.
- `services/aureus-signal/engine/scoring/compute.py`: output scoring deterministic, phù hợp làm payload chuẩn cho evaluation record.
- `services/aureus-signal/engine/scoring/aggregate.py`: có group key strategy/symbol/timeframe hỗ trợ aggregate lineage.

### Established Patterns
- Phase 54 đã cố tình giữ persistence ở mức temporary contract trong executor; Phase 55 là nơi chuyển sang DB schema chính thức.
- Runtime hiện tại đi theo flow signal/strategy executor trước, rồi mới sang lớp persistence/reporting downstream.

### Integration Points
- Điểm tích hợp chính: flow sau khi order MT5 gửi thành công (theo quyết định user) để bắt đầu ghi evaluation.
- Điểm tích hợp dữ liệu: map execution journal identity/lifecycle sang evaluation records để đảm bảo traceability một-trade-xuyên-suốt.

</code_context>

<specifics>
## Specific Ideas

- User định hướng rõ: không muốn thiết kế schema/pipeline quá cầu kỳ tách rời; ưu tiên mở rộng từ Trade Execution Journal hiện có.
- User muốn trigger lưu DB diễn ra từ mốc order gửi MT5 thành công.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 55-evaluation-data-model-pipeline*
*Context gathered: 2026-04-21*
