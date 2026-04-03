# Phase 15.6: Update Sweep Rules + Sentiment Mapping - Research

## Objective
Chuẩn hóa tài liệu kỹ thuật cho Phase 15.6, tập trung vào sweep lifecycle rules, phân tích warning `missing origin_timestamp`, và ranh giới giữa AI trigger mapping với AI sentiment output.

## Scope Constraints
- Không thay đổi runtime behavior ngoài phạm vi phase đã chốt.
- Không đổi thuật toán core OB/FVG/CHOCH/BOS.
- Không đổi logic sentiment runtime (giữ output từ AI pulse).
- Tài liệu phải phản ánh đúng kết quả đã có trong `CONTEXT/SUMMARY/UAT`.

## Key Technical Findings
- `SweepSignal.calculate` đang dùng mitigation-age gate: `0 < (c_t - t_mitigation) <= 300`.
- Sweep lifecycle đã đồng bộ naming canonical (`CLEAN_BREAKOUT`, `sweep_broken_pending_*`, `sweep_touched_*`, `stop_hunt_*`).
- `missing origin_timestamp` đã được chốt ở mức root-cause analysis (không mở rộng fix trong phase 15.6).
- `_AI_TAG_TO_TRIGGER` là mapping trigger/context, không remap `analysis['sentiment']`.
- Logging hot-reload đã được ghi nhận hoàn tất trong phase artifacts.

## Chosen Approach
1. Đồng bộ bộ tài liệu phase 15.6 theo mẫu đầy đủ (PLAN/SUMMARY/CONTEXT/RESEARCH/UAT/VALIDATION).
2. Giữ phạm vi documentation-sync; không thêm runtime feature mới.
3. Dùng bằng chứng đã có từ `15.6-01-SUMMARY.md` và `15.6-UAT.md` để lập validation sign-off.

## Research Outcome
- Phase 15.6 đã có đủ quyết định kỹ thuật và bằng chứng UAT để đóng report thiếu.
- Hai report `RESEARCH` và `VALIDATION` có thể bổ sung ngay mà không phát sinh thay đổi code.
- Global health của `.planning` vẫn có cảnh báo khác phase (ngoài phạm vi 15.6).
