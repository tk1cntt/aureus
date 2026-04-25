---
phase: 260425-mfv-tpo-shape-output
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/aureus-signal/engine/indicator_snapshot.py
  - services/aureus-signal/tests/test_indicator_snapshot.py
  - services/aureus-notifier/formatters.py
  - services/aureus-notifier/tests/test_formatters.py
  - services/aureus-signal/engine/signals/tpo_replay.py
  - services/aureus-signal/tests/test_tpo_replay.py
autonomous: true
requirements: [REQ-LQO-06, REQ-LQO-07, REQ-LQO-08]
user_setup: []
must_haves:
  truths:
    - "Indicator snapshot carries calibrated TPO shape, shape_confidence_pct, and shape_scores_pct from state.tpo_profile for tpo_d1/tpo_h1/tpo_m30 without schema or DB persistence changes."
    - "SIGNAL ALERT Telegram renders TPO shape as explanatory metadata and words confidence as heuristic confidence, not win probability or statistical probability."
    - "Replay/backtest calibration report includes shape flip-rate and confidence-distribution baseline metrics by timeframe, while leaving strategy scoring/tag selection unchanged."
    - "No strategy scoring, seed strategy template, journal persistence, DB schema, or migration file consumes TPO shape in this quick task."
  artifacts:
    - path: "services/aureus-signal/engine/indicator_snapshot.py"
      provides: "Display-only indicator snapshot passthrough/sanitization for TPO shape metadata"
      contains: "tpo_d1"
    - path: "services/aureus-signal/tests/test_indicator_snapshot.py"
      provides: "Integration coverage that TPO shape metadata survives snapshot construction"
      contains: "shape_confidence_pct"
    - path: "services/aureus-notifier/formatters.py"
      provides: "SIGNAL ALERT rendering for TPO explanatory shape metadata"
      contains: "Heuristic"
    - path: "services/aureus-notifier/tests/test_formatters.py"
      provides: "Telegram formatter regression coverage for shape metadata and low-confidence safe rendering"
      contains: "SIGNAL ALERT"
    - path: "services/aureus-signal/engine/signals/tpo_replay.py"
      provides: "Offline shape flip-rate and confidence-distribution baseline metrics"
      contains: "shape_flip_rate"
    - path: "services/aureus-signal/tests/test_tpo_replay.py"
      provides: "Replay/backtest baseline tests and scoring guardrail"
      contains: "confidence_distribution"
  key_links:
    - from: "services/aureus-signal/engine/indicator_snapshot.py"
      to: "state.tpo_profile"
      via: "build_indicator_snapshot_for_telegram reads tpo_d1/tpo_h1/tpo_m30"
      pattern: "tpo_profile.*tpo_d1"
    - from: "services/aureus-notifier/formatters.py"
      to: "indicator_snapshot.tpo_*"
      via: "format_signal_event -> format_indicator_snapshot -> _fmt_tpo"
      pattern: "shape_confidence_pct"
    - from: "services/aureus-signal/engine/signals/tpo_replay.py"
      to: "shape metadata in replay rows"
      via: "replay_tpo_calibration derives flip and confidence baseline metrics without calling scoring with shape"
      pattern: "shape_flip_rate|confidence_distribution"
---

<objective>
Tích hợp calibrated TPO shape output vào indicator snapshot và SIGNAL ALERT Telegram theo REQ-LQO-06/07/08, chỉ như explanatory metadata.

Purpose: Người dùng thấy shape D/B/p/b và confidence đã calibrated trong snapshot/Telegram, đồng thời có baseline replay để đánh giá flip rate và confidence distribution trước khi shape được phép ảnh hưởng scoring.
Output: Snapshot/Telegram integration tests, formatter wording an toàn, replay metrics baseline; không sửa DB schema/migrations và không đưa shape vào strategy scoring.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md
@D:/Aureus/.planning/quick/260425-m1y-implement-calibrated-tpo-shape-classifie/260425-m1y-SUMMARY.md
@D:/Aureus/.planning/quick/260425-m1y-implement-calibrated-tpo-shape-classifie/260425-m1y-VERIFICATION.md
@D:/Aureus/services/aureus-signal/engine/indicator_snapshot.py
@D:/Aureus/services/aureus-signal/tests/test_indicator_snapshot.py
@D:/Aureus/services/aureus-notifier/formatters.py
@D:/Aureus/services/aureus-notifier/tests/test_formatters.py
@D:/Aureus/services/aureus-signal/engine/signals/tpo_replay.py
@D:/Aureus/services/aureus-signal/tests/test_tpo_replay.py

