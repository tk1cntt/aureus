---
phase: quick-260427-wwv-validate-and-fix-trend-cont-limit-bull-a
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/strategies/seed_strategies.py
  - services/aureus-signal/engine/orders.py
autonomous: true
requirements:
  - QUICK-260427-WWV
must_haves:
  truths:
    - "TREND_CONT_LIMIT_BULL và TREND_CONT_LIMIT_BEAR tồn tại trong seed declarations với direction, entry_type, entry_method, SL/TP/trailing/size đầy đủ để runtime tạo order plan."
    - "Hai strategy LIMIT dùng ENTRY_PIVOT_LIMIT hợp lệ: BUY lấy LL dưới current, SELL lấy HH trên current, và không silently fallback sang CURRENT/MARKET."
    - "Sau khi seed runtime vào database, aureus_strategy_templates và aureus_symbol_strategies có đủ 2 strategy active cho symbol runtime."
    - "Nếu sửa code/data, executor chứng minh bằng test tự động và DB/E2E verification qua WSL/container theo RUN_SERVICES.md."
  artifacts:
    - path: "services/aureus-signal/engine/strategies/seed_strategies.py"
      provides: "Seed declarations cho TREND_CONT_LIMIT_BULL và TREND_CONT_LIMIT_BEAR"
      contains: "TREND_CONT_LIMIT_BULL"
    - path: "services/aureus-signal/engine/orders.py"
      provides: "Runtime validation/calculation cho ENTRY_PIVOT_LIMIT, PIVOT_POINT SL, RR TP"
      contains: "ENTRY_PIVOT_LIMIT"
    - path: "services/aureus-signal/engine/snapshot_utils.py"
      provides: "Allowed entry_method contract"
      contains: "VALID_ENTRY_METHODS"
  key_links:
    - from: "services/aureus-signal/engine/strategies/seed_strategies.py"
      to: "aureus_strategy_templates.config"
      via: "seed_system_strategies json.dumps(strat['config'])"
      pattern: "ENTRY_PIVOT_LIMIT"
    - from: "services/aureus-signal/engine/strategies/registry.py"
      to: "services/aureus-signal/engine/orders.py"
      via: "accepted trigger includes order_plan consumed by SimulatedTradeManager"
      pattern: "order_plan"
    - from: "services/aureus-signal/engine/orders.py"
      to: "services/aureus-signal/engine/snapshot_utils.py"
      via: "VALID_ENTRY_METHODS allows ENTRY_PIVOT_LIMIT"
      pattern: "VALID_ENTRY_METHODS"
---

<objective>
Kiểm tra và sửa đúng trọng tâm 2 seed strategy `TREND_CONT_LIMIT_BULL` và `TREND_CONT_LIMIT_BEAR` để đảm bảo logic khai báo khớp runtime order creation và đã seed đầy đủ vào DB.

Purpose: Tránh trạng thái strategy có trong code nhưng khi chạy thật bị reject do config thiếu/sai, entry_method không hợp lệ, SL/TP không tính được, hoặc chưa active trong DB.
Output: Seed declarations/runtime support được xác minh bằng test và DB/E2E verification; nếu có sửa thì commit kèm evidence.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-signal/engine/strategies/seed_strategies.py
@D:/Aureus/services/aureus-signal/engine/strategies/registry.py
@D:/Aureus/services/aureus-signal/engine/orders.py
@D:/Aureus/services/aureus-signal/engine/snapshot_utils.py

<interfaces>
Các contract quan trọng đã đọc trước khi lập plan:

From `services/aureus-signal/engine/snapshot_utils.py`:
```python
VALID_ENTRY_TYPES = ("MARKET", "LIMIT", "STOP")
VALID_SIZE_MODES = ("FIXED_UNITS", "FIXED_LOT", "RISK_PERCENT", "RISK_FIXED_AMOUNT")
VALID_ENTRY_METHODS = ("CURRENT", "PULLBACK_50", "OB_EDGE", "EMA_TOUCH", "FIXED_OFFSET", "ENTRY_PIVOT_LIMIT")
REQUIRED_ORDER_PLAN_KEYS = (
    "entry_type", "entry_method", "entry_value", "entry_policy",
    "sl_mode", "sl_value", "tp_mode", "tp_value",
    "trailing_mode", "trailing_value", "size_mode", "size_value", "expiry_policy",
)
```

