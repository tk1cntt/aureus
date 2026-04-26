---
phase: 260426-ayf-update-ca-ch-ti-nh-htf-trend-trong-servi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/signals/trend.py
  - services/aureus-signal/tests/test_trend_o1.py
autonomous: true
requirements:
  - QUICK-260426-AYF
must_haves:
  truths:
    - "htf_trend không còn phụ thuộc EMA200/ema_200 để cho ra BULLISH hoặc BEARISH."
    - "Trend phản ứng nhanh hơn với hướng thị trường khi structure/CHOCH, EMA21/55 momentum, OB và sweep cùng nghiêng một phía."
    - "Trend vẫn NEUTRAL khi tín hiệu lẫn lộn hoặc thiếu directional evidence rõ ràng."
  artifacts:
    - path: "services/aureus-signal/engine/signals/trend.py"
      provides: "TrendSignal.calculate dùng score hiện có trong file, không dùng ema_200/EMA200 penalty/gate"
      contains: "structure_score"
    - path: "services/aureus-signal/tests/test_trend_o1.py"
      provides: "Regression tests cho no-ema200 dependency, faster reaction, mixed-evidence neutral"
      contains: "TrendSignal"
  key_links:
    - from: "TrendSignal.calculate"
      to: "state_obj.htf_trend"
      via: "score-based regime decision"
      pattern: "state_obj\.htf_trend"
    - from: "tests/test_trend_o1.py"
      to: "TrendSignal.calculate"
      via: "in-memory DataFrame/state fixtures"
      pattern: "TrendSignal\("
---

<objective>
Cập nhật cách tính `htf_trend` trong `services/aureus-signal/engine/signals/trend.py` để bỏ hoàn toàn EMA200 khỏi quyết định trend, dùng các score/signal hiện có trong chính file (`_structure_score`, `_ema_score` EMA21/55, `_ob_score`, `_sweep_score`) theo phương án tốt nhất: score tổng hợp có xác nhận tối thiểu từ structure/momentum hoặc OB mạnh, nhưng giữ NEUTRAL khi bằng chứng nhiễu.

Purpose: EMA200 đang làm `htf_trend` trễ với thị trường; mục tiêu là nhạy hơn mà không thêm dependency/indicator mới và không phá contract downstream `BULLISH|BEARISH|NEUTRAL`.
Output: Code trend được sửa surgical và regression tests chứng minh bỏ EMA200 dependency, phản ứng nhanh, và neutral ổn định khi mixed evidence.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/RUN_SERVICES.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-kj9-th-c-hi-n-update-trend-theo-nh-ph-n-ti-c/260425-kj9-SUMMARY.md
@D:/Aureus/services/aureus-signal/engine/signals/trend.py

<interfaces>
TrendSignal hiện có:
```python
class TrendSignal(BaseSignal):
    signal_type = SignalType.INDICATOR
    def __init__(self, ema_period: int = 200): ...
    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]: ...
    def _ema_value(self, df: pd.DataFrame, state_obj: Any, period: int) -> Optional[float]: ...
    def _structure_score(self, state_obj: Any, kwargs: Dict[str, Any]) -> float: ...
    def _ema_score(self, df: pd.DataFrame, ema21: Optional[float], ema55: Optional[float]) -> float: ...
    def _ob_score(self, obs: list, current_t: int) -> float: ...
    def _sweep_score(self, obs: list, kwargs: Dict[str, Any]) -> float: ...
    def _ema200_penalty(self, current_price: float, current_ema: Optional[float], raw_score: float) -> float: ...
```