<interfaces>
Existing contracts to preserve:
- `build_indicator_snapshot_for_telegram(state, m1_df=None) -> Dict[str, Any]` is display-only and must not write DB/persistence.
- `state.tpo_profile` uses keys `tpo_d1`, `tpo_h1`, `tpo_m30`; each TPO block may include `POC`, `VAH`, `VAL`, `shape`, `shape_confidence_pct`, `shape_scores_pct`.
- `format_signal_event(event: dict) -> str` reads `event["data"]["indicator_snapshot"]` and renders SIGNAL ALERT HTML.
- `replay_tpo_calibration(rows, thresholds=(0.75,)) -> Dict[str, Any]` currently reports detector/tag calibration metrics. Extend report output, but do not change `tpo_strategy_tags_from_candidates` semantics.
</interfaces>

<decisions>
- REQ-LQO-06: Shape is backdrop/explanatory geometry only; detector context remains the confirmation layer.
- REQ-LQO-07: Replay/backtest metrics are required before any shape scoring. This plan adds metrics baseline only, not scoring.
- REQ-LQO-08: Telegram/indicator snapshot must remain compatible and must not imply `shape_confidence_pct` is probability.
- Database is explicitly out of scope: do not modify migrations, schema, journal persistence, or database-facing code. Because no database-facing persistence code is touched, no E2E DB test is required for this quick task.
</decisions>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Preserve calibrated TPO shape metadata in indicator snapshot</name>
  <files>services/aureus-signal/engine/indicator_snapshot.py, services/aureus-signal/tests/test_indicator_snapshot.py</files>
  <behavior>
    - Test 1: when `state.tpo_profile.tpo_d1/tpo_h1/tpo_m30` contain `POC/VAH/VAL/shape/shape_confidence_pct/shape_scores_pct`, `build_indicator_snapshot_for_telegram` returns those fields intact or via an equivalent display-only sanitized dict.
    - Test 2: malformed/missing TPO blocks still return `None` or safe existing behavior; no exception and no DB access.
    - Test 3: snapshot does not add any scoring field such as `shape_score_weight`, `strategy_score`, or `shape_signal`.
  </behavior>
  <action>Before editing any function, run GitNexus impact analysis for `build_indicator_snapshot_for_telegram` (or the closest available GitNexus CLI/MCP fallback) and record direct callers/risk in the summary. Add/adjust integration tests first in `test_indicator_snapshot.py` for REQ-LQO-08. If `indicator_snapshot.py` already passes through full TPO blocks safely, keep production change minimal and only tighten the display-only contract if needed; do not touch DB schema, migrations, journal persistence, or strategy files. Keep shape as explanatory metadata only, not a scoring input.</action>
  <verify>
    <automated>cd D:/Aureus && pytest services/aureus-signal/tests/test_indicator_snapshot.py -q</automated>
  </verify>
  <done>Indicator snapshot exposes calibrated TPO shape metadata for D1/H1/M30 display paths, tests prove safe missing/malformed behavior, and no database or strategy-scoring files are modified.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Render TPO shape safely in SIGNAL ALERT Telegram</name>
  <files>services/aureus-notifier/formatters.py, services/aureus-notifier/tests/test_formatters.py</files>
  <behavior>
    - Test 1: `format_signal_event` renders TPO Shape for D1/H1/M30 in SIGNAL ALERT when indicator snapshot contains `shape` and `shape_confidence_pct`.
    - Test 2: wording labels confidence as heuristic/explanatory metadata and does not say probability, win rate, edge, score contribution, buy/sell confidence, or any scoring language.
    - Test 3: low confidence or missing shape renders safely without crashing and without misleading probability wording.
  </behavior>
  <action>Before editing formatter symbols, run GitNexus impact analysis for `format_signal_event` and the TPO formatting helper if available, then report blast radius in the summary. Update `_fmt_tpo`/related SIGNAL ALERT formatting so shape is rendered as explanatory metadata per REQ-LQO-08, e.g. wording equivalent to `Shape:D (heuristic 82.5%)`; avoid any language that treats confidence as statistical probability or strategy edge. Do not change notifier transport, Telegram bot sending, strategy scoring, or persistence.</action>
  <verify>
    <automated>cd D:/Aureus && pytest services/aureus-notifier/tests/test_formatters.py -q</automated>
  </verify>
  <done>SIGNAL ALERT includes calibrated TPO shape metadata with safe heuristic wording, formatter tests cover normal and low/missing confidence cases, and no scoring/persistence behavior changes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add replay/backtest shape baseline metrics without scoring integration</name>
  <files>services/aureus-signal/engine/signals/tpo_replay.py, services/aureus-signal/tests/test_tpo_replay.py</files>
  <behavior>
    - Test 1: `replay_tpo_calibration` returns deterministic `shape_baseline` metrics containing flip rate by timeframe for D1/H1/M30 when replay rows include shape metadata across sequential rows.
    - Test 2: `shape_baseline` includes confidence distribution by timeframe, at minimum count/min/max/avg and bucket counts or equivalent stable bins for `shape_confidence_pct`.
    - Test 3: existing detector threshold sensitivity and emitted strategy tag counts remain unchanged for existing fixtures, proving shape does not enter strategy scoring/tag selection.
    - Test 4: import-scope guard still excludes persistence/runtime modules and no DB-facing code is imported.
  </behavior>
  <action>Before editing `replay_tpo_calibration`, run GitNexus impact analysis for that symbol and report blast radius. Extend offline replay metrics for REQ-LQO-07 by reading shape metadata from each row context/timeframes, computing per-timeframe shape flip rate between consecutive valid shapes, and confidence distribution from `shape_confidence_pct`. Keep this as reporting-only under a clear report key such as `shape_baseline`; do not pass shape into `tpo_strategy_tags_from_candidates`, do not alter seed strategies, and do not add A/B scoring behavior. Preserve current report keys and current tests for threshold sensitivity.</action>
  <verify>
    <automated>cd D:/Aureus && pytest services/aureus-signal/tests/test_tpo_replay.py services/aureus-signal/tests/test_indicator_snapshot.py services/aureus-notifier/tests/test_formatters.py -q</automated>
  </verify>
  <done>Replay report includes flip-rate/confidence-distribution baseline metrics for TPO shape, all existing strategy tag metrics remain stable, GitNexus change detection is run before commit if available, and no DB/schema/migration/scoring files are modified.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| signal-state→indicator snapshot | Runtime state data is converted into display-only Telegram payload; malformed TPO blocks must not crash formatting. |
