---
phase: 260503-neg-fix-spam-managepositiondecision-hold-pro
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
  - .planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md
autonomous: true
requirements:
  - QUICK-260503-NEG
must_haves:
  truths:
    - "Repeated ManagePositionDecision HOLD logs for reason=profile_fallback do not spam every tick for same symbol+magic+direction+reason."
    - "Repeated ManagePositionDecision HOLD logs for reason=legacy_no_rule_matched do not spam every tick for same symbol+magic+direction+reason."
    - "CLOSE actions, market-close first detection logs, close failure/error logs, and non-HOLD decisions remain visible."
  artifacts:
    - path: "mql5/AureusProvider_v2.mq5"
      provides: "Provider-local HOLD decision log suppression for repeated low-value reasons"
      contains: "LogManagementDecision"
    - path: ".planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md"
      provides: "Execution summary with verification, GitNexus limitation, compile limitation, and changed scope"
  key_links:
    - from: "LogManagementDecision"
      to: "PrintFormat([ManagePositionDecision])"
      via: "HOLD-only repeated reason suppression before print"
      pattern: "action == \"HOLD\""
    - from: "ProcessPositionsByType"
      to: "LogManagementDecision(profile_fallback)"
      via: "same symbol+magic+direction+reason emits once or long TTL"
      pattern: "profile_fallback"
    - from: "ProcessLegacyPositionsByType"
      to: "LogManagementDecision(legacy_no_rule_matched)"
      via: "same symbol+magic+direction+reason emits once or long TTL"
      pattern: "legacy_no_rule_matched"
---

<objective>
Fix noisy repeated `[ManagePositionDecision]` HOLD logs in `AureusProvider_v2` for `profile_fallback` and `legacy_no_rule_matched`.

Purpose: keep MT5 journal readable after market-close guard has already stopped close spam, without hiding close attempts, market-close detection, close failures, non-HOLD decisions, or errors.
Output: surgical provider-local log suppression keyed by `symbol+magic+direction+reason`, plus summary.
</objective>

<execution_context>
@D:/Aureus/.claude/get-shit-done/workflows/execute-plan.md
@D:/Aureus/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Aureus/CLAUDE.md
@D:/Aureus/.planning/STATE.md
@D:/Aureus/.planning/quick/260503-mjm-market-closed-guard-v-n-spam-log-hold-pr/260503-mjm-SUMMARY.md
@D:/Aureus/.planning/quick/260503-n24-update-khi-n-o-g-p-l-i-market-close-c-a-/260503-n24-SUMMARY.md
@D:/Aureus/mql5/AureusProvider_v2.mq5

Key existing facts:
- `LogManagementDecision(...)` prints every `[ManagePositionDecision]` line.
- `ProcessPositionsByType(...)` logs `action=HOLD reason=profile_fallback` when `ResolveManagementProfile(...)` falls back.
- Legacy branch logs `action=HOLD reason=legacy_no_rule_matched`.
- Previous quick tasks added market-close guards; active guard path is intentionally silent.
- GitNexus may not index MQL5 symbols; previous summaries document `Target ... not found` for MQL5 symbols and detect command limitations.

Implementation assumption:
- Prefer once-per-key suppression for only low-value repeated HOLD reasons: `profile_fallback` and `legacy_no_rule_matched`.
- If executor finds existing rate-limit helper, reuse it. Otherwise add a small provider-local helper near `LogManagementDecision`.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add HOLD decision spam suppression at log boundary</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <behavior>
    - First `LogManagementDecision(symbol, magic, direction, profile, "HOLD", "profile_fallback", ...)` for a unique `symbol+magic+direction+reason` prints.
    - Later identical `profile_fallback` HOLD logs for same `symbol+magic+direction+reason` are suppressed.
    - First `legacy_no_rule_matched` HOLD log for a unique `symbol+magic+direction+reason` prints; later identical ones suppress.
    - `action != "HOLD"` always prints.
    - HOLD reasons other than `profile_fallback` and `legacy_no_rule_matched` keep current behavior unless executor finds requirement says otherwise.
    - `target` details for ticket/target_sl remain unchanged for non-suppressed logs.
  </behavior>
  <action>Before editing, run GitNexus impact for `LogManagementDecision`; if GitNexus cannot find MQL5 symbol, document exact limitation and proceed with source-level checks. Modify only `LogManagementDecision` and minimal helper/state declarations needed nearby. Add a compact suppression helper keyed by `symbol`, `magic`, `direction`, and `reason`. Suppress only when `action == "HOLD"` and `reason` is `profile_fallback` or `legacy_no_rule_matched`. Do not suppress `CLOSE`, market-close guard detection logs, close failure logs, non-HOLD decisions, unknown profile fallback warning from `ResolveManagementProfile`, or error logs. Keep existing `PrintFormat` format unchanged for emitted logs.</action>
  <verify>
    <automated>cd /d/Aureus && python - <<'PY'