Contract cần giữ:
- `state_obj.htf_trend` nhận một trong `BULLISH`, `BEARISH`, `NEUTRAL`.
- Return dict giữ `tag: "htf_trend"`, `value`, `t`, `data.regime` với `TREND_UP|TREND_DN|SIDEWAYS`.
- Không thêm package mới. Không đụng database.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add focused regression tests for EMA200-free HTF trend</name>
  <files>services/aureus-signal/tests/test_trend_o1.py</files>
  <behavior>
    - Test 1: Bullish HTF trend can be produced from bullish CHOCH/HH-HL structure plus EMA21/55 momentum and bullish OB evidence even when no `ema_200` column/state exists.
    - Test 2: Bearish HTF trend can flip from bearish CHOCH/LH-LL structure plus EMA21/55 momentum and bearish OB/sweep evidence without waiting for EMA200 alignment.
    - Test 3: Mixed/conflicting evidence remains `NEUTRAL`, proving the more responsive logic does not become always-on/noisy.
    - Test 4: Returned `data` no longer exposes or requires `ema_ref`/`ema200_penalty`; if kept temporarily for compatibility, test must assert these fields are not used for decision and no `ema_200` fixture is required. Prefer removing EMA200-specific explainability fields to match the user requirement.
  </behavior>
  <action>Before editing tests, inspect existing trend tests. If `services/aureus-signal/tests/test_trend_o1.py` does not exist in the current checkout, create it with small in-memory pandas DataFrame fixtures and a simple state object. Do not use database or services. Write tests first so they fail against current EMA200-dependent implementation. Use only existing `TrendSignal` public behavior; avoid asserting private implementation details except absence of EMA200 dependency/output where necessary.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_trend_o1.py -q"</automated>
  </verify>
  <done>Tests cover removal of EMA200 dependency, faster directional reaction, and stable neutral mixed evidence. Initial RED failure is documented in the summary.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Replace EMA200-dependent decision with existing score consensus</name>
  <files>services/aureus-signal/engine/signals/trend.py</files>
  <behavior>
    - With bullish structure/CHOCH plus EMA21>EMA55 momentum and supporting OB/sweep score, `calculate` returns/stores `BULLISH` without reading `ema_200` or requiring `ema_period=200` history.
    - With bearish structure/CHOCH plus EMA21<EMA55 momentum and supporting OB/sweep score, `calculate` returns/stores `BEARISH` without EMA200 alignment.
    - With score conflict or weak directional evidence, `calculate` returns/stores `NEUTRAL`.
  </behavior>
  <action>Run GitNexus impact analysis before modifying symbols: try `npx gitnexus impact TrendSignal.calculate --direction upstream --repo Aureus`, and if the exact method is not indexed, run `npx gitnexus impact TrendSignal --direction upstream --repo Aureus`. Report/directly record blast radius in the summary. Then surgically update `TrendSignal.calculate`: remove the `current_ema = self._ema_value(..., self.ema_period)` requirement, remove `ema200_penalty` from score, and stop using EMA200 as a gate/penalty. Keep EMA21/55 via `_ema_score`, structure via `_structure_score`, OB via `_ob_score`, sweep via `_sweep_score`. Best-choice decision rule: use a bounded raw score from existing methods, require at least one fast directional anchor (`structure_score` or `ema_score`) plus supporting total score/OB/sweep confirmation; return NEUTRAL for mixed anchors (e.g. structure positive but ema_score negative) or weak totals. Remove `_ema200_penalty` if it becomes unused. Do not add new indicators, files, dependencies, or broad refactors.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_trend_o1.py -q"</automated>
  </verify>
  <done>`trend.py` no longer reads/requires `ema_200`/EMA200 for `htf_trend`; all focused tests pass; downstream output contract remains unchanged except intentional removal of EMA200-specific explainability fields if implemented.</done>
</task>

<task type="auto">
  <name>Task 3: Verify scoped behavior and change impact</name>
  <files>services/aureus-signal/engine/signals/trend.py, services/aureus-signal/tests/test_trend_o1.py</files>
  <action>Run scoped pytest. Then run GitNexus change detection before any commit attempt: `npx gitnexus detect-changes --scope all` or the installed equivalent. If GitNexus detect_changes is unavailable, document the blocker exactly and fall back to `git diff -- services/aureus-signal/engine/signals/trend.py services/aureus-signal/tests/test_trend_o1.py` plus `git status --short` to verify only expected files changed. If pytest command fails because of service/runtime command conventions, consult `D:/Aureus/RUN_SERVICES.md` and rerun with the documented WSL `.venv` pattern. No database E2E is required because no database code is touched.</action>
  <verify>
    <automated>wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_trend_o1.py -q"</automated>
  </verify>
  <done>Verification evidence includes passing scoped pytest, GitNexus impact result, GitNexus detect_changes result or documented CLI blocker with diff/status fallback, and confirmation that no DB E2E was needed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| market-data/state -> TrendSignal.calculate | DataFrame/state/kwargs can contain missing, stale, or mixed indicator evidence. |
| TrendSignal.calculate -> downstream strategy/journal/Telegram consumers | `htf_trend` output influences strategy context and reporting. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260426-ayf-01 | Tampering | `TrendSignal.calculate` inputs | mitigate | Coerce numeric close/EMA values defensively as existing code does; tests use no `ema_200` fixture and mixed evidence case. |
| T-260426-ayf-02 | Denial of Service | trend calculation | mitigate | Keep computation O(window) over recent OBs as current `_ob_score`/`_sweep_score`; no new external calls or DB access. |
| T-260426-ayf-03 | Information Disclosure | output `data` explainability | accept | Output contains derived scores only, no secrets/PII; do not add raw account/order data. |
</threat_model>

<verification>
Automated gate:
`wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_trend_o1.py -q"`

Change-scope gate:
- GitNexus impact before editing `TrendSignal.calculate`/`TrendSignal`.
- GitNexus detect_changes before commit if available; otherwise documented blocker plus scoped diff/status fallback.
</verification>

<success_criteria>
- `services/aureus-signal/engine/signals/trend.py` no longer uses EMA200/`ema_200`/`ema_period=200` to decide `htf_trend`.
- Existing score methods/signals in `trend.py` drive the final decision.
- Regression tests prove no EMA200 dependency, faster bullish/bearish reaction, and NEUTRAL on mixed evidence.
- No new dependency, no database change, no DB E2E required.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260426-ayf-update-ca-ch-ti-nh-htf-trend-trong-servi/260426-ayf-SUMMARY.md`.
</output>
