# Phase 48: performance-backtest-api-wiring - Research

**Researched:** 2026-04-20
**Domain:** Performance Dashboard API/Web contract wiring (FastAPI + Next.js)
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Data Contract (API ↔ Web)
- **D-01:** Chuẩn hóa response contract cho 3 endpoint performance theo hướng backward-compatible: chỉ bổ sung/chuẩn hóa field cần thiết, không phá field cũ đã được web sử dụng.
- **D-02:** Mọi field số liên quan hiệu năng (PnL, drawdown, win rate, RR, equity values) phải có kiểu dữ liệu nhất quán giữa API và web; nullability phải explicit để web không cần suy đoán.
- **D-03:** `metrics`, `trades`, `equity-curve` phải cùng phản ánh một bộ filter input để tránh lệch số liệu giữa cards/table/chart.

### Filter Semantics
- **D-04:** Chuẩn hóa bộ query params dùng chung cho 3 endpoint (symbol, strategy, timeframe, date-range) với default thống nhất và validation rõ ràng ở API.
- **D-05:** Khi filter không hợp lệ, API trả lỗi có cấu trúc ổn định (không silent fallback), web hiển thị trạng thái lỗi thay vì render số liệu sai.

### Pagination & Ordering
- **D-06:** Trades endpoint dùng pagination ổn định (`page`, `page_size`, `total`) và deterministic ordering để tránh nhảy bản ghi giữa các lần fetch.
- **D-07:** Rule sort mặc định phải cố định và được dùng xuyên suốt (không phụ thuộc ngầm vào storage order).

### Freshness & Caching
- **D-08:** Caching phải được áp dụng có chủ đích (TTL ngắn cho metrics) nhưng không tạo split-brain giữa metrics/trades/equity khi cùng filter.
- **D-09:** Ưu tiên correctness contract trước tối ưu hiệu năng; nếu cache khiến lệch dữ liệu cross-widget thì phải giảm/điều chỉnh cache policy để đảm bảo E2E consistency.

### Claude's Discretion
- Cách đặt tên field trung gian nội bộ trong API/service layer.
- Mức refactor tối thiểu cần thiết để gom logic filter validation mà vẫn giữ thay đổi surgical.

### Deferred Ideas (OUT OF SCOPE)
- Bổ sung capability analytics mới ngoài PERF-01..08 (ví dụ Sharpe/export nâng cao) giữ cho phase sau theo roadmap.
- Mọi chỉnh sửa liên quan order execution multi-symbol contract để phase 49 xử lý.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-01 | API endpoint trả danh sách trades với entry/exit details | Contract + pagination/order + nullability mapping cho `/performance/trades` [VERIFIED: codebase Read `api/main.py`, `page.tsx`] |
| PERF-02 | Tính toán Win rate | Chuẩn hóa numeric field + cùng filter semantics giữa metrics/trades/equity [VERIFIED: codebase Read `api/main.py`] |
| PERF-03 | Tính toán Profit factor | Giữ metric computation hiện có, chỉ sửa contract/filter consistency [VERIFIED: codebase Read `api/main.py`] |
| PERF-04 | Tính toán Max drawdown | Giữ compute path numpy, bổ sung type/null contract rõ ràng [VERIFIED: codebase Read `api/main.py`] |
| PERF-05 | Tính toán Average R:R | Đồng bộ kiểu dữ liệu số và semantics theo D-02/D-03 [VERIFIED: codebase Read `api/main.py`, `48-CONTEXT.md`] |
| PERF-06 | Equity curve chart | Đồng bộ filter + cache policy + source semantics cho `/equity-curve` [VERIFIED: codebase Read `api/main.py`, `page.tsx`] |
| PERF-07 | Filter theo symbol, strategy, timeframe | Thiết kế filter contract dùng chung và API validation lỗi cấu trúc [VERIFIED: codebase Read `api/main.py`, `48-CONTEXT.md`] |
| PERF-08 | Trang trade history trên aureus-dashboard | Web consumer contract phải chịu lỗi API đúng cách, không render sai số [VERIFIED: codebase Read `page.tsx`, `33-VERIFICATION.md`] |
</phase_requirements>

