---
phase: 260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby
verified: 2026-05-17T00:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Quick 260517-sf2: Verification Report

**Task goal:** Phân tích hàm `ProcessLegacyPositionsByType` của `mql5/AureusProvider_v2.mq5`, làm rõ vì sao nhánh `positions_count == 1 && age_seconds > 1800 && net_profit > 0` close cả lệnh đang lời tốt, phân biệt 3 case sideway không có lợi nhuận, âm rồi hòa/chớm lời, lời tốt cần giữ, và đưa giải pháp xử lý.

**Verified:** 2026-05-17T00:00:00Z  
**Status:** passed  
**Re-verification:** Không — verification lần đầu.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Xác định rõ nhánh `ProcessLegacyPositionsByType` đóng lệnh single stale profit khi `positions_count == 1`, `age_seconds > 1800`, `net_profit > 0`. | VERIFIED | Source tại `mql5/AureusProvider_v2.mq5:2117-2119` có đúng điều kiện và gọi `ClosePositionTickets(..., "legacy_stale_profitable_single", "P-08")`. Report dòng 58-79 giải thích điều kiện và root cause. |
| 2 | Phân biệt được 3 case: sideway không có lợi nhuận, âm rồi hòa/chớm lời, và đang có lợi nhuận tốt cần giữ/không close sớm. | VERIFIED | Report dòng 81-106 có ma trận 3 trạng thái, dữ liệu hiện có, hạn chế snapshot, thiếu MFE/MAE, và hành động đề xuất cho từng case. |
| 3 | Đề xuất xử lý không sửa code vội; nếu cần fix, nêu điều kiện an toàn cụ thể để executor xin xác nhận trước khi edit. | VERIFIED | Report dòng 107-183 có 3 phương án, threshold `0 < net_profit < small_profit_threshold` / `< positions_count * InpBEProfitTarget / 2`, giữ hoặc `MovePositionsSL` khi `net_profit >= InpBEProfitTarget`, kết luận không implement và yêu cầu GitNexus impact trước edit. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-REPORT.md` | Báo cáo phân tích root cause, case classification, solution proposal; chứa `ProcessLegacyPositionsByType`. | VERIFIED | File tồn tại, substantive, tiếng Việt markdown, có GitNexus note, root cause, ma trận 3 case, solution proposal. |
| `.planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby/260517-sf2-SUMMARY.md` | Summary quick sau completion. | VERIFIED | File tồn tại, ghi task completed, source_files_modified: 0, GitNexus notes. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `mql5/AureusProvider_v2.mq5` | `260517-sf2-REPORT.md` | Trích line logic và luồng `ManagePositionProfitBreakEvent -> ProcessPositionsByType -> ProcessLegacyPositionsByType` | VERIFIED | Source xác nhận call chain tại `ProcessPositionsByType` và `ManagePositionProfitBreakEvent`; report dòng 23-40 ghi blast radius/source flow và reason `legacy_stale_profitable_single`. |
| `ProcessLegacyPositionsByType` | `ClosePositionTickets` | `legacy_stale_profitable_single` branch | VERIFIED | Source dòng 2117-2119 khớp report dòng 60-68. |
| `ProcessBreakoutProtectPositionsByType` | `MovePositionsSL` | alternative safe behavior | VERIFIED | Source dòng 2221-2225 khớp report dòng 77-78 và 137-144. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `260517-sf2-REPORT.md` | N/A | Static analysis report, không render dynamic data. | N/A | SKIPPED — report-only artifact. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Source chứa target function/branch và report chứa required terms. | Python assertion check against `mql5/AureusProvider_v2.mq5` and `260517-sf2-REPORT.md`. | Source assertions passed; one literal assertion for `không implement` failed because shell/Python encoding rendered Vietnamese as mojibake (`kh�ng implement`). Manual Read/Grep verified report dòng 179 contains `Không implement trong quick này`. | PASS WITH ENCODING NOTE |
| Source không bị sửa trong quick này. | `git -C "D:/Aureus" status --short -- "mql5/AureusProvider_v2.mq5" ".planning/quick/260517-sf2-ph-n-ti-ch-ha-m-processlegacypositionsby"` | Output chỉ shows quick directory untracked; no modified entry for `mql5/AureusProvider_v2.mq5`. | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| `QUICK-260517-SF2` | `260517-sf2-PLAN.md` | Analyze `ProcessLegacyPositionsByType` stale single profitable close behavior and propose safe handling. | SATISFIED | Report exists and covers source branch, call flow, 3-case classification, safe fix options, no source edit. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| N/A | N/A | No TODO/FIXME/placeholder/stub markers found in report. | Info | Không có blocker. |

### Human Verification Required

Không cần. Đây là quick phân tích/report-only; source branch và report content verified bằng đọc source và artifact.

### Gaps Summary

Không có gap. Goal đạt: report phân tích đúng root cause close sớm, phân biệt 3 trạng thái, nêu solution an toàn và không sửa source.

---

_Verified: 2026-05-17T00:00:00Z_  
_Verifier: Claude (gsd-verifier)_
