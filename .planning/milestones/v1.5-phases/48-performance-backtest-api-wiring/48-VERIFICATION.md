---
phase: 48-performance-backtest-api-wiring
verified: 2026-04-20T21:35:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/7
  gaps_closed:
    - "Cùng một filter input cho ra metrics/trades/equity nhất quán theo cùng dataset (per D-03, D-04)."
    - "Khi API trả invalid-filter error, web hiển thị trạng thái lỗi rõ ràng theo structured contract (per D-05)."
  gaps_remaining: []
  regressions: []
---

# Phase 48: performance-backtest-api-wiring Verification Report

**Phase Goal:** Khôi phục luồng E2E Performance Dashboard bằng cách wire đầy đủ backtest API routes với web consumer contract.
**Verified:** 2026-04-20T21:35:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Cùng một filter input cho ra metrics/trades/equity nhất quán theo cùng dataset (D-03, D-04) | ✓ VERIFIED | `get_equity_curve` đã dùng filter dimensions trong query snapshot + fallback: `symbol`, `strategy_id`, `timeframe`, `start/end` (`services/aureus-dashboard/api/main.py`). |
| 2 | Filter không hợp lệ trả 4xx với error envelope ổn định, không silent fallback (D-05) | ✓ VERIFIED | `_normalize_performance_filters` + `_error_envelope` trả lỗi có cấu trúc; exception handler trả top-level `{error, code, details}`. |
| 3 | Trades pagination/ordering deterministic giữa các lần fetch (D-06, D-07) | ✓ VERIFIED | `ORDER BY filled_at DESC, id DESC` + meta pagination; test deterministic pass. |
| 4 | Cache policy không gây split-brain giữa metrics/trades/equity khi cùng filter (D-08, D-09) | ✓ VERIFIED | Cache key metrics/equity đều dùng `_performance_cache_key(...)` với cùng dimensions filter; equity query cũng đã lọc theo cùng semantics. |
| 5 | Trang `/performance` dùng cùng filter semantics cho 3 API calls | ✓ VERIFIED | `sharedParams` được reuse cho metrics/trades/equity; trades chỉ thêm `page`/`page_size` (`services/aureus-dashboard/web/src/app/performance/page.tsx`). |
| 6 | UI hiển thị lỗi invalid-filter rõ ràng theo structured API contract | ✓ VERIFIED | `parseErrorMessage` ưu tiên top-level `code` + `error` string, vẫn fallback nested legacy; error state render rõ ràng. |
| 7 | Web parse số/nullability an toàn, tránh NaN/toFixed crash | ✓ VERIFIED | `toFiniteNumber` + `formatMetric` bảo vệ null/NaN trước khi `.toFixed()`. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `services/aureus-dashboard/api/main.py` | Shared filter parser/validator + structured errors + stable pagination/order + cache semantics | ✓ VERIFIED | Tồn tại, substantive, wired; equity filter-effect đã nối đúng runtime query path. |
| `services/aureus-dashboard/api/tests/test_performance_contract.py` | Contract tests PERF-01..PERF-07 | ✓ VERIFIED | Có regression test equity filter-effect theo strategy/timeframe; test file pass. |
| `services/aureus-dashboard/api/tests/conftest.py` | Deterministic fixtures cho API contract tests | ✓ VERIFIED | Fixture/fake pool lọc đủ `symbol/strategy_id/timeframe/start/end`, phục vụ data-flow test đúng semantics. |
| `services/aureus-dashboard/web/src/app/performance/page.tsx` | Contract-aligned fetch/query/error/render | ✓ VERIFIED | Shared query params + parser envelope top-level + fallback compatible + error-state wiring. |
| `services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx` | Success + invalid-filter error contract tests | ✓ VERIFIED | Test success path + invalid-filter path với mock backend runtime shape top-level. |
| `services/aureus-dashboard/web/package.json` | Script test contract targeted | ✓ VERIFIED | Script `test:performance-contract` chạy thành công. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `api/main.py:get_equity_curve` | `_normalize_performance_filters` | query predicates | ✓ WIRED | Normalized filters được dùng vào SQL predicates cho cả snapshot/fallback. |
| `web/page.tsx` | API error envelope | `parseErrorMessage` | ✓ WIRED | Parser đọc top-level `{error, code, details}` và hiển thị đúng error state. |
| `web/page.tsx` | `/api/v1/performance/metrics|trades|equity-curve` | shared URLSearchParams | ✓ WIRED | Cùng filter dimensions được áp cho cả 3 calls. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `api/main.py:get_metrics` | `metrics` | PostgreSQL (`compute_basic_metrics`, `compute_complex_metrics`) + Redis cache | Yes | ✓ FLOWING |
| `api/main.py:get_trades` | `data/meta` | PostgreSQL COUNT + SELECT | Yes | ✓ FLOWING |
| `api/main.py:get_equity_curve` | `data/meta.filters` | PostgreSQL snapshot query + fallback cumulative query (đều có đầy đủ filter predicates) | Yes | ✓ FLOWING |
| `web/page.tsx` | `metrics/trades/equityData/errorMessage` | 3 fetch calls + parsed envelope + state setters | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| API contract PERF-01..07 chạy xanh | `python3 -m pytest "D:/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py" -q -x` | `7 passed` | ✓ PASS |
| Web contract test PERF-08 chạy xanh | `npm --prefix "D:/Aureus/services/aureus-dashboard/web" run test:performance-contract` | `1 file passed, 2 tests passed` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PERF-01 | 48-01, 48-03 | API endpoint trả danh sách trades với entry/exit details | ✓ SATISFIED | `get_trades` response contract + test `test_trades_contract_envelope_and_order_deterministic`. |
| PERF-02 | 48-01 | Tính toán Win rate | ✓ SATISFIED | `compute_basic_metrics` + `test_win_rate_numeric_contract`. |
| PERF-03 | 48-01 | Tính toán Profit factor | ✓ SATISFIED | `compute_basic_metrics` + `test_profit_factor_numeric_contract`. |
| PERF-04 | 48-01 | Tính toán Max drawdown | ✓ SATISFIED | `compute_complex_metrics` + `test_max_drawdown_numeric_contract`. |
| PERF-05 | 48-01, 48-02 | Tính toán Average R:R | ✓ SATISFIED | `avg_rr` nullability explicit + UI guard số/null. |
| PERF-06 | 48-01, 48-03 | Equity curve chart | ✓ SATISFIED | Equity endpoint filter semantics đồng bộ + test `test_equity_curve_contract_uses_shared_filters`. |
| PERF-07 | 48-01, 48-03 | Filter theo symbol, strategy, timeframe | ✓ SATISFIED | `_normalize_performance_filters` + query predicates áp vào metrics/trades/equity đầy đủ. |
| PERF-08 | 48-02, 48-03 | Trang trade history trên aureus-dashboard | ✓ SATISFIED | `/performance` fetch wiring + invalid-filter error-state contract test pass. |

**Orphaned requirements check:** Không có orphan cho phase 48. Tất cả PERF-01..PERF-08 đều có trong plan frontmatter và được đối chiếu với `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `services/aureus-dashboard/api/main.py` | 70, 81 | `@app.on_event(...)` deprecation warning (FastAPI lifespan migration) | ℹ️ Info | Không block goal phase 48; là nợ kỹ thuật riêng không thuộc scope gap closure. |

### Gaps Summary

Không còn gap chặn goal phase. Hai gap trước đó (equity filter-effect và web error-envelope mismatch) đã được đóng, có bằng chứng code + test runtime contract.

---

_Verified: 2026-04-20T21:35:00Z_
_Verifier: Claude (gsd-verifier)_