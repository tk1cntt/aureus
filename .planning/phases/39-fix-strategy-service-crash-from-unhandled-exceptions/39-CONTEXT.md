# Phase 39: Fix Strategy Service Crash from Unhandled Exceptions — Context

**Gathered:** 2026-04-10
**Status:** Ready for planning
**Source:** Research-based decisions (no discuss-phase — bug fix)

<domain>
## Phase Boundary

Bổ sung exception handling vào 2 files core của `aureus-signal` service:
- `services/aureus-signal/engine/live_engine.py` (signal aggregation)
- `services/aureus-signal/engine/strategy_executor.py` (strategy evaluation)

Không thay đổi logic nghiệp vụ — chỉ thêm fault tolerance để service không crash silent.
</domain>

<decisions>
## Implementation Decisions

### D1: Không dùng `asyncio.TaskGroup` — giữ compatibility với pattern hiện tại
- Dùng supervisor wrapper cho `asyncio.create_task()` thay vì TaskGroup
- Lý do: TaskGroup yêu cầu tất cả tasks hoàn thành trước khi exit context — không phù hợp cho background infinite loops
- Pattern: `supervised_background_task(name, coro)` với retry + exponential backoff

### D2: Fix `recalculate_all_signals()` — bỏ `raise` sau exception
- Line ~1091 trong `live_engine.py` hiện có `raise` sau except
- Hành vi: Nếu recalculation fail → `daily_gc_loop` chết vĩnh viễn
- Fix: Log error + return (không re-raise), set status NOT_READY để retry lần sau

### D3: Bảo vệ `news_refresh_loop()` 24h variant
- Lines ~537-543 trong `live_engine.py` không có try-catch
- Fix: Bọc try-catch trong loop, giữ `news_refresh_worker()` (900s) làm primary — có thể remove 24h loop trong phase sau

### D4: Bảo vệ `listen_for_reload()` pubsub listener
- Trong cả `live_engine.py` và `strategy_executor.py`, pubsub listener không có try-catch
- Fix: Bọc toàn bộ `async for message in pubsub.listen()` trong try-catch với reconnect logic

### D5: Bảo vệ `tradingagents_provider.get_decision()` trong candle processing
- Line ~767 trong `live_engine.py`—nếu HTTP timeout crash toàn bộ candle loop
- Fix: Bọc try-catch riêng,Nếu timeout skip pulse và tiếp tục

### D6: Bảo vệ `update_orders()` và `process_triggers()` trong strategy_executor.py
- Lines ~438-458 không có try-catch
- Fix: Bọc try-catch riêng cho mỗi function

### D7: Thay bare `except:` bằng `except Exception:` trong `simulated_orders.py`
- Line ~170 dùng bare `except:` — bắt luôn KeyboardInterrupt/SystemExit
- Fix: Thay bằng `except Exception:`

### D8: Fire-and-forget tasks cần supervisor
- `asyncio.create_task(insert_single_snapshot(...))` line ~724
- `asyncio.create_task(shadow_execute_pulse(...))` line ~789
- Fix: Tạo helper `_safe_task_wrapper` để wrap mọi fire-and-forget tasks

### D9: Không thay đổi architecture — chỉ thêm exception handling
- Không thêm dependencies mới (không dùng `tenacity`, giữ manual retry)
- Không refactor cấu trúc code — chỉ bọc try-catch tại các điểm nguy hiểm
- Service Docker restart policy đã có (`restart: unless-stopped` trong docker-compose) — nhưng không được dựa vào vì dead tasks vẫn mất functionality
</decisions>

<canonical_refs>
## Canonical References

### Source files to modify
- `services/aureus-signal/engine/live_engine.py` — signal aggregation (1132 lines)
- `services/aureus-signal/engine/strategy_executor.py` — strategy evaluation (483 lines)
- `services/aureus-signal/engine/simulated_orders.py` or `engine/orders.py` — bare except fix

### Pattern references
- `services/aureus-signal/engine/live_engine.py` lines 62-76 — existing per-signal try-catch pattern (good example)
- `services/aureus-signal/engine/ai_validator.py` lines 483-542 — validate_trigger fallback pattern
- `services/aureus-signal/common/circuit_breaker.py` — existing CircuitBreaker implementation

### Research & planning
- `.planning/phases/39-fix-strategy-service-crash-from-unhandled-exceptions/39-RESEARCH.md` — full research

</canonical_refs>

<specifics>
## Specific Ideas

- Phase này là technical fix — không có requirements từ ROADMAP.md (TBD)
- RESEARCH.md đã identify 4 crash patterns cụ thể với line numbers
- Cần tạo tests để verify exception handling hoạt động
</specifics>

<deferred>
## Deferred Ideas

- Tích hợp Sentry/structlog-based crash reporting — để phase sau
- Chuyển sang `asyncio.TaskGroup` — cần Python 3.11+ migration review
- Consolidate `news_refresh_loop` + `news_refresh_worker` thành single loop
</deferred>

---

*Phase: 39-fix-strategy-service-crash-from-unhandled-exceptions*
*Context gathered: 2026-04-10 via Research-based decisions*
