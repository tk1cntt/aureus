---
phase: 260425-duy-xoa-trade-evaluations
plan: 01
subsystem: trader-runtime-schema
tags: [quick, database, journal, signal-snapshot]
requires: []
provides:
  - Runtime không còn tạo/ghi bảng aureus_trade_evaluations
  - ORDER_OPENED vẫn update aureus_trade_journal và insert aureus_trade_signal_snapshots
affects:
  - services/aureus-db-writer/migrations/add_trade_evaluations.sql
  - services/aureus-trader/journal.py
  - services/aureus-trader/recompute_evaluations.py
  - services/aureus-trader/tests
  - services/aureus-db-writer/tests
  - services/aureus-trader/scripts/verify_phase55_runtime_evidence.py
  - docs/system-design-strategy-trigger-data-flow.md
  - RUN_SERVICES.md
  - scripts/dev-service.sh
tech-stack:
  patterns: [asyncpg, pytest, TimescaleDB]
key-files:
  modified:
    - services/aureus-db-writer/migrations/add_trade_evaluations.sql
    - services/aureus-trader/journal.py
    - services/aureus-trader/recompute_evaluations.py
    - services/aureus-db-writer/tests/test_evaluation_migration.py
    - services/aureus-trader/tests/test_evaluation_pipeline.py
    - services/aureus-trader/tests/test_evaluation_recompute.py
    - services/aureus-trader/tests/test_signal_snapshot_pipeline.py
    - services/aureus-trader/tests/test_signal_snapshot_recompute.py
    - services/aureus-trader/scripts/verify_phase55_runtime_evidence.py
    - docs/system-design-strategy-trigger-data-flow.md
    - RUN_SERVICES.md
    - scripts/dev-service.sh
    - .planning/REQUIREMENTS.md
decisions:
  - Giữ file recompute_evaluations.py nhưng chuyển vai trò còn lại sang backfill signal snapshots để tránh xóa nhầm đường dẫn runtime đang dùng.
  - DB dev chỉ chạy DROP TABLE IF EXISTS aureus_trade_evaluations; không drop bảng khác.
metrics:
  tasks_completed: 3
  completed_at: 2026-04-25T00:00:00Z
---

# Quick 260425-duy Summary: Xóa bảng aureus_trade_evaluations

Đã loại bỏ bảng `aureus_trade_evaluations` khỏi runtime schema/source/tests/docs hiện hành, đồng thời giữ nguyên luồng `ORDER_OPENED` cập nhật `aureus_trade_journal` và persist `aureus_trade_signal_snapshots`.

## Kết quả theo task

| Task | Trạng thái | Commit | Nội dung chính |
|---|---|---|---|
| 1 | Hoàn tất | b33e165 | Xóa schema bảng evaluations khỏi migration, xóa insert path trong `on_order_opened`, strip recompute khỏi read/write evaluations, cập nhật tests runtime liên quan. |
| 2 | Hoàn tất | fde8984 | Cập nhật verification script, RUN_SERVICES, dev-service, docs design và requirements để không còn yêu cầu bảng evaluations. |
| 3 | Hoàn tất | Không có code commit riêng | Chạy full test suite liên quan, DB verification và GitNexus detect_changes fallback. |

## Thay đổi chính

- `services/aureus-db-writer/migrations/add_trade_evaluations.sql` chỉ còn schema/index cho `aureus_trade_signal_snapshots`, không tạo `aureus_trade_evaluations`.
- `TradeJournalManager.on_order_opened` không còn validate scoring core fields hay insert evaluation row; transaction vẫn update journal và insert snapshot.
- `services/aureus-trader/recompute_evaluations.py` không còn query/insert/update bảng evaluations; phần còn lại chỉ backfill signal snapshots.
- Active tests được chuyển sang assert không có evaluation insert và retained snapshot path vẫn hoạt động.
- Active verification/docs không còn yêu cầu row hoặc table evaluations; script runtime evidence kiểm tra bảng evaluations đã bị xóa không tồn tại.

## GitNexus blast radius

