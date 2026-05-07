---
quick_id: 260507-tau
phase: quick
plan: 260507-tau
type: quick-full
wave: 1
depends_on: []
files_modified:
  - mql5/AureusProvider_v2.mq5
  - services/**
  - .planning/quick/260507-tau-pending-fill-update/260507-tau-SUMMARY.md
  - .planning/quick/260507-tau-pending-fill-update/260507-tau-VERIFICATION.md
  - .planning/STATE.md
autonomous: true
status: planned
must_haves:
  truths:
    - Determine whether pending orders filled in `mql5/AureusProvider_v2.mq5` send a fill notification to gateway.
    - Determine whether backend gateway/trader flow updates DB fields for pending fill linkage.
    - If missing, add minimal update so pending fill notification carries identifiers needed for DB update.
    - DB/e2e verification proves a real journal/trade row can be updated from pending fill event.
  artifacts:
    - Source investigation/fix if needed.
    - Focused tests or static verification if MQL5 cannot run in CI.
    - DB/e2e proof output for pending fill update path.
    - Summary and verification report.
    - STATE.md update.
  key_links:
    - MT5 pending fill detection -> gateway event payload
    - gateway event payload -> trader/journal DB update path
    - DB/e2e proof -> updated pending/fill fields in real DB row
---

# Quick Task 260507-tau Plan

## Goal

Kiểm tra `mql5/AureusProvider_v2.mq5`: lệnh pending khi được fill có gửi thông báo về gateway không, backend có update thông tin vào DB không. Nếu chưa có, cập nhật tối thiểu.

<task type="auto">
  <name>Trace pending fill flow</name>
  <files>
    mql5/AureusProvider_v2.mq5
    services/aureus-gateway/**
    services/aureus-trader/**
  </files>
  <action>
    Use GitNexus query for pending fill/order lifecycle, then impact before editing any symbol. Inspect MT5 transaction handlers and backend event consumers. Identify event names and fields for pending placed/fill update.
  </action>
  <verify>
    Summary states exact current behavior: whether MT5 sends event, whether gateway receives it, whether DB update path exists.
  </verify>
  <done>
    Gap known with exact file/function symbols.
  </done>
</task>

<task type="auto">
  <name>Patch missing pending fill update path</name>
  <files>
    mql5/AureusProvider_v2.mq5
    services/aureus-gateway/**
    services/aureus-trader/**
  </files>
  <action>
    If missing, add minimal payload/event handling so pending fills produce a backend event with enough identifiers (`pending_order_id`, ticket/deal/position, symbol, magic, direction, fill price/time). Update backend DB path only if event is not already handled.
  </action>
  <verify>
    Diff only touches required flow. Any edited symbols have GitNexus impact recorded.
  </verify>
  <done>
    Pending fill event can update DB linkage.
  </done>
</task>

<task type="auto">
  <name>Verify tests and DB/e2e proof</name>
  <files>
    changed tests/scripts
    runtime DB
    .planning/quick/260507-tau-pending-fill-update/260507-tau-SUMMARY.md
    .planning/quick/260507-tau-pending-fill-update/260507-tau-VERIFICATION.md
    .planning/STATE.md
  </files>
  <action>
    Run focused tests for backend handler if available. For MQL5, document static compile-limited verification if compiler unavailable. Run DB/e2e through WSL/TimescaleDB proving pending fill fields can update a real row. Write summary, verification, update STATE.md.
  </action>
  <verify>
    Test output and DB query output captured. Verification status passed or human_needed only for MT5 compile/manual runtime if unavailable.
  </verify>
  <done>
    Artifacts complete and ready for commit.
  </done>
</task>
