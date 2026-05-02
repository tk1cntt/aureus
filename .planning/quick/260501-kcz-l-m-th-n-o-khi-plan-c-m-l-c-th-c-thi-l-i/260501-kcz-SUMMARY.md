---
phase: quick-260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i
plan: 01
subsystem: mt5-provider-position-management-planning
tags: [planning, checklist, anti-lack, mql5, position-management]
dependency_graph:
  requires:
    - D:/Aureus/.planning/quick/260501-i1p-tri-n-khai-strategy-aware-position-manag/260501-i1p-SUMMARY.md
    - D:/Aureus/mql5/AureusProvider_v2.mq5
    - D:/Aureus/mql5/CISD_Slope_EA_v6.39_Final.mq5
  provides:
    - anti-lack-implementation-checklist
    - old-behavior-coverage-matrix
  affects:
    - future-strategy-aware-position-management-refactor
tech_stack:
  added: []
  patterns: [coverage-matrix, rule-primitives, profile-checklists, anti-lack-gate]
key_files:
  created:
    - D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md
    - D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-SUMMARY.md
  modified: []
decisions:
  - "Giữ quick này ở phạm vi documentation/planning; không sửa MQL5 source và không sửa ROADMAP.md."
metrics:
  completed_date: 2026-05-01T07:45:09Z
  tasks_completed: 1
---

# Quick 260501-kcz: Anti-Lack Implementation Checklist Summary

## Tóm tắt

Đã tạo checklist chống thiếu implementation cho strategy-aware position management: kiểm kê behavior cũ, map sang rule primitive, map sang từng profile, checklist function-level, verification matrix, và anti-lack gate bắt buộc không để item trống.

## Thay đổi chính

- Tạo artifact `D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md`.
- Bổ sung diagnosis vì sao quick `260501-i1p` vẫn có rủi ro partial execution dù plan đúng hướng.
- Kiểm kê old behavior từ `ManagePositionProfitBreakEvent()`, `ProcessPositionsByType()`, và `ManagePositionByHistory()` trong reference EA.
- Định nghĩa 20 rule primitives, gồm grouping, resolver, audit log, severe guard, basket escape, stale single policy, cost-aware SL, history cooldown, signal cooldown side-effect, command non-regression, và cycle risk telemetry.
- Tạo **Old behavior/rule coverage matrix** với 30 behavior rows, mỗi row có primitive, profile disposition, verification checklist, và cột final mark.
- Tạo per-profile checklist cho `conservative`, `trend_runner`, `breakout_protect`, `basket_escape`.
- Tạo function-level checklist cho resolver, logging, grouping, processing, history cooldown helpers, và non-regression functions.
- Tạo verification matrix và **Anti-lack gate**: implementation sau không complete nếu còn item chưa check hoặc chưa deferred có rationale.

## Verification

- Đã chạy automated check:
  - file checklist tồn tại.
  - có chuỗi `Old behavior/rule coverage matrix`.
  - có chuỗi `Anti-lack gate`.
- Xác nhận không sửa MQL5 source trong quick task này.
- Xác nhận không sửa database files.
- Xác nhận không update ROADMAP.md theo constraint.

## Deviations from Plan

None - plan executed exactly as written.

## Auth Gates

Không có.

## Known Stubs

Không có stub làm hỏng mục tiêu plan. Các ô checklist `[ ]` trong artifact là chủ ý vì đây là template/gate cho executor sau điền khi implement code.

## Threat Flags

Không có threat surface runtime mới; quick task chỉ tạo planning artifact.

## Commits

- `1576fb6`: `docs(quick-260501-kcz): add anti-lack implementation checklist`

## Self-Check: PASSED

- Checklist tồn tại: `D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-IMPLEMENTATION-CHECKLIST.md`.
- Summary tồn tại: `D:/Aureus/.planning/quick/260501-kcz-l-m-th-n-o-khi-plan-c-m-l-c-th-c-thi-l-i/260501-kcz-SUMMARY.md`.
- Task commit tồn tại: `1576fb6`.
