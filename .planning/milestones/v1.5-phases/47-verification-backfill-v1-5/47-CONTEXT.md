# Phase 47: verification-backfill-v1-5 - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Bổ sung verification artifacts còn thiếu cho các phase v1.5 đang orphan requirement, chuẩn hoá evidence theo requirement-level để milestone audit có thể chứng minh trạng thái thực thi bằng bằng chứng nhất quán.

Phạm vi phase này là **verification backfill** (artifact + traceability), không mở rộng sang sửa logic sản phẩm/runtime mới (các gap tích hợp kỹ thuật được xử lý ở phase 48/49).

</domain>

<decisions>
## Implementation Decisions

### Verification Backfill Scope
- **D-01:** Backfill verification cho đúng các phase thiếu artifact theo audit: **26, 28, 29, 31, 32, 33**.
- **D-02:** Mỗi phase backfill phải có 1 file `{phase}-VERIFICATION.md` theo format verifier hiện hành (frontmatter + Goal Achievement + Requirements Coverage + Gaps/Human Needed nếu có).
- **D-03:** Không “tuyên bố complete” bằng SUMMARY-only; requirement chỉ được coi là closed khi có evidence trong VERIFICATION.

### Requirement-level Evidence Policy
- **D-04:** Với mỗi requirement mục tiêu của phase 47 (NOTIF-01, STRAT-01..04, ORDER-04..07, TRADE-03..04), verification bắt buộc map theo bảng `Requirement | Status | Evidence` với tham chiếu file/test/command cụ thể.
- **D-05:** Evidence ưu tiên 3 lớp: (1) artifact/code-path, (2) test/command output, (3) flow/key-link wiring; thiếu lớp nào phải ghi rõ mức độ confidence.
- **D-06:** Nếu có điểm chưa thể auto-verify (môi trường live/manual), trạng thái phải là `human_needed` thay vì `passed`.

### Traceability & Audit Consistency
- **D-07:** Sau khi backfill, REQUIREMENTS traceability phải đồng bộ trạng thái từ Pending/Orphaned sang trạng thái đã có chứng cứ verification.
- **D-08:** `v1.5-MILESTONE-AUDIT.md` là baseline gap list để đối chiếu đóng gap; không tự mở rộng scope requirement ngoài danh sách audit hiện tại.
- **D-09:** Mọi kết luận phải nhất quán với Nyquist gate (không bypass VALIDATION/VERIFICATION contract).

### Scope Guardrails
- **D-10:** Không sửa runtime/business logic ở phase 47 trừ khi bắt buộc để khôi phục khả năng verify (nếu phát hiện blocker kỹ thuật thì ghi gap chuyển phase 48/49).
- **D-11:** Integration gaps đã audit (backtest API wiring, qty contract, multi-symbol hardcode) được giữ nguyên deferred sang phase đã map (48/49), chỉ link chéo trong verification nếu liên quan.

### Claude's Discretion
- Thứ tự ưu tiên backfill giữa các phase 26/28/29/31/32/33 để tối ưu tốc độ đóng orphan count.
- Mức chi tiết narrative trong phần Goal Achievement miễn vẫn đủ bằng chứng truy vết requirement-level.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone contract & gap baseline
- `.planning/ROADMAP.md` — Định nghĩa Phase 47 (goal, requirements, dependency, gap-closure intent).
- `.planning/REQUIREMENTS.md` — Requirement IDs cần đóng orphan và bảng traceability milestone v1.5.
- `.planning/v1.5-MILESTONE-AUDIT.md` — Nguồn gap chính thức: orphan requirements, integration gaps, flow breaks, nyquist coverage.
- `.planning/PROJECT.md` — Milestone objective và boundary v1.5 để giữ scope verification-only.

