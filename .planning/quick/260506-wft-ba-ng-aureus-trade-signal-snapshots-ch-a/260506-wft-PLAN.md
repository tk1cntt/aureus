---
quick_id: 260506-wft
mode: quick-full
status: planned
must_haves:
  truths:
    - aureus_trade_signal_snapshots.session must be persisted non-null when source signal/session data exists.
    - Database-related change must be verified with DB/e2e data creation.
  artifacts:
    - Source fix for session mapping/persistence path.
    - Regression test covering non-null session in aureus_trade_signal_snapshots.
    - Executor summary.
    - Verification report.
  key_links:
    - .planning/STATE.md
---

# Quick Task 260506-wft Plan

## Goal

Fix `aureus_trade_signal_snapshots.session` being saved as null by wiring existing session value into trade signal snapshot persistence, then prove with database/e2e verification that created snapshot rows contain non-null `session`.

## Tasks

### Task 1 — Locate session persistence gap and patch mapping

- **files**: To be discovered in journal/signal snapshot persistence path, likely `services/aureus-signal/**/journal*.py` or related trade snapshot code.
- **action**: Use GitNexus query/context to identify `aureus_trade_signal_snapshots` write path. Before editing modified symbols, run `gitnexus_impact({target: "<symbol>", direction: "upstream"})` and report direct callers, affected processes, risk. Patch only mapping needed so existing session source flows into `session` column.
- **verify**: Static check shows insert/upsert payload includes `session` with source value, not omitted/null fallback.
- **done**: Code path saving trade signal snapshot passes `session` from source snapshot/event when available.

### Task 2 — Add focused regression coverage

- **files**: Existing tests near journal/trade signal snapshot persistence.
- **action**: Add/adjust test that builds source signal/session data and asserts persisted `aureus_trade_signal_snapshots.session` is non-null and equals expected session.
- **verify**: Run targeted test.
- **done**: Test fails before fix or would catch omitted session mapping; passes after fix.

### Task 3 — Run DB/e2e verification and commit code

- **files**: Source/test files changed above.
- **action**: Run DB/e2e command per repo conventions (read `RUN_SERVICES.md` if command fails). Create data proving `aureus_trade_signal_snapshots.session` non-null. Run `gitnexus_detect_changes()` before commit. Commit code changes atomically.
- **verify**: Query/test output confirms row created with non-null `session`; git commit succeeds.
- **done**: Code committed; summary written to `.planning/quick/260506-wft-ba-ng-aureus-trade-signal-snapshots-ch-a/260506-wft-SUMMARY.md`.
