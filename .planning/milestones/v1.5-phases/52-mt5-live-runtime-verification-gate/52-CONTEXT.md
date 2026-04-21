# Phase 52: mt5-live-runtime-verification-gate - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning
**Mode:** Fallback context (discuss retry)

<domain>
## Phase Boundary

Thực hiện human verification gate trên MT5 live runtime cho ORDER-04..06 và TRADE-03..04, tạo evidence end-to-end đủ điều kiện xác nhận runtime contracts.

</domain>

<decisions>
## Implementation Decisions

### Live Verification Scope
- **D-01:** Verification phải bao phủ ORDER-04, ORDER-05, ORDER-06 và TRADE-03, TRADE-04 với bằng chứng runtime thực tế.
- **D-02:** Ưu tiên evidence có khả năng truy vết xuyên luồng (command → MT5 execution/event → trade history reconciliation).

### Human Gate Protocol
- **D-03:** Các check mang tính live runtime được phân loại `human_needed` và phải có checklist rõ để user xác nhận.
- **D-04:** Nếu có thiếu evidence, phải ghi rõ gap thay vì đánh passed giả định.

### Claude's Discretion
- Chọn cụm test command và format checklist phù hợp hạ tầng hiện tại.
- Tổ chức artifact verification sao cho dùng lại được cho re-audit phase 53.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements
- `.planning/ROADMAP.md` — Phase 52 scope và flow gap cần đóng.
- `.planning/REQUIREMENTS.md` — ORDER-04..06, TRADE-03..04 requirement definitions.

### Upstream implementation baseline
- `.planning/phases/28-aureusprovider-mq5-bidirectional-extension/28-VERIFICATION.md` — MT5 command/event contract baseline.
- `.planning/phases/31-mt5-history-sync/31-VERIFICATION.md` — reconciliation + history sync baseline.
- `.planning/phases/51-order-execution-contract-hardening/51-VERIFICATION.md` — hardening output làm đầu vào live gate.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing MT5 gateway command/event pipeline.
- Existing reconciliation loop and verification conventions from prior phases.

### Established Patterns
- Verification status routing: passed / human_needed / gaps_found.
- Requirement-level evidence linking in verification artifacts.

### Integration Points
- MT5 order events stream.
- Trade history reconciliation path.
- Verification docs consumed by audit/re-audit.

</code_context>

<specifics>
## Specific Ideas

- Tập trung chứng minh runtime end-to-end thay vì chỉ unit test coverage.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 52-mt5-live-runtime-verification-gate*
*Context gathered: 2026-04-21*
