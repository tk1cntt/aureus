---
quick_id: 260507-vmj
phase: quick
plan: 260507-vmj
type: quick-full
wave: 1
depends_on:
  - 260507-udw
files_modified:
  - .planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-SUMMARY.md
  - .planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-VERIFICATION.md
  - .planning/STATE.md
autonomous: true
status: planned
must_haves:
  truths:
    - Analyze ACK_LOST_DUPLICATE_RECOVERY incident from trader logs in detail.
    - Identify likely execution sequence and root cause without changing code.
    - State whether INVALID_STOPS retcode 10016 recurred in observed window.
  artifacts:
    - Report-only summary with log timeline, affected order, suspected root cause, and next fix recommendation.
    - Verification report validating findings against logs and code paths.
    - STATE.md update.
  key_links:
    - trader log order ord-4fd96f27887e -> dispatcher retry path
    - ACK timeout -> retry publish -> late ACK/ORDER_OPENED/NACK
    - dispatcher pending state -> RECONCILE_NEEDED
---

# Quick Task 260507-vmj Plan

## Goal

Phân tích chi tiết lỗi `ACK_LOST_DUPLICATE_RECOVERY` vừa thấy khi monitor `aureus-trader-dev`, tập trung vào order `ord-4fd96f27887e` BTCUSD SELL. Chỉ report, không sửa code.

<task type="auto">
  <name>Collect incident evidence</name>
  <files>
    services/aureus-trader/dispatcher.py
    services/aureus-trader/order_builder.py
    mql5/AureusProvider_v2.mq5
  </files>
  <action>
    Read recent trader logs via `docker logs --since 10m aureus-trader-dev 2>&1` and relevant dispatcher/provider code. Capture exact timeline for `ord-4fd96f27887e`, including publish, ACK timeout, retry, late events, and RECONCILE_NEEDED. Also check same observed window for `INVALID_STOPS` and `retcode 10016`.
  </action>
  <verify>
    Evidence includes exact log lines, affected cmd_id/symbol/lane, and explicit conclusion about whether `INVALID_STOPS`/`10016` recurred.
  </verify>
  <done>
    Incident sequence reconstructed.
  </done>
</task>

<task type="auto">
  <name>Analyze root cause and impact</name>
  <files>
    services/aureus-trader/dispatcher.py
    services/aureus-trader/journal.py
    mql5/AureusProvider_v2.mq5
  </files>
  <action>
    Trace how dispatcher handles pending commands, retry, ACK/ORDER_OPENED/NACK matching, and duplicate recovery. Determine likely cause, whether order may have opened, and if DB/journal impact exists.
  </action>
  <verify>
    Report distinguishes confirmed facts from hypotheses and lists risk level.
  </verify>
  <done>
    Root cause hypothesis and impact stated.
  </done>
</task>

<task type="auto">
  <name>Document and verify report</name>
  <files>
    .planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-SUMMARY.md
    .planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-VERIFICATION.md
    .planning/STATE.md
  </files>
  <action>
    Write summary and verification artifacts, update STATE.md quick table, commit docs-only analysis.
  </action>
  <verify>
    Artifacts contain conclusion and recommended next fix path. No source code modified. Commit hash recorded in final response.
  </verify>
  <done>
    Quick analysis ready and committed.
  </done>
</task>