from pathlib import Path
p = Path('mql5/AureusProvider_v2.mq5')
s = p.read_text(encoding='utf-8')
assert 'void LogManagementDecision(' in s
assert 'profile_fallback' in s and 'legacy_no_rule_matched' in s
log = s[s.index('void LogManagementDecision('):s.index('//+------------------------------------------------------------------+', s.index('void LogManagementDecision('))]
assert 'action == "HOLD"' in log or 'action=="HOLD"' in log
assert 'profile_fallback' in log and 'legacy_no_rule_matched' in log
assert 'PrintFormat("[ManagePositionDecision]' in log
assert log.index('HOLD') < log.index('PrintFormat("[ManagePositionDecision]')
assert 'CLOSE' not in log.split('PrintFormat("[ManagePositionDecision]')[0] or 'action != "HOLD"' in log or 'action!="HOLD"' in log
print('hold decision suppression source assertions passed')
PY</automated>
    <automated>cd /d/Aureus && git diff --check -- mql5/AureusProvider_v2.mq5</automated>
  </verify>
  <done>`profile_fallback` and `legacy_no_rule_matched` repeated HOLD decision logs are suppressed per unique `symbol+magic+direction+reason`; all non-target logs remain emitted.</done>
</task>

<task type="auto">
  <name>Task 2: Verify source scope, compile availability, and GitNexus change scope</name>
  <files>D:/Aureus/mql5/AureusProvider_v2.mq5</files>
  <action>Run focused source assertions proving suppression is narrow. Check whether MetaEditor CLI exists before attempting compile. Run GitNexus detect changes before any commit if command/tool is available; if unavailable or command name differs, record exact failure and use `git diff --stat`, `git diff --check`, and targeted source assertions as fallback. Do not commit generated/untracked `mql5/AureusProvider_v2.ex5` or `stable/`.</action>
  <verify>
    <automated>cd /d/Aureus && python - <<'PY'
from pathlib import Path
s = Path('mql5/AureusProvider_v2.mq5').read_text(encoding='utf-8')
assert s.count('[ManagePositionDecision]') == 1, 'do not add alternate decision log format'
assert 'SetMarketClosedCloseGuard' in s and 'IsSymbolMarketClosedCloseGuardActive' in s, 'previous market-close guard must remain'
assert 'unknown_profile' in s, 'unknown profile warning must remain visible'
assert 'trade.PositionClose' in s, 'close path must remain present'
print('narrow logging scope assertions passed')
PY</automated>
    <automated>cd /d/Aureus && (command -v MetaEditor64.exe || command -v metaeditor64.exe || command -v MetaEditor.exe || command -v metaeditor.exe || true)</automated>
    <automated>cd /d/Aureus && (npx gitnexus detect_changes --scope all || npx gitnexus detect-changes --repo Aureus --scope all || true)</automated>
    <automated>cd /d/Aureus && git diff --stat -- mql5/AureusProvider_v2.mq5</automated>
  </verify>
  <done>Verification proves only provider MQL5 source changed for narrow HOLD log suppression; environment limitations are captured if GitNexus or MetaEditor cannot run.</done>
</task>

<task type="auto">
  <name>Task 3: Write execution summary</name>
  <files>D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md</files>
  <action>Create summary containing objective, exact files changed, behavior changed, verification commands/results, GitNexus impact/detect results or limitations, MetaEditor compile status, and explicit note that `CLOSE`, market-close first detection, close failure/error logs, and non-HOLD decisions were not suppressed.</action>
  <verify>
    <automated>cd /d/Aureus && test -f .planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md</automated>
  </verify>
  <done>Summary exists and gives future executors enough context to avoid reintroducing HOLD spam or hiding close/error logs.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| MT5 runtime to journal log | Internal runtime state becomes operator-visible logs; suppression must not hide safety-relevant actions. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-260503-NEG-01 | Repudiation | `LogManagementDecision` | mitigate | Suppress only repeated low-value HOLD reasons and preserve first log per key so decision still has trace. |
| T-260503-NEG-02 | Information Disclosure | MT5 journal | accept | Change reduces repeated operational noise; no new data exposure or external sink. |
| T-260503-NEG-03 | Denial of Service | MT5 journal/log IO | mitigate | Reduce repeated HOLD spam for profile fallback/no-rule paths, lowering log churn while market is closed or unmanaged. |
| T-260503-NEG-04 | Tampering | Close/error observability | mitigate | Do not suppress `CLOSE`, market-close detection, close failures, non-HOLD decisions, or errors. |
</threat_model>

<verification>
Overall required checks:
- Source assertions pass for targeted suppression.
- `git diff --check -- mql5/AureusProvider_v2.mq5` passes.
- GitNexus impact attempted before modifying `LogManagementDecision`; limitation documented if MQL5 symbol not indexed.
- GitNexus detect changes attempted before commit; limitation documented if command unavailable.
- MetaEditor compile attempted only if CLI exists; limitation documented if unavailable.
</verification>

<success_criteria>
- Repeated runtime HOLD logs with `reason=profile_fallback` no longer spam for same `symbol+magic+direction+reason`.
- Repeated runtime HOLD logs with `reason=legacy_no_rule_matched` no longer spam for same `symbol+magic+direction+reason`.
- First occurrence still visible for diagnostics.
- `CLOSE`, market-close detection, close failure/error logs, and non-HOLD decisions remain visible.
- Scope stays surgical: only `mql5/AureusProvider_v2.mq5` plus summary.
</success_criteria>

<output>
After completion, create `D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md`.
</output>
