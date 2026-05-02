---
phase: quick-260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md
autonomous: true
requirements:
  - ANTI-LACK-01
  - ANTI-LACK-02
  - ANTI-LACK-03
must_haves:
  truths:
    - "Executor sau có checklist đủ chi tiết để không làm thiếu behavior cũ khi triển khai strategy-aware position management."
    - "Mỗi behavior/rule cũ được map sang primitive, profile áp dụng, và verification checklist."
    - "Implementation chỉ được coi là complete khi mọi checklist item được check hoặc deferred có rationale."
  artifacts:
    - path: "D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md"
      provides: "Detailed anti-lack implementation checklist and coverage matrix"
      contains: "Anti-lack gate"
  key_links:
    - from: "260501-kcz-IMPLEMENTATION-CHECKLIST.md"
      to: "D:/Aureus/mql5/AureusProvider_v2.mq5"
      via: "function-level checklist references current provider management functions"
      pattern: "ProcessPositionsByType"
    - from: "260501-kcz-IMPLEMENTATION-CHECKLIST.md"
      to: "D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5"
      via: "old behavior coverage matrix references reference EA rules"
      pattern: "Old behavior/rule coverage matrix"
---

<objective>
Tạo một artifact checklist triển khai chi tiết để tránh tình trạng plan có nhưng execution chỉ làm được một phần.

Purpose: Biến yêu cầu strategy-aware position management thành checklist kiểm kê đầy đủ behavior cũ, primitive, profile composition, verification, và anti-lack gate để executor sau không bỏ sót rule.
Output: `D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-PLAN.md
@D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-SUMMARY.md
@D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-VERIFICATION.md
@D:/Aureus/mql5/AureusProvider_v2.mq5
@D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5

<interfaces>
Key source functions for checklist coverage:

```mql5
string ResolveManagementProfile(long magic, bool &fallback_used);
void LogManagementDecision(string symbol, long magic, string direction, string profile, string action, string reason, int positions_count, double net_profit, int age_seconds, ulong ticket = 0, double target_sl = 0);
void ProcessPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time);
void ManagePositionProfitBreakEvent();
```

Reference old EA functions to decompose:

```mql5
void ManagePositionProfitBreakEvent();
void ProcessPositionsByType(ENUM_POSITION_TYPE target_type, const long &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time);
void ManagePositionByHistory();
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Produce anti-lack implementation checklist artifact</name>
  <files>D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md</files>
  <action>Create a markdown checklist artifact only; do not modify any MQL5 source and do not touch database files. The artifact must explain why quick 260501-i1p was vulnerable to partial execution; decompose existing management logic into scope/grouping, state aggregation, risk/exit guards, protective management, and post-action side effects; define rule primitives; include an explicit coverage matrix mapping old behavior/rule -> primitive -> conservative/trend_runner/breakout_protect/basket_escape -> verification checklist; include per-profile strategy checklists; include function-level implementation checklist for resolver/logging/grouping/processing/non-regression functions; include pass/fail verification checklist; include an anti-lack gate stating implementation is incomplete unless every checklist item is checked or explicitly deferred with rationale.</action>
  <verify>
    <automated>test -f "D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md" && grep -q "Old behavior/rule coverage matrix" "D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md" && grep -q "Anti-lack gate" "D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md"</automated>
  </verify>
  <done>Checklist artifact exists and contains why previous execution was incomplete, decomposition, primitive list, old behavior coverage matrix, per-profile checklists, function-level checklist, verification checklist, and anti-lack gate.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Planning artifact -> later executor | Checklist text controls what a future code executor treats as complete. |
| Old EA behavior -> provider implementation | Incorrect mapping can silently drop trading risk management behavior. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260501-kcz-01 | Tampering | Coverage matrix | mitigate | Require every old behavior to be marked KEPT/CHANGED/DEFERRED with rationale before completion. |
| T-260501-kcz-02 | Repudiation | Future summary/verification | mitigate | Require pass/fail checklist and explicit deferred rationale; no blank checklist items accepted. |
| T-260501-kcz-03 | Denial of service | Overbroad plan scope | mitigate | This task is documentation/planning only and must not modify MQL5 source or database files. |
</threat_model>

<verification>
- The checklist artifact exists at the expected quick directory path.
- It includes an explicit old behavior/rule coverage matrix.
- It includes per-profile checklists for conservative, trend_runner, breakout_protect, basket_escape.
- It includes pass/fail acceptance and anti-lack gate.
- No MQL5 source or database files are modified by this quick task.
</verification>

<success_criteria>
- `D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md` is concrete enough for a later executor to implement without losing old function/rule behavior.
- The artifact includes: why previous execution was incomplete, required decomposition, rule primitives, profile composition, function-level checklist, verification checklist, and anti-lack gate.
- The anti-lack gate requires every checklist item to be checked or explicitly deferred with rationale.
- No database changes and no MQL5 source changes are included in this quick task.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-SUMMARY.md` if this plan is executed by `/gsd-execute-phase`.
</output>
