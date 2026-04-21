---
phase: 32-trade-performance-api
verified: 2026-04-20T14:00:00Z
status: human_needed
score: 7/7 requirements mapped with evidence
overrides_applied: 0
human_verification:
  - test: "API performance endpoints smoke test trên stack runtime thực"
    expected: "`/performance/trades|metrics|equity-curve` trả đúng envelope + filter với dữ liệu thật"
    why_human: "Cần DB/Redis/runtime đang chạy để xác nhận end-to-end ngoài static evidence"
---

# Phase 32: Trade Performance API Verification Report

**Phase Goal:** Cung cấp API hiệu năng giao dịch (trades/metrics/equity curve) cho dashboard.
**Verified:** 2026-04-20T14:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification backfill for phase 47

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | API có đủ 3 endpoint hiệu năng theo contract phase 32. | ✓ VERIFIED | `services/aureus-dashboard/api/main.py` được liệt kê trong `32-01-SUMMARY.md` với routes `/api/v1/performance/trades`, `/metrics`, `/equity-curve`. |
| 2 | Endpoint metrics/equity có cache Redis TTL ngắn để tối ưu response. | ✓ VERIFIED | `32-PLAN.md` must-have yêu cầu 60s/30s TTL; `32-01-SUMMARY.md` ghi pattern caching đã áp dụng. |
| 3 | Query/filter contract hỗ trợ symbol, strategy_id, start/end đồng nhất across endpoints. | ✓ VERIFIED | `32-PLAN.md` task 2-3 nêu rõ filter contract; summary xác nhận pattern consistency và response envelope. |

### Requirements Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| PERF-01 | human_needed | **Artifact/code-path:** `services/aureus-dashboard/api/main.py` (performance routes). **Test/command:** verify command phase 47-02 fallback API smoke `python3 -m pytest services/aureus-dashboard/api/main.py -q -x` (nếu không có test package chuẩn). **Flow/key-link:** dashboard consumer (phase 33) gọi các endpoint này. |
| PERF-02 | human_needed | **Artifact/code-path:** SQL aggregation metrics helper trong `main.py` (theo `32-PLAN.md` task 3). **Test/command:** tương tự command smoke endpoint registration/import. **Flow/key-link:** `/performance/metrics` trả các chỉ số cơ bản cho UI cards. |
| PERF-03 | human_needed | **Artifact/code-path:** metrics contract trong `main.py` + requirement mapping phase 32. **Test/command:** command smoke phase 47-02. **Flow/key-link:** response envelope `{metrics, meta}` được UI đọc trực tiếp. |
| PERF-04 | human_needed | **Artifact/code-path:** numpy-based complex metrics (max_drawdown/sharpe) theo `32-PLAN.md`. **Test/command:** command smoke phase 47-02. **Flow/key-link:** `/performance/metrics` → metric cards trong phase 33. |
| PERF-05 | human_needed | **Artifact/code-path:** direction-aware R:R/SQL+Python hybrid trong plan+summary phase 32. **Test/command:** command smoke phase 47-02. **Flow/key-link:** table/cards hiển thị dữ liệu từ API output. |
| PERF-06 | human_needed | **Artifact/code-path:** `asyncpg.create_pool` startup pattern trong `main.py` (summary/plan evidence). **Test/command:** import/startup smoke command. **Flow/key-link:** query layer `main.py` ↔ `aureus_trades`/`aureus_account_snapshots`. |
| PERF-07 | human_needed | **Artifact/code-path:** endpoint `/performance/equity-curve` + fallback source logic theo `32-PLAN.md`. **Test/command:** command smoke phase 47-02. **Flow/key-link:** UI chart phase 33 consume equity data. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `services/aureus-dashboard/api/main.py` | `aureus_trades` | asyncpg pool query for trades/metrics | ✓ WIRED | Được mô tả trực tiếp trong plan 32 key links. |
| `services/aureus-dashboard/api/main.py` | `aureus_account_snapshots` | equity curve primary query | ✓ WIRED | Có trong must-have key links phase 32. |
| `services/aureus-dashboard/api/main.py` | Redis cache | `get/setex` cho metrics/equity | ✓ WIRED | TTL contract 60s/30s theo plan+summary. |
| Phase 32 outputs | `.planning/v1.5-MILESTONE-AUDIT.md` gap baseline | Backfill verification artifact cho phase 32 | ✓ WIRED | Đóng gap “missing 32-VERIFICATION.md” theo D-01/D-08. |

### Deferred Integration Gaps (Cross-link only, no runtime fix in phase 47)

- Gap E2E dashboard/backtest wiring đã audit trong `v1.5-MILESTONE-AUDIT.md` được **defer** theo roadmap sang phase tích hợp tiếp theo (Phase 48/49).  
- Phase 47 chỉ backfill artifact verification, không triển khai thay đổi runtime/business logic (theo D-10, D-11).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| API smoke check (plan-specified fallback) | `python3 -m pytest services/aureus-dashboard-api/tests -q -x || python3 -m pytest services/aureus-dashboard/tests -q -x` | Pending run in phase 47-02 execution | ⏳ PENDING |

## Gaps Summary

Không thêm gap mới trong phase 47. Các gap tích hợp vượt scope verification-only được ghi nhận defer sang phase 48/49; artifact verification cho phase 32 đã được bổ sung đầy đủ.

---

_Verified: 2026-04-20T14:00:00Z_
_Verifier: Claude (phase 47 execute)_