## Summary

Phase 48 là phase **integration contract stabilization**, không phải phase thêm capability analytics mới. Endpoint performance đã tồn tại (`/trades`, `/metrics`, `/equity-curve`) và trang web `/performance` đã gọi song song 3 endpoint bằng cùng query params, nhưng verification phase 47 xác nhận còn gap E2E runtime và contract drift cần đóng ở phase này. [VERIFIED: codebase Read `32-VERIFICATION.md`, `33-VERIFICATION.md`, `47-02-SUMMARY.md`]

Để plan tốt, cần tập trung vào 4 trục: (1) contract response ổn định + explicit nullability, (2) filter semantics dùng chung + lỗi validation có cấu trúc, (3) pagination/deterministic ordering cho trades, (4) cache/freshness tránh split-brain cross-widget. Đây cũng chính là locked decisions D-01..D-09 trong CONTEXT. [VERIFIED: codebase Read `48-CONTEXT.md`]

**Primary recommendation:** Plan phase 48 theo hướng “minimum-change wiring” trực tiếp trong `services/aureus-dashboard/api/main.py` và `services/aureus-dashboard/web/src/app/performance/page.tsx`, ưu tiên contract correctness trước tối ưu hiệu năng. [VERIFIED: codebase Read `48-CONTEXT.md`]

## Project Constraints (from CLAUDE.md)

