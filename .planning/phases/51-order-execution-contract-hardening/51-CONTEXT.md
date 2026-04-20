# Phase 51: order-execution-contract-hardening - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning
**Mode:** Fallback context (discuss retry)

<domain>
## Phase Boundary

Khóa chặt execution boundary cho ORDER_OPEN (market + pending) để loại reject sai, đồng thời đảm bảo PH45-07 rollback gate được đóng trên runtime path thực tế.

</domain>

<decisions>
## Implementation Decisions

### Execution Contract Boundary
- **D-01:** Ưu tiên contract-first validation tại execution consume boundary (không chấp nhận fallback payload mơ hồ).
- **D-02:** Market và pending phải đi chung một chuẩn payload parsing/normalization để tránh reject lệch nhánh.
- **D-03:** Idempotency và symbol routing phải giữ strict behavior đã chuẩn hóa ở phase 49.

### Runtime Rollback Gate (PH45-07)
- **D-04:** Rollout/rollback gate phải được chứng minh trên runtime path (không chỉ unit isolation).
- **D-05:** Guardrail per-symbol rollback được giữ nguyên, không dùng global rollback.

### Claude's Discretion
- Cách tách task theo file/service cụ thể trong plan.
- Mức độ mở rộng test matrix miễn giữ đúng requirement ORDER-01..03, PH45-07.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements
- `.planning/ROADMAP.md` — Phase 51 goal, depends_on, gap-closure boundary.
- `.planning/REQUIREMENTS.md` — ORDER-01, ORDER-02, ORDER-03, PH45-07 definitions và guardrails.

### Upstream runtime contracts
- `.planning/phases/45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-/45-CONTEXT.md` — per-symbol rollback/SLO runtime constraints.
- `.planning/phases/49-order-execution-contract-multi-symbol/49-CONTEXT.md` — execution contract + multi-symbol path baseline để harden.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing ORDER_OPEN consume and execution mapping stack from phase 49 (contract baseline).
- Existing per-symbol runtime health/rollback path from phase 45.

### Established Patterns
- Contract-first validation tại service boundary.
- Requirement-level evidence via VERIFICATION.md + validation artifacts.

### Integration Points
- `orders.py -> execution_client.py`
- `bridge lifecycle publish`
- `multi-symbol streams -> _poll_loop`

</code_context>

<specifics>
## Specific Ideas

- Ưu tiên đóng reject sai trước, sau đó xác nhận rollback gate bằng evidence runtime.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 51-order-execution-contract-hardening*
*Context gathered: 2026-04-21*
