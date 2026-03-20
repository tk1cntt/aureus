# Phase 1 Research — Signal ATR Optimization

## Context
Phase 1 tập trung vào `atr` trong milestone v1.1, với mục tiêu giữ nguyên trading intent nhưng tăng độ tin cậy integration và testability.

## Issues Discovered
1. Thiếu wiring: `atr_14` chưa được đăng ký đúng trong `create_signal_set(...)`.
2. Runtime test masking: có test patch factory output nên wiring sai vẫn pass.
3. Contract lệch schema: timestamp key runtime dùng `t`, test có chỗ assert `ts`.
4. Governance gap: thiếu rule chống xóa test case legacy khi refactor.

## Risks
- Regression im lặng nếu signal có logic đúng nhưng không được wire vào factory.
- False positive test nếu integration path bị mock sai tầng.
- Drift contract nếu test schema không bám runtime source-of-truth.

## Decisions
- Bắt buộc 3 tầng test cho signal integration: factory contract, helper integration, runtime-path integration.
- Anti-masking: không patch factory output cho chính signal đang verify.
- Legacy tests phải được giữ lại; chỉ chỉnh sửa để phù hợp runtime/contract mới.
