---
quick: 260425-lqo
plan: 01
type: summary
status: complete
completed_date: 2026-04-25
artifacts:
  - .planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-ARCHITECTURE-ADVISORY.md
  - .planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/260425-lqo-REQUIREMENTS.md
source:
  - .planning/quick/260425-kwd-ph-n-t-ch-h-m-classify-shape-t-m-quan-tr/260425-kwd-REPORT.md
---

# Summary quick 260425-lqo

Quick task này là planning-only: chỉ tạo tài liệu tư vấn kiến trúc và tài liệu yêu cầu/kiểm thử cho hướng cải thiện `_classify_shape` / TPO shape. Không có production code, tests, migrations, runtime config, database schema hoặc dữ liệu runtime nào bị thay đổi.

## Artifact đã tạo

1. `260425-lqo-ARCHITECTURE-ADVISORY.md`
   - Viết advisory 4 bước theo yêu cầu: Neutral Listing, Attribute Mapping, Contextual Recommendation, Adversarial Mode.
   - Bám trực tiếp vào `260425-kwd-REPORT.md`.
   - Kết luận `Suggested best choice`: chọn lộ trình calibrated deterministic heuristic + maturity/data-quality gate trước, dùng detector context và replay/backtest calibration làm lớp xác nhận trước khi dùng shape cho scoring.

2. `260425-lqo-REQUIREMENTS.md`
   - Chuyển khuyến nghị thành yêu cầu thực thi và kiểm thử sau này.
   - Có Decision Summary, In Scope, Out of Scope / Do Not Do, Acceptance Criteria, Test Basis và Traceability.
   - Nhấn mạnh không coi `shape_confidence_pct` là xác suất thật khi chưa calibrate; không dùng ML ngay; không đưa shape vào scoring trước replay/backtest.

## Quyết định kiến trúc được ghi nhận

Lựa chọn tốt nhất là cải thiện `_classify_shape` theo hướng deterministic và explainable:

- Bổ sung calibrated heuristic metrics cho D/B/p/b.
- Thêm peak separation + valley depth cho B-shape.
- Thêm maturity/data-quality gate cho sparse/current bucket.
- Tính confidence theo top-1/top-2 margin và data quality thay vì chỉ normalized score.
- Dùng TPO detector context như confirmation layer.
- Bắt buộc replay/backtest trước khi dùng shape cho strategy scoring.

## Yêu cầu và test basis đã ghi nhận

Requirements document đã ghi các nhóm kiểm thử sau:

- Unit fixture cho D/B/p/b.
- Edge tests cho sparse, empty/zero counts, outlier/wick, tick_size sensitivity, equal peaks, flat profile.
- Integration tests với indicator snapshot và Telegram rendering.
- Replay metrics gồm flip rate và confidence distribution.
- A/B backtest nếu future implementation dùng shape cho scoring.

## Deviations from Plan

Không có deviation về nội dung. Plan được thực hiện đúng phạm vi planning-only.

## Giới hạn công cụ

GitNexus MCP tools không khả dụng trong agent này, nên không thể chạy `gitnexus_detect_changes()` trực tiếp trước commit. Vì constraint yêu cầu không commit docs artifacts, không có commit nào được tạo trong quick task này. Phạm vi thay đổi được kiểm tra bằng `git -C "D:/Aureus" status --short` và chỉ thấy thư mục planning quick 260425-lqo là untracked.

## Xác nhận planning-only

- Không có production code bị sửa.
- Không có test code bị sửa.
- Không có migration/database schema bị sửa.
- Không có runtime config bị sửa.
- Chỉ có artifact trong `.planning/quick/260425-lqo-d-a-va-o-report-na-y-planning-quick-2604/` được tạo.

## Self-Check: PASSED

- `260425-lqo-ARCHITECTURE-ADVISORY.md`: tồn tại và có đủ 4 bước cùng `Suggested best choice`.
- `260425-lqo-REQUIREMENTS.md`: tồn tại và có đủ Decision Summary, In Scope, Out of Scope, Acceptance Criteria, Test Basis, Traceability.
- `260425-lqo-SUMMARY.md`: tồn tại và xác nhận planning-only, không có production code/database/schema thay đổi.
