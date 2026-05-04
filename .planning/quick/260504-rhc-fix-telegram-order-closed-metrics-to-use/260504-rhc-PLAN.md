---
phase: quick-260504-rhc-fix-telegram-order-closed-metrics-to-use
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-notifier/order_reporter.py
  - services/aureus-notifier/tests/test_order_reporter.py
autonomous: true
requirements:
  - QUICK-260504-RHC
must_haves:
  truths:
    - "Telegram Order Closed message uses real close_price, not event pips override, when entry and exit prices exist."
    - "ETHUSD BUY Entry 2364.45 Exit 2365.44 renders about +99.0 pips, not +9900.0 pips."
    - "Order Closed RR is actual realized reward/risk from entry, close_price, and initial SL when available, not planned TP/SL ratio."
  artifacts:
    - path: "services/aureus-notifier/order_reporter.py"
      provides: "ORDER_CLOSED Telegram pips and realized RR calculation"
      contains: "def _format_close"
    - path: "services/aureus-notifier/tests/test_order_reporter.py"
      provides: "Regression coverage for close_price based pips and realized RR"
      contains: "test_close_metrics_use_actual_exit_price_for_ethusd"
  key_links:
    - from: "services/aureus-notifier/order_reporter.py::_format_close"
      to: "ORDER_CLOSED event close_price/open_price plus journal entry_price/sl_initial/tp_initial"
      via: "entry/exit/SL/TP metric calculation"
      pattern: "close_price.*entry_price.*sl_initial"
    - from: "services/aureus-notifier/tests/test_order_reporter.py"
      to: "OrderStatusReporter._format_close"
      via: "direct formatter regression test"
      pattern: "_format_close\(event, journal\)"
---

<objective>
Sửa Telegram `Order Closed` metrics để pips và RR dùng giá đóng thực tế.

Purpose: Message đóng lệnh hiện có thể hiển thị `+9900.0 pips` và RR planned `1:1.5` cho ETHUSD BUY Entry 2364.45 Exit 2365.44. Cần tính lại từ `close_price`, `entry_price`, `sl_initial`, `tp_initial` khi có đủ dữ liệu.

Output: Một fix nhỏ trong formatter và regression tests.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/services/aureus-notifier/order_reporter.py
@D:/Aureus/services/aureus-notifier/tests/test_order_reporter.py

<interfaces>
Key existing contracts:

`services/aureus-notifier/order_reporter.py`
```python
PIP_VALUES = {
    "XAUUSD": 0.01, "BTCUSD": 0.01, "ETHUSD": 0.01,
    "DEFAULT": 0.0001
}

class OrderStatusReporter:
    def _format_close(self, event: dict, journal: dict | None = None) -> str:
        """Format single order close notification in HTML with strategy info."""
```

`_format_close` current behavior to change:
- entry uses `event["open_price"]`, fallback `journal["entry_price"]` only when event entry is `0.0`.
- exit uses `event["close_price"]`.
- pips currently prefers explicit `event["pips"]` before price calculation.
- RR currently uses planned `abs(tp_initial - entry) / abs(entry - sl_initial)` and ignores `close_price`.