- `npx gitnexus query --repo Aureus "aureus_trade_evaluations journal evaluation recompute"`: tìm thấy các process/symbol liên quan trong recompute, journal tests, evaluation tests và signal snapshot tests.
- `npx gitnexus impact --repo Aureus on_order_opened --direction upstream`: `impactedCount=0`, risk `LOW`, không có direct callers trong graph.
- `npx gitnexus impact --repo Aureus recompute_batch --direction upstream`: `impactedCount=3`, risk `CRITICAL`; direct caller `_run`, transitive `main`, affected module `Aureus-trader`. Đã không xóa file/hàm để tránh phá CLI path, chỉ strip evaluation table access.
- `npx gitnexus detect_changes --repo Aureus` và `npx gitnexus detect-changes --repo Aureus`: CLI hiện tại báo `unknown command`; fallback dùng `git status`, test suite, active-reference scan và DB verification.

## Verification

### Unit/integration tests

- `python -m pytest D:/Aureus/services/aureus-db-writer/tests/test_evaluation_migration.py D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_pipeline.py D:/Aureus/services/aureus-trader/tests/test_signal_snapshot_recompute.py -x`
  - Kết quả: `13 passed, 1 skipped`.
- `python -m pytest D:/Aureus/services/aureus-trader/tests/test_evaluation_pipeline.py D:/Aureus/services/aureus-trader/tests/test_evaluation_recompute.py -x`
  - Kết quả: `6 passed`.
- `python -m pytest D:/Aureus/services/aureus-trader/tests -x`
  - Kết quả: `142 passed, 1 skipped`.
- `python -m pytest D:/Aureus/services/aureus-trader/tests D:/Aureus/services/aureus-db-writer/tests -x`
  - Kết quả: `240 passed, 1 skipped`.

### Active reference scan

- Scan active repo excluding `.planning/quick`, `.planning/phases`, `.planning/milestones`, `.planning/archive`, `.venv`, `node_modules`.
- Cho phép 2 reference chủ đích trong:
  - `services/aureus-trader/scripts/verify_phase55_runtime_evidence.py` để assert removed table absent.
  - `services/aureus-db-writer/tests/test_evaluation_migration.py` để assert migration không chứa removed table.
- Kết quả: `active references clean`.

### DB/E2E verification

- Ban đầu DB dev vẫn còn bảng cũ:
  - `SELECT tablename ... tablename = 'aureus_trade_evaluations';` trả 1 row.
- Đã chạy destructive action giới hạn đúng plan:
  - `DROP TABLE IF EXISTS aureus_trade_evaluations;`
- Verify sau drop:
  - `SELECT tablename ... tablename = 'aureus_trade_evaluations';` trả 0 row.
  - `SELECT tablename ... IN ('aureus_trade_journal','aureus_trade_signal_snapshots') ORDER BY tablename;` trả đủ `aureus_trade_journal` và `aureus_trade_signal_snapshots`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical verification update] Active scan cần loại trừ reference chủ đích**
- **Found during:** Task 2
- **Issue:** Plan yêu cầu active scan không còn references nhưng hai file active cần giữ tên bảng để assert absence.
- **Fix:** Scan verification cho phép đúng hai file chủ đích; docs summary ghi rõ lý do.
- **Files modified:** `services/aureus-trader/scripts/verify_phase55_runtime_evidence.py`, `services/aureus-db-writer/tests/test_evaluation_migration.py`
- **Commit:** fde8984 / b33e165

**2. [Rule 3 - Blocking verification issue] DB dev còn bảng lịch sử**
- **Found during:** Task 3
- **Issue:** TimescaleDB dev vẫn còn `aureus_trade_evaluations` từ migration cũ.
- **Fix:** Chạy `DROP TABLE IF EXISTS aureus_trade_evaluations` theo đúng giới hạn trong plan, verify retained tables vẫn tồn tại.
- **Files modified:** Không có.
- **Commit:** N/A

## Known Stubs

Không phát hiện stub mới trong các file đã chỉnh.

## Threat Flags

Không có threat surface mới. Thay đổi giảm surface bằng cách xóa write/query path tới bảng evaluations; retained trust boundary MT5/strategy payload -> journal/snapshot DB writes vẫn được test.

## Self-Check: PASSED

- Summary file tồn tại: `D:/Aureus/.planning/quick/260425-duy-xo-a-ba-ng-aureus-trade-evaluations-va-s/260425-duy-SUMMARY.md`.
- Commit task 1 tồn tại: `b33e165`.
- Commit task 2 tồn tại: `fde8984`.
- DB retained tables verified sau drop.
