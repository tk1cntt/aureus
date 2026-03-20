---
status: testing
phase: 01-signal-atr
source: SUMMARY.md, VALIDATION.md
started: 2026-03-20T21:02:42+07:00
updated: 2026-03-20T21:02:42+07:00
---

## Current Test

number: 1
name: Factory Wiring Smoke
expected: |
  Chạy bộ test Phase 1 theo lệnh trong `VALIDATION.md` và thấy kết quả pass, xác nhận wiring `atr_14` hoạt động trong đường chạy thật.
awaiting: user response

## Tests

### 1. Factory Wiring Smoke
expected: Chạy bộ test Phase 1 theo lệnh trong `VALIDATION.md` và thấy kết quả pass, xác nhận wiring `atr_14` hoạt động trong đường chạy thật.
result: [pending]

### 2. Runtime Schema Timestamp Key
expected: Trong output/assert của test integration, history signal dùng key timestamp `t` (không lệch sang key khác), khớp schema runtime hiện tại.
result: [pending]

### 3. Anti-Masking Integration Guard
expected: Bộ test integration vẫn bảo vệ đúng wiring thật (không che lỗi wiring bằng mock/snapshot fallback sai tầng), nên regression về registration path sẽ bị phát hiện.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0

## Gaps

[none yet]