| indicator snapshot→Telegram HTML | Snapshot values cross into user-visible HTML; values must be escaped and wording must not misrepresent confidence. |
| replay input rows→offline report | Historical/replay rows are untrusted test/offline data; invalid/missing shape metadata must not affect scoring logic. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260425-mfv-01 | T | `build_indicator_snapshot_for_telegram` | mitigate | Preserve display-only snapshot behavior and add tests for safe missing/malformed TPO blocks. |
| T-260425-mfv-02 | I | `format_signal_event` / `_fmt_tpo` | mitigate | Escape rendered TPO text and label confidence as heuristic metadata, not probability/scoring. |
| T-260425-mfv-03 | E | `replay_tpo_calibration` | mitigate | Keep shape metrics under reporting-only key; tests assert emitted strategy tags/threshold sensitivity remain unchanged. |
| T-260425-mfv-04 | T | DB/schema/persistence | accept | Explicitly out of scope; plan forbids migration/schema/journal changes and therefore no DB trust boundary is expanded. |
</threat_model>

<verification>
Run focused tests after each task and final combined regression:

<automated>cd D:/Aureus && pytest services/aureus-signal/tests/test_indicator_snapshot.py services/aureus-notifier/tests/test_formatters.py services/aureus-signal/tests/test_tpo_replay.py -q</automated>

Before commit, run GitNexus change detection if available: `gitnexus_detect_changes()` via MCP or closest CLI fallback. If GitNexus tools are unavailable, record the fallback checks and run `git diff --name-only` to prove only plan files changed.
</verification>

<success_criteria>
- REQ-LQO-06: Shape remains explanatory geometry metadata; detector/strategy scoring behavior is not changed.
- REQ-LQO-07: Replay/backtest report exposes baseline flip rate and confidence distribution by timeframe before scoring integration.
- REQ-LQO-08: Indicator snapshot and SIGNAL ALERT Telegram display calibrated shape metadata safely and avoid probability/scoring wording.
- No DB schema, migration, journal persistence, or database-facing code is modified; DB E2E test is not required because DB is out of scope.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260425-mfv-t-ch-h-p-calibrated-tpo-shape-output-v-o/260425-mfv-SUMMARY.md` with GitNexus impact/detect-change evidence, test outputs, DB out-of-scope confirmation, and a note that shape was not added to strategy scoring.
</output>
