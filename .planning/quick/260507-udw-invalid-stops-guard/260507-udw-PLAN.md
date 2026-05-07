---
quick_id: 260507-udw
phase: quick
plan: 260507-udw
type: quick-full
wave: 1
depends_on:
  - 260507-u2b
files_modified:
  - services/aureus-trader/order_builder.py
  - services/aureus-trader/tests/test_order_builder.py
  - .planning/quick/260507-udw-invalid-stops-guard/260507-udw-SUMMARY.md
  - .planning/quick/260507-udw-invalid-stops-guard/260507-udw-VERIFICATION.md
  - .planning/STATE.md
autonomous: true
status: planned
must_haves:
  truths:
    - Non-numeric object SL/TP must not be sent to MT5 as OPEN_ORDER payload.
    - Numeric int/float SL/TP path must remain unchanged.
    - Error must fail before socket dispatch path can produce INVALID_STOPS from object parsing.
  artifacts:
    - Minimal source fix in trader order builder/validation path.
    - Regression tests for object SL/TP rejection and numeric pass-through.
    - Summary and verification report.
    - STATE.md update.
  key_links:
    - STRATEGY_MATCH data.sl/tp -> build_order_command
    - build_order_command output -> dispatcher MT5 send
    - malformed SL/TP object -> rejected before provider numeric parser
---

# Quick Task 260507-udw Plan

## Goal

Fix theo suggest từ `260507-u2b`: chặn `sl`/`tp` không phải numeric trước khi dispatch sang MT5 để tránh `INVALID_STOPS` do object JSON bị MQL5 parse thành `0.0`.

<task type="auto">
  <name>Add numeric SL TP guard</name>
  <files>
    services/aureus-trader/order_builder.py
  </files>
  <action>
    Run GitNexus impact for `build_order_command`. Add minimal guard in `build_order_command()` so selected `sl` and `tp` must be real numbers, not dict/list/bool/string. Raise a clear `ValueError` with field name if invalid. Keep numeric output unchanged.
  </action>
  <verify>
    Existing order builder tests still pass for numeric SL/TP. New malformed object payload raises before returning command.
  </verify>
  <done>
    MT5 command builder cannot emit object SL/TP.
  </done>
</task>

<task type="auto">
  <name>Add regression tests</name>
  <files>
    services/aureus-trader/tests/test_order_builder.py
  </files>
  <action>
    Add focused tests: object `sl` rejected, object `tp` rejected, numeric `sl_absolute/tp_absolute` remains pass-through. Keep changes limited to current test class.
  </action>
  <verify>
    Run focused pytest for `test_order_builder.py`.
  </verify>
  <done>
    Regression covers previous bad payload shape.
  </done>
</task>

<task type="auto">
  <name>Verify and document</name>
  <files>
    .planning/quick/260507-udw-invalid-stops-guard/260507-udw-SUMMARY.md
    .planning/quick/260507-udw-invalid-stops-guard/260507-udw-VERIFICATION.md
    .planning/STATE.md
  </files>
  <action>
    Run focused tests, static diff check, GitNexus detect changes if available. Write summary, verification, and update STATE.md.
  </action>
  <verify>
    Artifacts record impact, tests, and scope. Verification status passed.
  </verify>
  <done>
    Quick task ready for commit.
  </done>
</task>