Required behavior:
- If valid `entry > 0` and `exit_p > 0`, calculate pips from actual `exit_p - entry` using `PIP_VALUES[symbol.upper()]` where available; do not use `digits` multiplier for symbols with explicit pip size.
- Only use explicit `event["pips"]` when price-based calculation cannot run.
- Realized RR: if valid `entry > 0`, `exit_p > 0`, and `sl_initial > 0`, compute `abs(exit_p - entry) / abs(entry - sl_initial)` and display with existing `RR: 1:{rr_ratio}` line. Use direction only for signed pips; RR remains magnitude. If SL missing, keep RR omitted.
- Do not touch `mql5/AureusProvider_v2.mq5`, `mql5/AureusProvider_v2.ex5`, or `stable/`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regression tests for actual close-price metrics</name>
  <files>services/aureus-notifier/tests/test_order_reporter.py</files>
  <behavior>
    - ETHUSD BUY with `open_price=2364.45`, `close_price=2365.44`, `pips=9900.0`, and journal `sl_initial=2363.79`, `tp_initial=2365.44` renders `+99.0 pips`, not `+9900.0 pips`.
    - Same ETHUSD case renders realized RR `1:1.5` because `(2365.44 - 2364.45) / (2364.45 - 2363.79) = 1.5`.
    - Case with planned TP farther than close price proves RR uses close price, not TP: same entry/SL, `tp_initial=2366.43`, `close_price=2365.44` still renders `RR: 1:1.5`, not `RR: 1:3.0`.
  </behavior>
  <action>Before editing, locate `OrderStatusReporter._format_close` and run GitNexus impact analysis for symbol `OrderStatusReporter._format_close` or `_format_close` with upstream direction. Report direct callers, affected flows, risk level. Then add focused pytest tests to `TestFormatClose`. Keep existing style. Tests must fail before production fix if old behavior remains.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py::TestFormatClose -q</automated>
  </verify>
  <done>Regression tests exist and cover ETHUSD bad explicit pips override plus realized RR from close price.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Recalculate pips and RR from real close price</name>
  <files>services/aureus-notifier/order_reporter.py</files>
  <behavior>
    - Price-based pips wins when entry and close price exist, even if event contains `pips`.
    - Symbol pip size comes from `PIP_VALUES` first, so ETHUSD uses `0.01` and Entry 2364.45 → Exit 2365.44 becomes `+99.0 pips`.
    - RR uses actual move to close price over initial risk to SL; planned TP only remains unused for RR display when close price exists.
    - Existing N/A behavior remains when entry or close price missing and no explicit pips exists.
  </behavior>
  <action>Update only `OrderStatusReporter._format_close`. Replace pips branch with: derive `pip = PIP_VALUES.get(symbol.upper(), PIP_VALUES["DEFAULT"])`; when `entry > 0 and exit_p > 0 and pip > 0`, signed pips = `(exit_p - entry) / pip` for BUY else `(entry - exit_p) / pip`; otherwise fallback to explicit `event["pips"]` when present. Replace RR branch with realized ratio from `abs(exit_p - entry) / abs(entry - sl)` when entry, exit, and SL are valid. Keep output label `RR: 1:{rr_ratio}`. Avoid DB changes, schema changes, MQL5 changes, and unrelated formatting cleanup.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py::TestFormatClose -q</automated>
  </verify>
  <done>All formatter tests pass; ETHUSD sample no longer can render `+9900.0 pips` when real entry and close price exist.</done>
</task>

<task type="auto">
  <name>Task 3: Run expected-scope checks</name>
  <files>services/aureus-notifier/order_reporter.py, services/aureus-notifier/tests/test_order_reporter.py</files>
  <action>Run full notifier order reporter tests, then run `gitnexus_detect_changes()` per project rule. Confirm only expected symbols/files changed. Do not commit unless user explicitly asks.</action>
  <verify>
    <automated>cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py -q</automated>
    <automated>gitnexus_detect_changes()</automated>
  </verify>
  <done>Tests pass and GitNexus changed-scope output matches only notifier formatter/test changes.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5/Gateway event → notifier formatter | Untrusted order event fields enter Telegram message generation. |
| Journal DB row → notifier formatter | Persisted trade data influences Telegram metrics. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260504-rhc-01 | Tampering | `OrderStatusReporter._format_close` | mitigate | Prefer price-derived metrics when entry and close price are valid, so stale or wrong event `pips` cannot override actual close metrics. |
| T-260504-rhc-02 | Information Disclosure | Telegram close message | accept | Message already contains trade price/profit data by design; no new fields added. |
| T-260504-rhc-03 | Denial of Service | Formatter numeric conversion | mitigate | Keep existing bounded formatting and avoid new external calls or DB work inside `_format_close`. |
</threat_model>

<verification>
Run:

```bash
cd D:/Aureus/services/aureus-notifier && python -m pytest tests/test_order_reporter.py -q
```

Then run GitNexus changed-scope check before any commit:

```text
gitnexus_detect_changes()
```
</verification>

<success_criteria>
- ETHUSD BUY Entry 2364.45 Exit 2365.44 displays `+99.0 pips`.
- Explicit wrong `event["pips"] = 9900.0` cannot override valid entry/exit calculation.
- RR uses actual close price against initial SL when available.
- No DB schema, MQL5 provider, `stable/`, or unrelated files touched.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260504-rhc-fix-telegram-order-closed-metrics-to-use/260504-rhc-SUMMARY.md`.
</output>
