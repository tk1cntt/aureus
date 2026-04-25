# Quick Task 260425-kwd Summary

## Objective

Phân tích hàm `_classify_shape`, vai trò của nó trong TPO pipeline, rủi ro hiện tại và 3-4 hướng cải thiện khả thi, chỉ tạo tài liệu phân tích và không sửa production code.

## Scope completed

- Tạo report tại `D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md`.
- Xác định `_classify_shape` nằm tại `D:/Aureus/services/aureus-signal/engine/signals/tpo.py:122-170`.
- Trace call path chính:
  - `TPOSignal.calculate` tạo `tpo_d1/tpo_h1/tpo_m30` và lưu `state_obj.tpo_profile`.
  - `_build_tpo_block` gọi `_classify_shape` và trả `shape`, `shape_confidence_pct`, `shape_scores_pct`.
  - `build_indicator_snapshot_for_telegram` đưa TPO blocks vào indicator snapshot.
  - Telegram formatter render `Shape:<D|B|p|b> (<confidence>%)` trong SIGNAL ALERT.
- Phân tích strategy context:
  - `strategy_executor.py` attach `indicator_snapshot` vào strategy result.
  - `signal_event_publisher.py` hiện chưa flatten TPO shape vào `signal_snapshot`, nên chưa có bằng chứng shape đang trực tiếp làm strategy scoring input.
- Nêu điểm yếu có evidence từ source code: confidence chưa calibrate, threshold brittle, peak detection chưa kiểm tra valley/separation, sparse current sessions, tick-size/binning sensitivity, wick/outlier sensitivity, UTC D1 semantic, thiếu unknown/insufficient-data state.
- Đề xuất 4 hướng cải thiện:
  1. Calibrated heuristic với distribution metrics rõ hơn.
  2. Multi-session/timeframe context và maturity gating.
  3. Rule-based hybrid với TPO detector outputs.
  4. Offline labeled replay/backtest calibration.

## Verification

- `test -f D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md` passed.
- Report chứa `Improvement Approaches` và `_classify_shape`.
- Report dài 432 dòng, vượt yêu cầu tối thiểu 80 dòng.
- `git -C D:/Aureus status --short` chỉ thấy quick directory mới trong `.planning/quick/260425-kwd...`; không có production source/test/migration/runtime config thay đổi.
- Có thử chạy `npx gitnexus detect_changes` / `detect-changes`; CLI trong môi trường không trả output hữu ích, nên phạm vi được kiểm soát bằng đọc source + `git status`/artifact path.

## Deviations from Plan

None - plan executed as analysis/report only. Không production code changes, không commit source changes.

## Known Stubs

None. Report là artifact phân tích, không chứa stub runtime.

## Threat Flags

None. Không thêm endpoint, auth path, file access runtime, schema hoặc trust boundary production mới.

## Commits

Không tạo commit theo constraint của user: report-only quick task và orchestrator xử lý docs commit ở Step 8.

## Self-Check: PASSED

- Report exists: `D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md`.
- Summary exists: `D:/Aureus/.planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-SUMMARY.md`.
- Production source changes: none detected by root git status.
