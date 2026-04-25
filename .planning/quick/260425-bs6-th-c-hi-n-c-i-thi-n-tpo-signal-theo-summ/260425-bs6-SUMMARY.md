# Quick Task 260425-bs6 Summary

## Objective
Thực hiện cải thiện TPO signal theo khuyến nghị trong `260425-bnh-SUMMARY.md`: triển khai single-pass profile build và full-block cache cho closed H1/M30 buckets.

## GitNexus Impact Analysis
- `_build_profile` → **LOW**
  - impactedCount: 2
  - d=1 indexed caller: `_compute_tf`
  - d=2: `calculate`
  - Note: index có vẻ cũ so với source hiện tại vì source đang dùng `_compute_sliding`.
- `TPOSignal` → **LOW**
  - impactedCount: 0
  - affected processes/modules: 0
- `_compute_sliding` và `_build_tpo_block`
  - GitNexus CLI báo target not found, nên phạm vi được kiểm soát bằng diff + tests.
- `npx gitnexus detect_changes` vẫn báo `unknown command`; fallback bằng `git diff`, `git diff --stat`, target tests.

## Scope implemented

### 1) Single-pass TPO block build
- `services/aureus-signal/engine/signals/tpo.py`
  - `_build_tpo_block()` giờ gọi `_build_levels_and_counts()` đúng 1 lần.
  - Thêm `_build_profile_from_counts(levels, counts)` để derive `POC/VAH/VAL/poc_idx` từ cùng histogram dùng cho shape classifier.
  - `_build_profile()` giữ public/internal behavior cũ bằng cách gọi helper mới và trả về tuple 3 giá trị như trước.

### 2) Full-block cache cho closed H1/M30 buckets
- `state.tpo_cache` giờ lưu full block dict thay vì chỉ tuple `(poc, vah, val)`.
- `_compute_sliding()` check cache hit trước khi slice M1 session.
- Nếu closed bucket có cache hit, dùng cached block ngay và không rebuild.
- Current bucket vẫn rebuild từ M1 session hiện tại để phản ánh candle mới.

### 3) Tests added
- `services/aureus-signal/tests/test_tpo_signal.py`
  - `test_tpo_closed_bucket_cache_hit_does_not_rebuild`
  - `test_tpo_current_bucket_still_updates_with_new_candle`
  - `test_tpo_block_build_uses_counts_once`

## Verification
- `pytest services/aureus-signal/tests/test_tpo_signal.py services/aureus-notifier/tests/test_formatters.py services/aureus-signal/tests/test_indicator_snapshot.py -q`
  - **45 passed**

## Acceptance Criteria
- TPO output giữ đủ `POC/VAH/VAL/shape/shape_confidence_pct/shape_scores_pct`: **PASS**
- `_build_levels_and_counts()` không bị gọi 2 lần cho cùng một block: **PASS**
- Closed H1/M30 bucket cache hit không rebuild session/block: **PASS**
- Current H1/M30 bucket vẫn update khi candle mới đến: **PASS**
- Target tests pass: **PASS**

## Notes
- D1 semantic giữ nguyên là UTC day (`now_ts - now_ts % 86400`), không thay đổi trong task này.
- Chưa triển khai incremental histogram đầy đủ; đây là Giai đoạn 1 B+E như recommendation của task `260425-bnh`.