### Existing verification quality bar (reference format)
- `.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-VERIFICATION.md` — Mẫu verification đầy đủ (frontmatter + truth table + requirement coverage + key links).
- `.planning/phases/44-profiling-baseline-performance/44-VERIFICATION.md` — Mẫu status `human_needed` và cách ghi manual gate bắt buộc.
- `.planning/phases/35-mt5-order-status-reporter/35-VERIFICATION.md` — Mẫu checklist requirement → location mapping ngắn gọn.
- `.planning/phases/40-signal-classification-indicator-event-based/40-VERIFICATION.md` — Mẫu tổng hợp wave-level verification + critical checks.

### Source artifacts to be backfilled
- `.planning/phases/26-signal-event-pipeline-strategy-contract/26-01-SUMMARY.md`
- `.planning/phases/26-signal-event-pipeline-strategy-contract/26-01-PLAN.md`
- `.planning/phases/26-signal-event-pipeline-strategy-contract/26-VALIDATION.md`
- `.planning/phases/28-aureusprovider-mq5-bidirectional-extension/28-01-SUMMARY.md`
- `.planning/phases/28-aureusprovider-mq5-bidirectional-extension/28-01-PLAN.md`
- `.planning/phases/29-mt5-order-execution-service/29-01-SUMMARY.md`
- `.planning/phases/29-mt5-order-execution-service/29-01-PLAN.md`
- `.planning/phases/31-mt5-history-sync/31-01-SUMMARY.md`
- `.planning/phases/31-mt5-history-sync/31-01-PLAN.md`
- `.planning/phases/31-mt5-history-sync/31-VALIDATION.md`
- `.planning/phases/32-trade-performance-api/32-01-SUMMARY.md`
- `.planning/phases/32-trade-performance-api/32-PLAN.md`
- `.planning/phases/33-performance-dashboard-ui/33-01-SUMMARY.md`
- `.planning/phases/33-performance-dashboard-ui/33-01-PLAN.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Hệ thống đã có nhiều SUMMARY/UAT/VALIDATION từ các phase mục tiêu, đủ làm nguồn evidence backfill mà không cần tái-implement tính năng.
- Các phase 28/29/31/32/33 đã ghi dependency graph + key-files + metrics khá rõ trong SUMMARY frontmatter, hỗ trợ dựng bảng requirement coverage nhanh.

### Established Patterns
- Milestone gần đây dùng `*-VERIFICATION.md` làm nguồn sự thật cuối cùng để pass gate (không dùng SUMMARY thay thế).
- Status verification phân tầng rõ: `passed`, `human_needed`, `gaps_found`.
- Bằng chứng thường theo pipeline: artifact existence → key-link wiring → behavioral checks/tests.

### Integration Points
- Kết quả backfill của phase 47 sẽ feed trực tiếp vào:
  - cập nhật traceability trong `.planning/REQUIREMENTS.md`
  - re-audit ở phase 50 (`nyquist-reaudit-closure`)
  - giảm orphan list trong `.planning/v1.5-MILESTONE-AUDIT.md`

</code_context>

<specifics>
## Specific Ideas

- Ưu tiên “evidence-first”: viết verification để chứng minh cái đã làm, không viết lại lịch sử theo claim.
- Chuẩn hóa từ ngữ status giữa các phase để tooling audit đọc nhất quán (đặc biệt orphan → satisfied transition).

</specifics>

<deferred>
## Deferred Ideas

- Sửa các integration gap kỹ thuật runtime (backtest API route mismatch, qty contract mismatch, hardcode XAUUSD consumer) — defer sang Phase 48/49 theo roadmap.
- Nyquist missing/partial closure và milestone re-audit cuối — defer sang Phase 50.

### Reviewed Todos (not folded)
- `2026-03-28-remove-market-regime-use-htf-trend.md` — không thuộc verification backfill scope.
- `2026-03-28-investigate-sweep-triggers-after-broken-pending.md` — thuộc điều tra logic signal, không phải requirement verification backfill.

</deferred>

---

*Phase: 47-verification-backfill-v1-5*
*Context gathered: 2026-04-20*