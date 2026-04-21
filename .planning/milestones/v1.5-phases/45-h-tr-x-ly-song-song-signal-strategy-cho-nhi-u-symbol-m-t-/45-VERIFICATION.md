---
phase: 45-h-tr-x-ly-song-song-signal-strategy-cho-nhi-u-symbol-m-t-
verified: 2026-04-18T13:10:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/7
  gaps_closed:
    - "Signal engine hỗ trợ per-symbol worker runtime thực tế (1 worker/symbol active)"
    - "FIFO strict + out-of-order drop policy chạy trong signal runtime production path"
    - "Circuit-breaker/backlog/SLO + rollout auto-rollback được wire cho cả signal và strategy runtime per-symbol"
  gaps_remaining: []
  regressions: []
---

# Phase 45: Hỗ trợ xử lý song song signal, strategy cho nhiều symbol một lúc chứ k tuần tự như hiện tại Verification Report

**Phase Goal:** Triển khai runtime song song per-symbol cho cả signal và strategy với FIFO strict theo symbol, drop out-of-order candle, idempotency trace_id per symbol+candle, cùng cơ chế rollout an toàn Shadow→Canary→Full kèm auto-rollback theo SLO per-symbol.
**Verified:** 2026-04-18T13:10:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Signal runtime chạy per-symbol worker thật trong production path | ✓ VERIFIED | `run_signal_engine` đã khởi tạo `runtime = PerSymbolWorkerRuntime(...)` và route entry qua `await runtime.enqueue(symbol, work_item)` trong `services/aureus-signal/engine/live_engine.py` (lines 914, 1008). |
| 2 | FIFO strict theo symbol trong runtime signal | ✓ VERIFIED | `PerSymbolWorkerRuntime` dùng queue riêng theo symbol và `_worker_loop` xử lý tuần tự từng queue (`_queues[symbol]`, `queue.get()`, `queue.task_done()`) trong `services/aureus-signal/engine/symbol_runtime.py`. |
| 3 | Out-of-order candle bị drop theo policy `ts_unix <= last_executed_candle_t` | ✓ VERIFIED | Guard được enforce trong production worker loop: `if item.ts_unix <= last_executed: await item.ack(item); continue` tại `services/aureus-signal/engine/symbol_runtime.py` lines 59-62. |
| 4 | Strategy chỉ xử lý khi snapshot cùng candle | ✓ VERIFIED | `validate_snapshot_candle_consistency(payload)` được gọi trước `process_triggers(...)` trong `services/aureus-signal/engine/strategy_executor.py` (lines 420 trước 601). |
| 5 | Idempotency strict trace_id `symbol:strategy:origin_timestamp` + replay dedupe | ✓ VERIFIED | `orders.py` tạo `trace_id = f"{symbol}:{strat_id}:{origin_t}"` và dedupe qua `sismember(history_key, trace_id)` với `history_key = aureus:orders:history:{symbol}` (lines 213, 220-221). |
| 6 | Circuit-breaker/backlog/SLO chạy độc lập per-symbol ở runtime | ✓ VERIFIED | Cả signal và strategy runtime đều gọi `SymbolRuntimeHealthManager.update_symbol_metrics(...)`; strategy path còn `record_symbol_success/failure` và resolve mode per symbol (`services/aureus-signal/engine/strategy_executor.py` lines 261, 431, 621, 634). |
| 7 | Rollout Shadow→Canary→Full + auto rollback theo SLO per-symbol được wire vào signal+strategy runtime | ✓ VERIFIED | Signal path resolve mode qua `resolve_symbol_processing_mode(symbol, symbol_health_manager)` trước xử lý (`live_engine.py` line 790); strategy path resolve mode + branch `shadow` skip trigger execution và transition logging (`strategy_executor.py` lines 437-445). |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `services/aureus-signal/engine/live_engine.py` | Production wiring router → per-symbol runtime + health hooks | ✓ VERIFIED | Runtime instantiated, enqueue wired, health metrics update in work-item loop. |
| `services/aureus-signal/engine/symbol_runtime.py` | Worker FIFO/drop policy + per-symbol health manager | ✓ VERIFIED | Substantive implementation for queue lifecycle, out-of-order guard, SLO fallback/hysteresis. |
| `services/aureus-signal/engine/strategy_executor.py` | Snapshot gate + rollout/health integration + trigger path | ✓ VERIFIED | Snapshot consistency gate, health manager update/resolve, mode-dependent execution flow. |
| `services/aureus-signal/tests/test_per_symbol_worker_runtime.py` | Regression guard for runtime worker wiring | ✓ VERIFIED | Source-level assertions confirm `run_signal_engine` contains `PerSymbolWorkerRuntime` and `.enqueue`. |
| `services/aureus-signal/tests/test_out_of_order_drop_policy.py` | Regression guard for enforcement path | ✓ VERIFIED | Test asserts main loop no duplicate out-of-order guard and worker drop+ack behavior. |
| `services/aureus-signal/tests/test_strategy_trigger_lifecycle.py` | Snapshot-before-trigger ordering guard | ✓ VERIFIED | Test asserts source ordering: `validate_snapshot_candle_consistency` occurs before `process_triggers`. |
| `services/aureus-signal/tests/test_symbol_slo_rollback.py` | Per-symbol rollback isolation and strategy health wiring proof | ✓ VERIFIED | Tests cover fallback scope isolation and strategy runtime health-wiring keywords. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `live_engine.py` | `symbol_runtime.py` | `PerSymbolWorkerRuntime(...).enqueue(...)` | ✓ WIRED | Runtime path now routes candle entries to per-symbol queue and worker callback. |
| `live_engine.py` | `symbol_runtime.py` | health metrics/mode update | ✓ WIRED | Uses `SymbolRuntimeHealthManager`, mode resolution, and `update_symbol_metrics` in production loop. |
| `strategy_executor.py` | `symbol_runtime.py` | `SymbolRuntimeHealthManager` update + resolve mode | ✓ WIRED | `gsd-tools verify key-links` returned verified for this link. |
| `strategy_executor.py` | `orders.py` | `process_triggers` under snapshot + trace constraints | ✓ WIRED | `process_triggers(...)` called only after snapshot consistency gate and health-mode branch. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `live_engine.py` | `work_item` / `data` | Redis stream `aureus:stream:{symbol}:candle` via `xreadgroup` | Yes | ✓ FLOWING |
| `symbol_runtime.py` | `item.ts_unix`, `last_executed` | Values fed from live_engine enqueue + state tracking | Yes | ✓ FLOWING |
| `strategy_executor.py` | `payload` and mode metrics | Redis stream `aureus:stream:{symbol}:signals` + payload metrics | Yes | ✓ FLOWING |
| `orders.py` | `trace_id` dedupe key | Strategy trigger payload + Redis set membership | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| SLO breach tự fallback mode per-symbol | `python3 -c "... SymbolRuntimeHealthManager ... print(m.get_symbol_mode('XAUUSD'))"` | `fallback_serial` | ✓ PASS |
| Import toàn bộ engine runtime modules | `python3 -c "... import engine.live_engine ..."` | Fail do thiếu dependency môi trường (`ModuleNotFoundError: asyncpg`) | ? SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PH45-01 | 45-01/45-04 | Signal engine per-symbol worker runtime active | ✓ SATISFIED | `run_signal_engine` instantiate `PerSymbolWorkerRuntime` + enqueue path (`live_engine.py`). |
| PH45-02 | 45-01/45-04 | FIFO strict theo candle trong symbol | ✓ SATISFIED | Queue per symbol + sequential worker loop in `symbol_runtime.py`. |
| PH45-03 | 45-01/45-04 | Drop out-of-order `ts_unix <= last_executed_candle_t` | ✓ SATISFIED | Guard and ack in worker loop (`symbol_runtime.py` lines 59-62). |
| PH45-04 | 45-02/45-05 | Strategy snapshot same-candle strict consistency | ✓ SATISFIED | Snapshot gate called before strategy processing (`strategy_executor.py`). |
| PH45-05 | 45-02/45-05 | Idempotency strict trace_id | ✓ SATISFIED | `orders.py` strict trace format + Redis history dedupe. |
| PH45-06 | 45-03/45-04/45-05 | Circuit-breaker + backlog threshold per-symbol | ✓ SATISFIED | `SymbolRuntimeHealthManager` wired in both live and strategy paths; per-symbol status/mode control used. |
| PH45-07 | 45-03/45-04/45-05 | Shadow→Canary→Full rollout + auto-rollback per-symbol | ✓ SATISFIED | Mode resolver + fallback transitions + per-symbol branching in runtime paths and tests. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | - | - | - | Không phát hiện TODO/FIXME/stub/blocker pattern trong artifacts mục tiêu. |

### Human Verification Required

Không có mục bắt buộc human verification ở gate này; các must-have của phase 45 đã được xác minh đủ qua code-path và wiring evidence.

### Gaps Summary

Ba gap của lần verify trước đã được đóng:
- Worker runtime signal path đã đi vào production flow thật.
- FIFO/out-of-order policy đã trở thành enforcement path runtime (không còn artifact-only).
- Health/rollout/rollback per-symbol đã wire vào cả signal và strategy execution path.

Kết luận: phase 45 đạt goal outcome theo roadmap contract và must_haves sau gap-closure.

---

_Verified: 2026-04-18T13:10:00Z_
_Verifier: Claude (gsd-verifier)_