From `services/aureus-signal/engine/orders.py`:
```python
def _calculate_entry_price(...):
    ...
    elif method == "ENTRY_PIVOT_LIMIT":
        return self._entry_pivot_limit(side, state_obj, current_price)

def _entry_pivot_limit(...):
    """BUY dùng LL chưa broken dưới current; SELL dùng HH chưa broken trên current."""
```

From `services/aureus-signal/engine/strategies/registry.py`:
```python
accepted.append({
    "entry_type": order_plan.get("entry_type", "MARKET"),
    "entry_policy": order_plan.get("entry_policy", "IMMEDIATE"),
    "sl": order_plan.get("sl"),
    "tp": order_plan.get("tp"),
    "trailing": order_plan.get("trailing"),
    "order_plan": order_plan,
})
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Audit two LIMIT trend seed declarations against runtime contracts</name>
  <files>services/aureus-signal/engine/strategies/seed_strategies.py, services/aureus-signal/engine/orders.py, services/aureus-signal/engine/snapshot_utils.py</files>
  <behavior>
    - Test/audit must assert both `TREND_CONT_LIMIT_BULL` and `TREND_CONT_LIMIT_BEAR` exist exactly once in `seed_system_strategies` seed list.
    - BULL must be `direction=BUY`, `entry_type=LIMIT`, `entry_method=ENTRY_PIVOT_LIMIT`, sequence contains required `choch_up`, early exit contains `choch_down`.
    - BEAR must be `direction=SELL`, `entry_type=LIMIT`, `entry_method=ENTRY_PIVOT_LIMIT`, sequence contains required `choch_down`, early exit contains `choch_up`.
    - Both must satisfy `VALID_ENTRY_TYPES`, `VALID_ENTRY_METHODS`, `VALID_SIZE_MODES`, and include enough execution config for `_build_order_plan_snapshot` plus later SL/TP enrichment: size, SL `PIVOT_POINT`, TP `RR_RATIO`, trailing, expiry default path.
  </behavior>
  <action>Run GitNexus exploration first if available (`gitnexus_query` for strategy seed/order plan flow) and run impact analysis before editing any symbol: `gitnexus_impact({target: "seed_system_strategies", direction: "upstream"})`; if editing `SimulatedTradeManager._build_order_plan_snapshot`, `_calculate_entry_price`, `_entry_pivot_limit`, or `_calculate_sl_tp`, run impact for each. Inspect only the two named strategies and required supporting contract code. Identify concrete mismatches, especially fields that cause `ORDER_PLAN_INCOMPLETE` (`entry_value`, `sl_value`, `tp_value`, `trailing_value`) or invalid runtime semantics. Do not broaden scope to other strategies unless a shared contract directly proves these two cannot run.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests -q -k 'strategy or order or seed'"</automated>
  </verify>
  <done>Executor reports the audit result with exact file/line evidence and GitNexus blast radius; either confirms no change needed or lists precise issues to fix in Task 2.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix only proven config/runtime gaps for the two strategies</name>
  <files>services/aureus-signal/engine/strategies/seed_strategies.py, services/aureus-signal/engine/orders.py</files>
  <behavior>
    - If seed config is missing fields required for accepted order-plan snapshots, tests must fail before fix and pass after fix.
    - `ENTRY_PIVOT_LIMIT` must remain a LIMIT entry method and must reject unavailable pivots instead of silently converting to market entry.
    - BUY LIMIT semantics must use a valid LL below current price; SELL LIMIT semantics must use a valid HH above current price.
    - SL/TP must remain computable for both strategies using PIVOT_POINT SL and RR_RATIO TP once valid pivots exist.
  </behavior>
  <action>If Task 1 finds issues, make surgical edits only. Likely acceptable fixes include adding explicit `entry_value` only if the runtime requires it as a non-empty contract field, normalizing missing snapshot values in `_build_order_plan_snapshot` only if needed for configs whose concrete values are later computed, or adjusting the two seed configs so they produce complete runtime order plans. Do not refactor registry/order flow, do not change unrelated strategy declarations, and do not add speculative fallback behavior. If no issue is proven, make no source changes and document why no fix is needed in the summary.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests -q -k 'entry_pivot_limit or order_plan or seed_strategies or strategy'"</automated>
  </verify>
  <done>Only the two strategy declarations and/or directly required runtime contract handling are changed; tests prove BULL/BEAR LIMIT configs create valid accepted order plans when required pivots exist and reject cleanly when pivots are absent.</done>
</task>

<task type="auto">
  <name>Task 3: Seed runtime DB and verify both strategies are active</name>
  <files>services/aureus-signal/engine/strategies/seed_strategies.py</files>
  <action>Because this touches database seeding/runtime strategy declarations, perform DB/E2E verification through WSL/container per RUN_SERVICES.md. First ensure services are up with docker compose ps. Run the seed inside the signal container. Query `aureus_strategy_templates` joined to `aureus_symbol_strategies` for only `TREND_CONT_LIMIT_BULL` and `TREND_CONT_LIMIT_BEAR`, confirming config JSON has `entry_type=LIMIT`, `entry_method=ENTRY_PIVOT_LIMIT`, correct direction, and `ss.is_active=true` for runtime symbol(s). If code changed, restart affected Python service only if needed; no rebuild unless dependencies changed. Before any commit, run `gitnexus_detect_changes()` if GitNexus is available; if unavailable, document limitation and use targeted `git diff -- services/aureus-signal/engine/strategies/seed_strategies.py services/aureus-signal/engine/orders.py` plus test/DB evidence.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps && docker exec aureus-signal-dev python -m engine.strategies.seed_strategies && docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT t.name, ss.symbol, ss.is_active, t.config->'trade_execution'->>'direction' AS direction, t.config->'trade_execution'->>'entry_type' AS entry_type, t.config->'trade_execution'->>'entry_method' AS entry_method FROM aureus_strategy_templates t JOIN aureus_symbol_strategies ss ON ss.strategy_id = t.id WHERE t.name IN ('TREND_CONT_LIMIT_BULL','TREND_CONT_LIMIT_BEAR') ORDER BY t.name, ss.symbol;\""</automated>
  </verify>
  <done>DB output shows both strategy templates and active symbol links with LIMIT/ENTRY_PIVOT_LIMIT and correct BUY/SELL directions; logs/tests have no runtime errors related to these strategies.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| code seed declarations -> database | Python seed config becomes JSON stored in `aureus_strategy_templates.config`. Bad config can cause runtime rejects or invalid orders. |
| database strategy config -> runtime order manager | DB-loaded config crosses into `TemplateStrategy`, `StrategyRegistry`, and `SimulatedTradeManager`; values must be validated against allowed entry/order contracts. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260427-wwv-01 | Tampering | `seed_system_strategies` strategy JSON | mitigate | Verify only the two named configs are changed; seed uses parameterized SQL and JSON serialization; run targeted diff/GitNexus detect_changes before commit. |
| T-260427-wwv-02 | Denial of Service | runtime strategy evaluation/order creation | mitigate | Tests must cover unavailable pivot path returning clean rejection, not exception/crash; DB seed verification confirms runtime can load configs. |
| T-260427-wwv-03 | Spoofing | strategy names in DB | mitigate | Query exact names `TREND_CONT_LIMIT_BULL` and `TREND_CONT_LIMIT_BEAR` after seed and confirm active symbol links. |
| T-260427-wwv-04 | Information Disclosure | DB verification output | accept | Verification queries only strategy names/config fields, no secrets or user PII. |
</threat_model>

<verification>
Overall checks:
1. GitNexus impact was run before editing `seed_system_strategies` or any runtime method; blast radius documented.
2. Python tests through WSL `.venv` pass for focused strategy/order plan coverage.
3. Runtime seed command succeeds inside `aureus-signal-dev` container.
4. TimescaleDB query proves both strategy templates and symbol links exist and are active with expected config.
5. `gitnexus_detect_changes()` runs before commit; if tool unavailable, executor documents limitation and includes targeted diff/test/DB evidence.
</verification>

<success_criteria>
- `TREND_CONT_LIMIT_BULL` and `TREND_CONT_LIMIT_BEAR` declarations are logically valid for ENTRY_PIVOT_LIMIT LIMIT orders.
- No unrelated strategy behavior is changed.
- If fixes are made, tests prove order plan completeness and pivot-limit semantics.
- DB runtime seed verification shows both strategies active and runnable for configured symbols.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260427-wwv-validate-and-fix-trend-cont-limit-bull-a/260427-wwv-SUMMARY.md` with audit findings, changes made or no-change rationale, test commands, DB query output, and GitNexus gate evidence.
</output>
