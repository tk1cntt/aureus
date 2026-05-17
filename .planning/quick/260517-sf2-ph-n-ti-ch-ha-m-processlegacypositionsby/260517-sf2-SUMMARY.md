---
phase: 260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby
plan: 01
subsystem: mql5-position-management-analysis
tags: [quick, report-only, mql5, legacy-position-management]
key-files:
  created:
    - .planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-REPORT.md
    - .planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-SUMMARY.md
  modified: []
decisions:
  - Không sửa source trong quick này; chỉ phân tích root cause và đề xuất điều kiện fix an toàn.
  - Legacy single stale profitable hiện close mọi lệnh single quá 30 phút có net_profit dương, kể cả lời tốt.
metrics:
  completed_date: 2026-05-17
  tasks_completed: 3
  source_files_modified: 0
---

# Quick 260517-sf2: Phân tích `ProcessLegacyPositionsByType` Summary

Phân tích root cause nhánh `legacy_stale_profitable_single` close sớm lệnh single đang lời tốt vì điều kiện `net_profit > 0` quá rộng và chưa phân biệt sideway, hồi hòa, lời tốt.

## Tasks Completed

| Task | Kết quả | Verification |
|---|---|---|
| Task 1: Trace logic hiện tại và root cause close nhầm | Đã xác nhận luồng `ManagePositionProfitBreakEvent -> ProcessPositionsByType -> ProcessLegacyPositionsByType -> ClosePositionTickets` và root cause `positions_count == 1 && age_seconds > 1800 && net_profit > 0`. | `ok` |
| Task 2: Phân loại 3 trạng thái cần nhận dạng | Đã lập ma trận sideway không lợi nhuận, âm rồi hồi hòa/chớm lời, lời tốt cần giữ; nêu thiếu MFE/MAE. | `ok` |
| Task 3: Đề xuất solution an toàn và tiêu chí fix nếu được duyệt | Đã đề xuất threshold an toàn, hướng `MovePositionsSL`, và yêu cầu GitNexus impact trước edit plan sau. | `ok` |

## Deviations from Plan

None - plan executed as report-only. Không sửa `mql5/AureusProvider_v2.mq5`.

## GitNexus Notes

- `npx gitnexus context ProcessLegacyPositionsByType --repo Aureus` trả `Symbol 'ProcessLegacyPositionsByType' not found`.
- `npx gitnexus query "legacy_stale_profitable_single ProcessLegacyPositionsByType" --repo Aureus` không trả process/symbol liên quan cho MQL5.
- Vì GitNexus chưa index symbol MQL5 này, report ghi rõ kết quả và xác nhận flow bằng đọc source trực tiếp.

## Verification

- Task 1 automated check: passed.
- Task 2 automated check: passed.
- Task 3 automated check: passed.
- Source code changes: none intended.

## Known Stubs

None.

## Threat Flags

None. Không tạo endpoint, auth path, file access runtime, schema change, hoặc trust boundary mới.

## Self-Check: PASSED

- Report exists: `.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-REPORT.md`.
- Summary exists: `.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-SUMMARY.md`.
- No source file edited for quick này.
