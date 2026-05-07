---
quick_id: 260507-rrs
phase: quick
plan: 260507-rrs
type: quick-full
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260507-rrs-d1-tpo-snapshot-check/260507-rrs-SUMMARY.md
  - .planning/quick/260507-rrs-d1-tpo-snapshot-check/260507-rrs-VERIFICATION.md
  - .planning/STATE.md
autonomous: true
status: planned
must_haves:
  truths:
    - Determine whether D1 POC/VAL/VAH source values exist before snapshot persistence.
    - Determine why latest `aureus_trade_signal_snapshots` rows do or do not have D1 POC/VAL/VAH values.
    - Produce DB-backed evidence from real rows and exact source field mapping.
  artifacts:
    - Investigation summary.
    - Verification report.
    - STATE.md update.
  key_links:
    - source snapshot payload -> `_build_signal_snapshot_columns` D1 TPO mapping
    - `_build_signal_snapshot_columns` -> `aureus_trade_signal_snapshots.d1_poc/d1_vah/d1_val`
    - DB query -> real latest snapshot rows with D1 TPO values/nulls
---

# Quick Task 260507-rrs Plan

## Goal

Kiểm tra vì sao dữ liệu `POC/VAL/VAH` của D1 chưa được lưu vào bảng snapshots, và xác nhận dữ liệu đầu vào đã có hay chưa.

<task type="auto">
  <name>Inspect source mapping and blast radius</name>
  <files>
    services/aureus-trader/journal.py
    services/aureus-signal/**
  </files>
  <action>
    Run GitNexus debug flow first: `gitnexus_query` for D1 POC VAL VAH snapshot persistence, then `gitnexus_context`/`gitnexus_impact` for `_build_signal_snapshot_columns` if symbol context is needed. No code edits expected. Confirm exact D1 TPO source keys accepted by `_build_signal_snapshot_columns` and insert destination columns.
  </action>
  <verify>
    Report exact key mapping and whether code path can persist values if input exists.
  </verify>
  <done>
    Mapping contract documented in SUMMARY.md.
  </done>
</task>

<task type="auto">
  <name>Query real DB snapshot and journal rows</name>
  <files>
    runtime DB: aureus_trade_signal_snapshots, aureus_trade_journal
  </files>
  <action>
    Through WSL/TimescaleDB, query latest `aureus_trade_signal_snapshots` rows for `d1_poc/d1_vah/d1_val`, join journal where useful, and check rows around today/latest trades.
  </action>
  <verify>
    DB output shows count/null rates and sample rows.
  </verify>
  <done>
    Evidence shows whether snapshots are missing D1 TPO because input missing, schema missing, or persistence path failing.
  </done>
</task>

<task type="auto">
  <name>Check upstream input availability and update artifacts</name>
  <files>
    runtime DB/logs/source payload evidence
    .planning/quick/260507-rrs-d1-tpo-snapshot-check/260507-rrs-SUMMARY.md
    .planning/quick/260507-rrs-d1-tpo-snapshot-check/260507-rrs-VERIFICATION.md
    .planning/STATE.md
  </files>
  <action>
    Inspect likely upstream signal/indicator payload source and logs or DB fields to see whether D1 TPO values exist before trader snapshot write. Write SUMMARY.md, VERIFICATION.md, and update STATE.md quick task row.
  </action>
  <verify>
    Evidence names upstream field(s) present or absent. STATE.md has `260507-rrs` row.
  </verify>
  <done>
    Root cause stated with confidence and next fix if needed; artifacts created and STATE.md updated.
  </done>
</task>
