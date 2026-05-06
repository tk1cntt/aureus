---
phase: 260506-rkn-pivot-sl-distance-limits
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/orders.py
  - services/aureus-signal/tests/test_pivot_sl.py
autonomous: true
requirements:
  - QUICK-260506-RKN
must_haves:
  truths:
    - "PIVOT_POINT orders are rejected when absolute entry-to-selected-SL distance is greater than configured symbol threshold."
    - "Thresholds are symbol-class specific: XAU 10.0 price units, USTEC 50.0 index points, BTC 500.0 price units, forex 20 pips converted with existing point-size convention."
    - "Distance equal to threshold remains allowed; only distance greater than threshold rejects."
    - "Non-PIVOT_POINT SL modes remain unchanged."
  artifacts:
    - path: "services/aureus-signal/engine/orders.py"
      provides: "PIVOT_POINT SL distance cap logic in _calculate_sl_tp using selected SL and entry price"
      contains: "PIVOT_POINT"
    - path: "services/aureus-signal/tests/test_pivot_sl.py"
      provides: "Regression coverage for reject/allow thresholds and non-PIVOT_POINT isolation"
      contains: "distance"
  key_links:
    - from: "services/aureus-signal/engine/orders.py"
      to: "services/aureus-signal/tests/test_pivot_sl.py"
      via: "SimulatedTradeManager._calculate_sl_tp PIVOT_POINT unit tests"
      pattern: "_calculate_sl_tp.*PIVOT_POINT"
---

<objective>
Thêm giới hạn khoảng cách SL cho `sl_mode == 'PIVOT_POINT'`.

Purpose: chặn lệnh có pivot SL quá xa so với entry để tránh risk quá lớn.
Output: logic reject trong `orders.py` và regression tests trong `test_pivot_sl.py`.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-signal/engine/orders.py
@D:/Aureus/services/aureus-signal/tests/test_pivot_sl.py

Assumptions:
- Scope chỉ `services/aureus-signal/engine/orders.py`; không đụng DB, không cần DB E2E.
- Distance semantic: `abs(entry - sl)` sau khi đã chọn pivot và áp `offset_pips`.
- Reject semantic: dùng cơ chế invalid SL/no-order hiện có bằng cách `return None, None` trong `_calculate_sl_tp`.
- Forex threshold 20 pips: dùng existing `get_point_size(symbol)` convention, tức threshold price distance = `20 * get_point_size(symbol)`.
- Symbol class detect tối thiểu: `symbol.upper()` chứa `XAU`, chứa `USTEC`/`NAS` nếu codebase đã dùng alias, chứa `BTC`; còn lại forex.