- Mọi trao đổi dùng tiếng Việt. [VERIFIED: codebase Read `CLAUDE.md`]
- Khi command lỗi, tham khảo `RUN_SERVICES.md`. [VERIFIED: codebase Read `CLAUDE.md`]
- Ưu tiên đơn giản, thay đổi tối thiểu, không mở rộng scope/speculative. [VERIFIED: codebase Read `CLAUDE.md`]
- Chỉ sửa đúng phần liên quan yêu cầu (surgical changes), không dọn dẹp lan sang vùng khác. [VERIFIED: codebase Read `CLAUDE.md`]
- Nếu có chỉnh sửa code symbol trong implement phase, bắt buộc chạy GitNexus impact trước sửa và detect_changes trước commit. [VERIFIED: codebase Read `CLAUDE.md`, `.claude/skills/gitnexus/*/SKILL.md`]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | `0.129.0` (pinned) | API route layer cho performance endpoints | Đã là framework runtime của dashboard API trong repo, phase 48 chỉ cần wire/contract [VERIFIED: codebase Read `services/aureus-dashboard/api/requirements.txt`, `api/main.py`] |
| asyncpg | `0.31.0` (pinned) | Query trades/metrics/equity data | Đã có pooled access trong startup; phù hợp sửa semantics/query contract [VERIFIED: codebase Read `requirements.txt`, `api/main.py`] |
| redis (py) | `7.2.0` (pinned) | Caching metrics/equity | Cache key + TTL hiện hữu cần chuẩn hóa theo filter contract [VERIFIED: codebase Read `requirements.txt`, `api/main.py`] |
| Next.js + React | `next 16.1.6`, `react 19.2.3` (pinned) | Web consumer `/performance` | Consumer contract hiện hữu đã sẵn để wiring API chuẩn [VERIFIED: codebase Read `web/package.json`, `page.tsx`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | `2.12.5` (pinned) | Schema typing/validation | Dùng để formalize response/error envelope nếu bổ sung model trong phase 48 [VERIFIED: codebase Read `api/requirements.txt`, `api/main.py`] |
| numpy | `>=1.24.0` (pinned range) | max drawdown/sharpe computations | Giữ nguyên compute path, không thay thuật toán trong phase 48 [VERIFIED: codebase Read `api/requirements.txt`, `api/main.py`] |
| lightweight-charts | `^5.1.0` | Consumer chart rendering `/performance` | Chỉ cần đảm bảo data contract equity tương thích, không đổi chart lib [VERIFIED: codebase Read `web/package.json`, `33-VERIFICATION.md`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Sửa trực tiếp endpoint hiện có | Tách module performance service mới | Tăng scope/refactor risk, trái nguyên tắc surgical của phase [VERIFIED: codebase Read `48-CONTEXT.md`, `CLAUDE.md`] |
| Backward-compatible field addition | Breaking rename contract | Có thể làm vỡ web consumer hiện tại [VERIFIED: codebase Read `48-CONTEXT.md`, `page.tsx`] |

**Installation:** Không cần thêm package mới cho phase 48 nếu giữ hướng minimum-change wiring. [VERIFIED: codebase Read `48-CONTEXT.md`, `requirements.txt`, `web/package.json`]

## Architecture Patterns

### Recommended Project Structure
```
services/aureus-dashboard/
├── api/main.py                         # performance handlers + validation + caching
└── web/src/app/performance/page.tsx    # parallel fetch + filter URL sync + render
```
[VERIFIED: codebase Read `48-CONTEXT.md`, `api/main.py`, `page.tsx`]

### Pattern 1: Shared filter contract builder (API-side)
**What:** Một nguồn parse/validate filter dùng chung cho cả trades/metrics/equity thay vì mỗi endpoint tự xử lý khác nhau.
**When to use:** Khi 3 endpoint cần cùng semantics D-03/D-04.
**Example:**
```python
# Source: services/aureus-dashboard/api/main.py
# Existing reusable piece: _parse_date_param(start/end)
# Phase 48 nên mở rộng thành parse_filter_contract(...) dùng lại cho 3 handlers.
```
[VERIFIED: codebase Read `api/main.py`, `48-CONTEXT.md`]

### Pattern 2: Deterministic trades list contract
**What:** ORDER BY cố định + pagination meta đầy đủ (`page`, `page_size`, `total`, `total_pages`).
**When to use:** Mọi fetch trades có phân trang.
**Example:**
```sql
-- Source: services/aureus-dashboard/api/main.py
ORDER BY filled_at DESC
LIMIT $6 OFFSET ($7 - 1) * $6
```
[VERIFIED: codebase Read `api/main.py`]

### Pattern 3: Parallel fetch with single filter source (web-side)
**What:** Web tạo 1 query string từ state filter rồi dùng cho cả 3 endpoint trong `Promise.all`.
**When to use:** Đồng bộ cards/table/chart theo cùng điều kiện lọc.
**Example:**
```ts
// Source: services/aureus-dashboard/web/src/app/performance/page.tsx
const [metricsRes, tradesRes, equityRes] = await Promise.all([
  fetch(`${API_BASE}/performance/metrics?${qs}`),
  fetch(`${API_BASE}/performance/trades?page=${currentPage}&page_size=20&${qs}`),
  fetch(`${API_BASE}/performance/equity-curve?${qs}`),
]);
```
[VERIFIED: codebase Read `page.tsx`]

### Anti-Patterns to Avoid
- **Silent fallback cho filter sai:** hiện `status/page_size` đang fallback ngầm; trái D-05 với invalid filter phải trả lỗi có cấu trúc. [VERIFIED: codebase Read `api/main.py`, `48-CONTEXT.md`]
- **Default time range không đồng nhất API-vs-web:** web default 7 ngày rolling theo phút; equity endpoint default start là đầu ngày hiện tại khi thiếu param. Dễ gây drift nếu web không gửi đủ param. [VERIFIED: codebase Read `page.tsx`, `api/main.py`]
- **Cache key không bao phủ đầy đủ filter semantics:** metrics key có symbol/strategy/start/end nhưng chưa có timeframe; equity key chưa có symbol/strategy nên khó giữ D-03 nếu phase thêm filter chung đầy đủ. [VERIFIED: codebase Read `api/main.py`, `48-CONTEXT.md`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query-string parsing đồng bộ | Tự parse nhiều nơi bằng string ops | `URLSearchParams` phía web + centralized parser phía API | Giảm drift semantics giữa endpoint [VERIFIED: codebase Read `page.tsx`, `api/main.py`] |
| Pagination consistency | Custom page math tách rời mỗi endpoint | Meta contract chuẩn (`total`, `page`, `page_size`, `total_pages`) | Tránh nhảy trang và mismatch table state [VERIFIED: codebase Read `api/main.py`] |
| JSON serialization datetime | Hand-format nhiều kiểu | `.isoformat()` nhất quán | Tránh parse lỗi phía web [VERIFIED: codebase Read `api/main.py`] |

**Key insight:** Phase 48 nên “chuẩn hóa contract và semantics”, không “viết lại analytics engine”. [VERIFIED: codebase Read `48-CONTEXT.md`, `ROADMAP.md`]

## Common Pitfalls

### Pitfall 1: API trả 200 với filter invalid (silent coercion)
**What goes wrong:** Web hiển thị dữ liệu “có vẻ đúng” nhưng thực chất từ filter fallback.
**Why it happens:** `page_size/status` bị ép về default thay vì trả lỗi rõ. [VERIFIED: codebase Read `api/main.py`]
**How to avoid:** Chuẩn hóa validation error envelope và trả 4xx cho input invalid theo D-05.
**Warning signs:** User đổi filter nhưng số liệu không thay đổi hợp lý.

### Pitfall 2: Cross-widget split-brain do TTL khác nhau
**What goes wrong:** Cards (metrics), table (trades), chart (equity) lệch snapshot thời gian.
**Why it happens:** metrics cached 60s, equity 30s, trades gần realtime; khi fetch song song có thể lấy state không cùng epoch. [VERIFIED: codebase Read `api/main.py`, `page.tsx`]
**How to avoid:** Bổ sung metadata freshness/version timestamp hoặc điều chỉnh cache policy theo D-08/D-09.
**Warning signs:** Cùng filter nhưng net PnL card không khớp tổng profit table.

### Pitfall 3: Contract mismatch nullability/number types
**What goes wrong:** Frontend formatting `.toFixed()` lỗi hoặc hiển thị NaN.
**Why it happens:** Metric/trade field nullable/empty object không explicit. [VERIFIED: codebase Read `page.tsx`, `api/main.py`]
**How to avoid:** API trả explicit null/0 theo contract rõ và web guard render cho empty metrics.
**Warning signs:** Console error render trong `/performance` khi data rỗng.

## Code Examples

### Shared parse + strict validation direction (điểm có sẵn)
```python
# Source: services/aureus-dashboard/api/main.py
def _parse_date_param(date_str: Optional[str]) -> tuple:
    if date_str is None:
        return None, None
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, None
    except (ValueError, TypeError):
        return None, {"error": f"Invalid ISO 8601 date format: {date_str}"}
```
[VERIFIED: codebase Read `api/main.py`]

### Web single-source filter + parallel fetch pattern
```ts
// Source: services/aureus-dashboard/web/src/app/performance/page.tsx
const params = new URLSearchParams();
if (selectedSymbol) params.set("symbol", selectedSymbol);
if (strategyId) params.set("strategy_id", String(strategyId));
if (startDate) params.set("start", startDate);
if (endDate) params.set("end", endDate);
const qs = params.toString();
```
[VERIFIED: codebase Read `page.tsx`]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Verification-only backfill phase 47 (không runtime fix) | Phase 48 dedicated integration wiring | 2026-04-20 roadmap/context update | Cho phép đóng E2E dashboard/api gap đúng scope [VERIFIED: codebase Read `47-02-SUMMARY.md`, `ROADMAP.md`, `48-CONTEXT.md`] |

**Deprecated/outdated:**
- Dùng verification artifact để suy ra “đã pass runtime E2E” là không hợp lệ; các artifact 32/33 đang `human_needed`. [VERIFIED: codebase Read `32-VERIFICATION.md`, `33-VERIFICATION.md`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | “timeframe” hiện chưa có trong API performance params dù đã là locked decision D-04 cần chuẩn hóa | Architecture Patterns / Pitfalls | Có thể plan thiếu task nếu timeframe thực ra đã được xử lý ở layer khác ngoài file đã đọc |
| A2 | Không có test suite chuyên biệt cho dashboard performance trong repo hiện tại | Validation Architecture | Có thể bỏ sót test command sẵn có nếu nằm ngoài đường dẫn đã scan |

## Open Questions

1. **Filter `timeframe` sẽ map vào nguồn dữ liệu nào cho metrics/trades/equity?**
   - What we know: D-04 yêu cầu timeframe trong shared params; endpoint hiện chưa nhận timeframe. [VERIFIED: codebase Read `48-CONTEXT.md`, `api/main.py`]
   - What's unclear: Có cần derive theo timeframe từ candle/snapshot hay chỉ apply trên trade timestamps. [ASSUMED]
   - Recommendation: Chốt semantics ngay trong PLAN-01 để tránh đổi contract giữa chừng.

2. **Error envelope chuẩn cho invalid filter là gì?**
   - What we know: D-05 yêu cầu structured error ổn định. [VERIFIED: codebase Read `48-CONTEXT.md`]
   - What's unclear: Format exact (`code/message/details`) nào để web xử lý thống nhất. [ASSUMED]
   - Recommendation: Chọn 1 schema tối giản và wire cả API + web error-state cùng lượt.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python3 | FastAPI runtime/tests | ✓ | 3.10.11 | — |
| node | Next.js web build/typecheck | ✓ | v22.22.0 | — |
| npm | Web scripts/deps | ✓ | 11.12.0 | — |
| pytest | Python test execution | ✓ | 9.0.2 | — |
| docker daemon | Full E2E stack smoke | ✗ | — | Chạy API/web local process mode nếu có env phù hợp [ASSUMED] |
| redis-cli/Redis local | Cache behavior verification | ✗ (cli probe fail) | — | Test non-cache path hoặc mock Redis [ASSUMED] |
| pg_isready/Postgres local | Query path verification | ✗ (probe fail) | — | Dùng DB integration env khác/WSL stack [ASSUMED] |

**Missing dependencies with no fallback:**
- Không xác nhận được Docker/Redis/Postgres local readiness từ shell hiện tại cho E2E runtime proof. [VERIFIED: env probe commands]

**Missing dependencies with fallback:**
- Redis/Postgres/Docker có thể verify qua môi trường WSL/compose theo runbook vận hành. [CITED: `/d/Aureus/RUN_SERVICES.md`]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (Python), TypeScript compile/lint scripts phía web [VERIFIED: env + package.json] |
| Config file | Không thấy test config riêng trong `services/aureus-dashboard` [VERIFIED: Glob scan] |
| Quick run command | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` (import/smoke mức tối thiểu) [ASSUMED pragmatic fallback; prior phase dùng pattern tương tự] |
| Full suite command | `python3 -m pytest /d/Aureus/services -q -x` + `npm --prefix /d/Aureus/services/aureus-dashboard/web run build` [ASSUMED] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-01 | trades response contract + pagination meta | integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-02 | win_rate correctness under filter | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-03 | profit_factor correctness | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-04 | max_drawdown correctness | unit | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-05 | avg_rr correctness + nullability | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-06 | equity-curve filter + source semantics | integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-07 | shared filter validation + structured error | unit/integration | `python3 -m pytest /d/Aureus/services/aureus-dashboard/api/main.py -q -x` | ❌ Wave 0 |
| PERF-08 | web consumer handles contract/error state | e2e/manual+build | `npm --prefix /d/Aureus/services/aureus-dashboard/web run build` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** API-focused quick check + web build/typecheck.
- **Per wave merge:** targeted API tests (nếu Wave 0 tạo test files) + web build.
- **Phase gate:** E2E `/performance` runtime smoke với API live data (human_needed nếu thiếu infra).

### Wave 0 Gaps
- [ ] `/d/Aureus/services/aureus-dashboard/api/tests/test_performance_contract.py` — cover PERF-01..07.
- [ ] `/d/Aureus/services/aureus-dashboard/web/src/app/performance/__tests__/page.contract.test.tsx` — cover PERF-08 contract/error rendering.
- [ ] Shared fixture cho mock Redis/DB (`conftest.py`) trong dashboard API test folder.
- [ ] Chuẩn hóa lệnh verify thay cho fallback command không có test path rõ như phase 47. [VERIFIED: codebase Read `47-02-SUMMARY.md`]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A cho public/internal read-only performance endpoints trong scope phase 48 [ASSUMED] |
| V3 Session Management | no | N/A [ASSUMED] |
| V4 Access Control | yes | Kiểm soát CORS origins env-based + gateway routing policy [VERIFIED: codebase Read `api/main.py`; gateway policy is ASSUMED] |
| V5 Input Validation | yes | Validate params (`_parse_date_param`, page/page_size/status rules) + explicit 4xx cho invalid filters [VERIFIED: codebase Read `api/main.py`, `48-CONTEXT.md`] |
| V6 Cryptography | no | Không có yêu cầu crypto mới trong phase này [VERIFIED: scope docs `48-CONTEXT.md`, `ROADMAP.md`] |

### Known Threat Patterns for FastAPI + Next filter endpoints

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Query-parameter tampering (invalid date/page/status) | Tampering | Strict validation + structured error, không silent fallback [VERIFIED: codebase + D-05] |
| Resource exhaustion qua page_size lớn | DoS | Allowlist `VALID_PAGE_SIZES` + bounds check [VERIFIED: codebase Read `api/main.py`] |
| CORS misconfiguration | Information Disclosure | Restrict `CORS_ORIGINS` theo env deploy [VERIFIED: codebase Read `api/main.py`] |

## Sources

### Primary (HIGH confidence)
- `/d/Aureus/.planning/phases/48-performance-backtest-api-wiring/48-CONTEXT.md` - locked decisions D-01..D-09, scope, canonical refs.
- `/d/Aureus/.planning/ROADMAP.md` - phase 48 goal/dependency/gap closure.
- `/d/Aureus/.planning/REQUIREMENTS.md` - PERF-01..PERF-08 requirement definitions and pending status.
- `/d/Aureus/.planning/phases/32-trade-performance-api/32-VERIFICATION.md` - phase 32 verification state + deferred integration notes.
- `/d/Aureus/.planning/phases/33-performance-dashboard-ui/33-VERIFICATION.md` - phase 33 verification + key link assertions.
- `/d/Aureus/.planning/phases/47-verification-backfill-v1-5/47-02-SUMMARY.md` - backfill constraints and runtime limits.
- `/d/Aureus/services/aureus-dashboard/api/main.py` - actual endpoint/filter/cache/ordering implementation.
- `/d/Aureus/services/aureus-dashboard/web/src/app/performance/page.tsx` - web consumer contract.
- `/d/Aureus/services/aureus-dashboard/web/package.json` + `/d/Aureus/services/aureus-dashboard/api/requirements.txt` - pinned stack versions.
- `/d/Aureus/.planning/config.json` - nyquist_validation=true.
- `/d/Aureus/CLAUDE.md` + `/d/Aureus/.claude/skills/gitnexus/*/SKILL.md` - project constraints/workflow rules.

### Secondary (MEDIUM confidence)
- Không dùng web source ngoài repo trong nghiên cứu này.

### Tertiary (LOW confidence)
- Các fallback vận hành hạ tầng local/WSL khi thiếu Docker/Redis/Postgres readiness (cần xác nhận thực địa).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - đọc trực tiếp pinned versions trong repo.
- Architecture: MEDIUM - cấu trúc hiện trạng rõ, nhưng E2E runtime behavior còn cần verify infra.
- Pitfalls: MEDIUM - phần lớn dựa trên code hiện có + locked decisions, chưa có full runtime replay.

**Research date:** 2026-04-20
**Valid until:** 2026-04-27 (7 ngày, vì phase tích hợp đang active và dễ đổi nhanh)
