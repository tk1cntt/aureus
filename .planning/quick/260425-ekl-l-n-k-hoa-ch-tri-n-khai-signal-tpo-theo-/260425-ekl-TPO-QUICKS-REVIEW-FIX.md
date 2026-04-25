---
phase: 260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-QUICKS-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 260425-ekl: Code Review Fix Report

**Fixed at:** 2026-04-25T00:00:00Z
**Source review:** .planning/quick/260425-ekl-l-n-k-hoa-ch-tri-n-khai-signal-tpo-theo-/260425-ekl-TPO-QUICKS-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: TPO history uses insertion order instead of timestamp order

**Files modified:** `services/aureus-signal/engine/signals/tpo_history.py`, `services/aureus-signal/tests/test_tpo_history.py`
**Commit:** 6f9003f
**Applied fix:** Sau khi append/dedup, history theo timeframe được sort theo timestamp và trim các entry cũ nhất theo thời gian; thêm test out-of-order để xác nhận `poc_shift`, `va_width_change`, freshness và bound trim dùng latest chronological snapshot.

**Impact analysis:** Đã attempt GitNexus impact cho `TPOHistoryStore.append`, nhưng CLI hiện trả `unknown option '--target'`; blast radius không lấy được từ GitNexus. Phạm vi diff chỉ chạm `TPOHistoryStore.append` và test liên quan.

**Verification:**
- `python -c "import ast; ast.parse(...)"` cho file source/test liên quan: pass
- `python -m pytest "D:/Aureus/services/aureus-signal/tests/test_tpo_history.py"`: 7 passed

### WR-02: Strategy seeding can silently continue after template upsert failures

**Files modified:** `services/aureus-signal/engine/strategies/seed_strategies.py`, `services/aureus-signal/tests/test_seed_strategies_tpo.py`
**Commit:** 84b9249
**Applied fix:** `_seed_with_conn` collect template upsert failures, log lỗi như cũ, rồi raise `RuntimeError` trước khi fetch/sync symbol strategies; thêm fake connection test đảm bảo failure dừng trước symbol strategy activation.

**Impact analysis:** Đã attempt GitNexus impact cho `seed_system_strategies`, nhưng CLI hiện trả `unknown option '--target'`; blast radius không lấy được từ GitNexus. Đã attempt `npx gitnexus detect-changes` trước commit nhưng CLI trả `unknown command 'detect-changes'`; dùng `git status`/`git diff` để xác nhận scope chỉ gồm file seed và test liên quan.

**DB evidence:** Fix chỉ thay đổi error-handling/control-flow khi template upsert lỗi, không đổi schema/migration và không đổi contract seed template hay data creation path thành công. Test dùng fake connection targeted để xác nhận không chạy symbol strategy sync sau failure; không cần DB thật vì không thay đổi persistence success path.

**Verification:**
- `python -c "import ast; ast.parse(...)"` cho file source/test liên quan: pass
- `python -m pytest "D:/Aureus/services/aureus-signal/tests/test_seed_strategies_tpo.py"`: 3 passed

## Skipped Issues

Không có.

---

_Fixed: 2026-04-25T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