Relevant existing interfaces:
```python
# services/aureus-signal/engine/orders.py
def get_point_size(symbol: str) -> float:
    """Return point size for SL/TP calculation from symbols.json."""

class SimulatedTradeManager:
    def _calculate_sl_tp(self, trigger, state_obj, config, entry_price_override: float = None, recent_candles: Optional[List[Dict[str, Any]]] = None):
        """Calculates prices for SL and TP based on strategy config."""
```
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add PIVOT_POINT SL distance cap regression tests</name>
  <files>services/aureus-signal/tests/test_pivot_sl.py</files>
  <behavior>
    - XAU BUY PIVOT_POINT with entry 2010.0 and selected SL 1999.0 has distance 11.0 greater than 10.0, returns `(None, None)`.
    - XAU BUY PIVOT_POINT with distance exactly 10.0 returns non-null SL/TP.
    - USTEC SELL PIVOT_POINT with distance greater than 50.0 returns `(None, None)`.
    - BTC BUY PIVOT_POINT with distance greater than 500.0 returns `(None, None)`.
    - Forex symbol (example EURUSD) PIVOT_POINT with distance greater than `20 * get_point_size("EURUSD")` returns `(None, None)`.
    - Existing `test_fixed_pips_unchanged` still proves non-PIVOT_POINT unaffected.
  </behavior>
  <action>Update existing `TestCalculateSlTpPivotPoint` tests. Before touching code, executor must run `gitnexus_impact({target: "_calculate_sl_tp", direction: "upstream"})` or, if GitNexus MCP unavailable in executor, document tool limitation in summary and proceed with narrow file-scoped fallback. Add focused tests for distance cap before production change. Avoid changing existing test semantics unrelated to PIVOT_POINT distance.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_pivot_sl.py -x</automated>
  </verify>
  <done>New tests fail before production logic exists; existing PIVOT_POINT tests remain present and unchanged except minimal setup needed for new cases.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Enforce selected PIVOT_POINT SL distance caps</name>
  <files>services/aureus-signal/engine/orders.py, services/aureus-signal/tests/test_pivot_sl.py</files>
  <behavior>
    - Only `sl_mode == 'PIVOT_POINT'` evaluates distance cap after `sl` is calculated from selected pivot plus offset.
    - Reject when `abs(entry - sl) > threshold`; allow when `abs(entry - sl) <= threshold`.
    - Thresholds: XAU = 10.0 price units; USTEC/NAS aliases = 50.0 index points only if existing symbol naming needs alias; BTC = 500.0 price units; otherwise forex = `20 * get_point_size(symbol)`.
    - Rejection logs symbol, strategy, entry, selected SL, distance, threshold, and reason.
    - Return `(None, None)` on rejection to reuse current no-order path; do not alter FIXED_PIPS/SIGNAL_LOW/SIGNAL_HIGH branches.
  </behavior>
  <action>Implement small helper near symbol helpers in `orders.py`, e.g. `_get_pivot_sl_max_distance(symbol: str) -> float`, using existing `get_point_size(symbol)` for forex conversion. In PIVOT_POINT branch, after BUY/SELL assigns `sl` and before success log continues, compute `sl_distance = abs(entry - sl)` and reject if `sl_distance > max_distance`. Keep exact greater-than semantic; do not reject equality. Keep changes surgical, no refactor. If helper symbol edited, executor must run `gitnexus_impact` for `_get_pivot_sl_max_distance` after creation only if GitNexus supports new symbol lookup; otherwise document not applicable.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_pivot_sl.py -x</automated>
  </verify>
  <done>PIVOT_POINT over-threshold cases return `(None, None)`, at-threshold cases still compute SL/TP, non-PIVOT_POINT tests still pass.</done>
</task>

<task type="auto">
  <name>Task 3: Run focused verification and GitNexus change scope check</name>
  <files>services/aureus-signal/engine/orders.py, services/aureus-signal/tests/test_pivot_sl.py</files>
  <action>Run focused pytest. Then run `gitnexus_detect_changes({scope: "all"})` before any commit or final summary; if GitNexus MCP unavailable, document limitation and use `git diff -- services/aureus-signal/engine/orders.py services/aureus-signal/tests/test_pivot_sl.py` as safe fallback. Confirm only expected symbols/files changed and no DB behavior touched.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_pivot_sl.py -x</automated>
  </verify>
  <done>Focused tests pass; change scope limited to `orders.py` and `test_pivot_sl.py`; summary records GitNexus impact/detect results or explicit tool limitation fallback.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| strategy config -> order calculation | `sl.type`, `offset_pips`, symbol, and pivot data affect whether an order is emitted |
| signal state -> order dispatch | selected pivot and entry price produce SL accepted/rejected before MT5 dispatch |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260506-rkn-01 | Tampering | `_calculate_sl_tp` PIVOT_POINT branch | mitigate | Reject PIVOT_POINT SL when `abs(entry - sl)` exceeds deterministic symbol threshold. |
| T-260506-rkn-02 | Denial of Service | order dispatch path | mitigate | Return `(None, None)` before order dispatch for too-far SL, reusing existing no-order path. |
| T-260506-rkn-03 | Repudiation | rejection diagnostics | mitigate | Log strategy, symbol, entry, SL, distance, threshold, reason when cap rejects order. |
</threat_model>

<verification>
Run:

```bash
cd D:/Aureus/services/aureus-signal && python -m pytest tests/test_pivot_sl.py -x
```

Expected: all `test_pivot_sl.py` tests pass, including new distance cap tests and existing `test_fixed_pips_unchanged`.
</verification>

<success_criteria>
- PIVOT_POINT SL distance uses `abs(entry - selected_sl)` after selected pivot and offset.
- XAU rejects only distance greater than 10.0 price units.
- USTEC rejects only distance greater than 50.0 index points.
- BTC rejects only distance greater than 500.0 price units.
- Forex rejects only distance greater than `20 * get_point_size(symbol)`.
- Equal-to-threshold PIVOT_POINT order remains allowed.
- Non-PIVOT_POINT SL modes unchanged.
- No DB code touched; no DB E2E required.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260506-rkn-pivot-sl-distance-limits/260506-rkn-SUMMARY.md`
</output>
