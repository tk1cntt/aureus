# Phase 44 Discussion — Tối ưu cách tính toán khi có nhiều signal với nhiều symbol

**Date:** 2026-04-17
**Status:** Discussion complete, reviewed via adversarial audit (see `44-REVIEW.md`)
**Participants:** Developer + Claude Code
**Reviewed by:** Independent Architecture Advisor (self-review, 4 steps)

> **CORRECTIONS FROM ADVERSARIAL REVIEW (2026-04-17):**
> - Symbol count verified: **8** (not 10 as originally assumed) — `.env` line 4,36
> - Row conversions corrected: **23.04M/day** (not 28.8M) — 8 × 1440 × 2000
> - Phase 44.0 (Profiling) added as mandatory first step
> - Circular Buffer (44.6) demoted — Batched Rebuild promoted as primary
> - Drift detection tightened: checkpoint every 10 candles, full recalc every 50
> - Test cases corrected: **1,344** (not 140) — 8 × 14 × 3 scenarios × 2 modes × 2 buffer states
> - Snapshot schema change requirement added for incremental buffers
> - Numba rejected for structure_processor (incompatible with pandas/dicts)
> - See `44-REVIEW.md` for full adversarial analysis

---

## 1. Problem Statement

Phase 44 goal: "Tối ưu cách tính toán khi có nhiều signal với nhiều symbol"

4 dimensions of optimization identified:
1. **Signal duplication** — Tính trùng lặp giữa signals gây lãng phí tài nguyên
2. **Incremental vs cached sharing** — Indicator tính lại từ đầu mỗi nến
3. **Sequential vs parallel architecture** — Single-threaded processing cho nhiều symbols
4. **Data window optimization** — DataFrame rebuild toàn bộ mỗi nến

---

## 2. Current Architecture Analysis (Evidence-Based)

### Key files analyzed:
- `services/aureus-signal/engine/live_engine.py` — Main engine, lines 158-882
- `services/aureus-signal/engine/manager.py` — WindowManager, lines 85-142
- `services/aureus-signal/engine/state.py` — SymbolState
- `services/aureus-signal/engine/signal_factory.py` — Signal set creation
- `services/aureus-signal/engine/signals/ema.py` — EMA incremental cache pattern
- `services/aureus-signal/engine/snapshot_utils.py` — MTF BB computation

### Current bottlenecks identified:

| ID | Bottleneck | Location | Impact |
|----|-----------|----------|--------|
| P1 | Full DataFrame rebuild every candle | `manager.py:126` | O(n) per candle, O(n²) warmup |
| P2 | No incremental indicator updates (except EMA) | All signals except `ema.py` | O(n) scan per signal per candle |
| P3 | Sequential symbol processing | `live_engine.py:630-866` | N symbols × T ms = N×T latency |
| P4 | Bollinger Band computation in snapshot (5 TFs) | `snapshot_utils.py:48-65` | 15 operations per snapshot |
| P5 | Redundant signal calculations on recalculation | `live_engine.py:982-1161` | O(candles × signals) |
| P6 | Signal history bounded but O(n) pop | `state.py:233` | Minor |
| P7 | Strategy evaluation every candle | `live_engine.py:479` | Sequential per strategy |

### Signal inventory (~14 signals per symbol):

| Signal | Type | Current cost | Has cache? |
|--------|------|-------------|-----------|
| ema_21/34/55/89/100/200 | Incremental | O(1) with cache | ✅ Yes |
| atr_14 | Full scan | O(n) | ❌ No |
| vol_sma_20 | Full scan | O(n) | ❌ No |
| trend (200) | Full scan | O(n), rarely changes | ❌ No |
| session | Time lookup | O(1) | N/A |
| pivots (ZigZagPro) | Incremental stateful | O(n) relabeling | ✅ Partial |
| structure_processor (CHOCH+OB) | O(OBs × candles) | Heavy | ❌ No |
| sweep_processor | Scan swing points | O(swing_points) | ❌ No |
| choch_up/down | Read transient | O(1) | N/A |
| cisd | Pattern match | O(n) | ❌ No |
| fvg_up/down | Pattern match | O(n) | ❌ No |

### Current dedup mechanisms (what exists):
- OB exact duplicate check (`state.py:382-389`)
- CHOCH duplicate by tag+timestamp (`structure.py:59-65`)
- Pivot non-repaint (skip last pivot until confirmed)
- Transient signals per-candle reset (`live_engine.py:703`)
- DB ON CONFLICT DO UPDATE for snapshots

### What is NOT deduplicated:
- Full `execute_signals_for_candle` loop always runs ALL ~14 signals per candle
- No dedup between consecutive candles
- No cross-symbol state sharing

---

## 3. Four Discussion Dimensions

### Dimension 1: Signal Duplication

**Problem:** All ~14 signals run on EVERY candle, even when 10-12 return None.

#### Option A: Dirty-Flag per Signal (Change Detection) — ✅ SELECTED
Each signal tracks "last result hash". If input (candle + state) unchanged → skip.

| S | W | O | T |
|---|---|---|---|
| Không thay đổi kiến trúc | Cần hash function per signal type | Kết hợp với event-driven | Hash collision → skip nhầm (xác suất极低) |
| Giảm 60-80% calls vô ích | Signal stateful (pivots) không thể skip | EMA cache pattern đã có sẵn | Implement sai → silent bug |
| Áp dụng incremental cho ATR, VolSMA | Overhead hash (nhưng rẻ hơn calculate) | Signal nào cần chạy = profiling data | |

**Risk: LOW**

#### Option B: Signal Grouping by Trigger Condition
3 nhóm: Always (EMA/ATR), Event-Triggered (structure/sweep), Time-Triggered (session/trend).

| S | W | O | T |
|---|---|---|---|
| Giảm structure từ "mỗi nến" → "chỉ khi event" | Heuristic `price_near_liquidity` có thể false negative | Tận dụng SignalType enum Phase 40 | Heuristic sai → miss signal quan trọng |
| Phù hợp SignalType enum đã có | Refactor signal_factory để group | Structure processor nặng nhất → giảm nhiều | Cần "luôn chạy N nến đầu" safeguard |

**Risk: MEDIUM** — Requires heuristics. Needs dirty-flag data first to be accurate.

#### Option C: Event-Driven Lazy Evaluation (Observer Pattern)
Signals subscribe to state changes instead of being called.

| S | W | O | T |
|---|---|---|---|
| Zero redundant calculation | Rewrite core engine | Mở đường cho parallel | Race condition async |
| Tự nhiên parallelizable | Phức tạp debug | Tương thích MTF | Risk cao nhất |
| Scalable: add signal = subscribe | Overhead observer pattern | | |

**Risk: CRITICAL** — Core rewrite. Phase riêng, không phải optimization.

#### Comparison:

| Criteria | A: Dirty-Flag | B: Grouping | C: Event-Driven |
|----------|--------------|-------------|-----------------|
| Giảm CPU | 30-40% | 50-70% | 70-90% |
| Risk | LOW | MEDIUM | CRITICAL |
| Effort | 2-3 ngày | 5-7 ngày | 3-4 tuần |
| Rollback | ✅ Dễ | ✅ Dễ | ❌ Khó |
| Path to parallel | ❌ | ⚠️ Một phần | ✅ |

**Decision: Start with A → measure → B if needed. C for future architecture.**

---

### Dimension 2: Incremental vs Cached Sharing

**Problem:** Only EMA has incremental cache. ATR, VolSMA, BB all recompute from scratch. Phase 43 MTF adds 5× resample + 5× BB per snapshot = 15 heavy ops per M1 candle.

#### Option A: Incremental Indicator Cache (extend EMA pattern) — ✅ SELECTED
Cache all indicators in SymbolState with incremental formulas.

| S | W | O | T |
|---|---|---|---|
| EMA pattern đã hoạt động | ATR incremental có drift sau nhiều nến | Tận dụng state.update_with_candle() | Drift accumulation → sai kết quả |
| O(n) → O(1) cho ATR, VolSMA | Memory tăng: deque buffers | Áp dụng cho MTF: mỗi TF có cache | Buffer size sai → kết quả lệch |
| Backward compatible: fallback nếu miss | BB cần 20-candle buffer → phức tạp | Periodic checkpoint chống drift | |

**ATR incremental:** `ATR = (Prev_ATR × (n-1) + TR_current) / n` → O(1)
**VolSMA incremental:** `SMA = prev_SMA - old_val/n + new_val/n` (circular buffer) → O(1)
**BB incremental:** `mid = SMA(close, 20)`, `std = sqrt(mean(sq_diff))` → O(20) ≈ O(1)

**Risk: LOW — NHƯNG CHỈ KHI CÓ VERIFICATION LAYER** (drift detection mỗi 10 nến, full recalc mỗi 50 nến, snapshot phải lưu buffer state). KHÔNG có verification → Risk HIGH (silent failure → wrong trades).

#### Option B: MTF Cache with Incremental Promotion
Maintain separate incremental window per timeframe. Promote M1→M5→M15→M30→H1.

| S | W | O | T |
|---|---|---|---|
| Eliminate 15 ops/snapshot | Complex: track 5 TF boundaries | Dùng chung cache cho signal+snapshot | M1 miss candle → MTF desync |
| O(5×n) → O(1) per snapshot | Need sync: resampled candle match gateway | Pre-compute BB cho TF cao | Need reconciliation |
| Fit tự nhiên với Phase 43 | Risk domino effect | Verify MTF cache khớp DB mỗi giờ | |

**Risk: MEDIUM** — MTF desync là mối lo chính.

#### Option C: Shared Computation Graph
Single graph per symbol. Only recompute nodes affected by change.

| S | W | O | T |
|---|---|---|---|
| Tự động optimize | Overhead graph management | Bước đệm cho event-driven | Circular dependencies |
| Share kết quả signal+snapshot+strategy | Phức tạp ban đầu | Graph visualization debug | Over-engineering cho 14 signals |
| Dễ thêm signal = thêm node | Dependency analysis chính xác | | |

**Risk: MEDIUM-HIGH** — Needs careful design.

#### Comparison:

| Criteria | A: Incremental Cache | B: MTF Cache | C: Computation Graph |
|----------|---------------------|-------------|---------------------|
| Giảm CPU | 40-50% | 60-80% (snapshot) | 50-70% (tổng thể) |
| Risk | LOW | MEDIUM | MEDIUM-HIGH |
| Effort | 3-4 ngày | 5-7 ngày | 2-3 tuần |
| Value for Phase 44 | ✅ ATR/VolSMA | ✅ MTF bottleneck | ✅ Tổng thể |
| Depends on #3 | ❌ | ❌ | ⚠️ |

**Decision: A first, then B for MTF bottleneck. C long-term.**

---

### Dimension 3: Sequential vs Parallel Architecture

**Current:** Single asyncio event loop, sequential per-symbol processing with per-symbol Lock (effectively no-op for main loop).

#### Current Architecture SWOT:

| S | W | O | T |
|---|---|---|---|
| Không race condition | Head-of-line blocking: symbol chậm block tất cả | Parallelize independent symbols | >20 symbols → latency >5s → miss candles |
| Debug đơn giản | Không tận dụng multi-core | Tune workers theo CPU cores | Structure processor 500ms+/symbol |
| State isolation | Latency tích lũy: N×T ms/batch | Daily recalc sẽ tệ hơn | |
| Memory predictable | Warmup chậm: 1500×N sequential | | |
| Zero sync overhead | Scale ngang không được | | |

#### Parallel Architecture SWOT:

| S | W | O | T |
|---|---|---|---|
| Giảm latency N×T → T | State isolation phức tạp hơn | Event-triggered signals trên worker riêng | ZigZagPro stateful → corruption nếu 2 workers |
| Tận dụng multi-core | Debug khó: race conditions | MTF offload separate worker | Redis connection pool overload |
| Scale theo hardware | Memory: N workers × DataFrame × State | AI brain workers pattern đã có | asyncio.gather không giúp CPU-bound (GIL) |
| Warmup nhanh hơn | | | |

#### Option A: Asyncio Gather (I/O Parallelism)
`asyncio.gather` cho multi-symbol concurrent processing.

| S | W | O | T |
|---|---|---|---|
| Thay đổi nhỏ nhất | Không giúp CPU-bound signals | Bước đầu trước worker pool | symbol_lock sai → race |
| Giảm latency batch đáng kể | Redis/DB connection contention | Giới hạn concurrency: Semaphore(4) | Memory spike: 10 symbols cùng rebuild DF |

**Risk: LOW-MEDIUM**

#### Option B: Worker Pool with ProcessPoolExecutor (CPU Parallelism)
Offload CPU-bound signal calculation to process pool.

| S | W | O | T |
|---|---|---|---|
| Bypass GIL, multi-core thật sự | Pickle overhead stateful objects | Chỉ offload CPU-heavy signals | Pickle cost > signal cost → tệ hơn |
| CPU-heavy signals hưởng lợi | Complex serialization | Shared memory (mmap) cho DataFrame | State sync phức tạp |
| Isolation tuyệt đối | Memory: process copy DF+State | | |

**Risk: HIGH** — Pickle overhead likely negates benefit.

#### Option C: Hybrid — I/O Parallel + Selective CPU Offload — ✅ SELECTED
asyncio.gather cho I/O, giữ signal calculation inline (đã optimized), selective to_thread.

| S | W | O | T |
|---|---|---|---|
| Balance tốt: I/O parallel, CPU optimized | Không tận dụng tối đa multi-core | Path tiến hóa tự nhiên | Nếu signal optimization đủ → CPU offload không cần |
| Ít rủi ro nhất | Phức tạp hơn pure sequential | | Thread safety shared state |

**Risk: LOW** — Conservative, evolution not revolution.

#### Option D: Multi-Instance Deployment (Horizontal Scaling)
Split symbols across instances.

| S | W | O | T |
|---|---|---|---|
| Scale ngang vô hạn | Infrastructure phức tạp | Fit Docker compose hiện có | Symbol distribution không đều → unbalanced |
| Mỗi instance nhẹ → latency thấp | Cost vận hành tăng | Kubernetes auto-scaling | Shared DB/Redis bottleneck |
| Fault isolation | Config management | | |

**Risk: MEDIUM** — Infrastructure change, code change minimal.

#### Comparison:

| Criteria | A: Asyncio Gather | B: ProcessPool | C: Hybrid | D: Multi-Instance |
|----------|------------------|---------------|-----------|-------------------|
| Giảm latency | 60-80% | 70-90% | 50-70% | 90%+ (per instance) |
| Risk | LOW-MEDIUM | HIGH | LOW | MEDIUM |
| Effort | 2-3 ngày | 1-2 tuần | 3-5 ngày | 1-2 tuần |
| Refactor signal code | ❌ | ✅ Nhiều | ⚠️ Ít | ❌ |
| Multi-core | ❌ | ✅ | ⚠️ | ✅ Per instance |
| Fit Phase 44 | ✅ Tốt | ⚠️ Overkill | ✅ Tốt nhất | ✅ Scale lớn |

**Decision: Start with C. If scale needed later → D.**

---

### Dimension 4: Data Window Optimization

**Current:** `pd.DataFrame(window)` rebuilds entire DataFrame from list on every candle. Warmup: 1500 rebuilds. Live: 2000-row rebuild per candle per symbol.

Cost: 10 symbols × 1440 candles/day × 2000 rows = **28.8M row-conversions/day**.

#### Current SWOT (Full Rebuild):

| S | W | O | T |
|---|---|---|---|
| Đơn giản: 1 dòng code | O(n) mỗi nến | Replace bằng incremental append | Incremental bug → silent corruption |
| Luôn consistent | Warmup O(n²) | Giảm window size nếu không cần | Window nhỏ → trend 200 mất accuracy |
| Không stale data risk | Memory allocation mới mỗi lần | | |

#### Incremental Append SWOT:

| S | W | O | T |
|---|---|---|---|
| O(1) append | DataFrame fragmentation | Numpy arrays thay vì DataFrame | Numpy immutable → vẫn copy |
| Giảm 99% work | Update same-timestamp candle khó | Circular buffer — zero allocation | Phức tạp, rewrite window_manager |
| Warmup O(n) batch | Index management | Mmap/shared memory | Over-engineering |

#### Option A: Circular Buffer with NumPy Arrays

| S | W | O | T |
|---|---|---|---|
| Zero allocation append | Rewrite window_manager hoàn toàn | Signals đọc trực tiếp numpy | Circular indexing bug → data corruption |
| O(1) append | Signals phải adapt đọc numpy | Shared memory cho parallel | |
| Warmup O(n) | Candle update phức tạp | Step đệm computation graph | |
| Memory predictable: ~96KB/symbol | to_dataframe() vẫn cần cho pandas ops | | |

**Risk: MEDIUM** — Rewrite window_manager, but backward compatible via `to_dataframe()`.

#### Option B: Lazy DataFrame with Incremental Patch

| S | W | O | T |
|---|---|---|---|
| Thay đổi nhỏ nhất | pd.concat vẫn allocate mới | Combine buffered rebuild | Memory fragmentation |
| Backward compatible 100% | iloc update không efficient | | Pandas deprecating append |
| Dễ rollback | Về bản chất vẫn O(n) | | |

**Risk: LOW** — But benefit limited (20-30%).

#### Option C: Batched Lazy Rebuild — ✅ SELECTED
Maintain base DataFrame + pending buffer. Only rebuild when buffer reaches threshold.

| S | W | O | T |
|---|---|---|---|
| 2000-row rebuild → 10-row concat | pd.concat vẫn allocate (nhỏ hơn) | Threshold adaptive | Threshold cao → stale data |
| Backward compatible | Handle edge cases | Tune theo volatility | Memory: base_df + pending |
| Full rebuild mỗi 10 nến | | | |

With threshold=10: warmup O(n) via batch load, live mode concat 2000+10 instead of rebuild 2000.

**Risk: LOW** — Conservative, easy test and rollback.

#### Option D: Columnar Storage with Pandas Block Management

| S | W | W | T |
|---|---|---|---|
| to_dataframe() zero-copy | Shift-left O(n) khi full | | Shift-left negate benefit |
| Column read trực tiếp | Không support update candle cũ | | Window luôn full sau 33h M1 |
| Memory contiguous | Pre-allocate toàn bộ | | |

**Risk: MEDIUM** — Shift-left cost when full.

#### Comparison:

| Criteria | A: Circular Buffer | B: Lazy Append | C: Batched Rebuild | D: Columnar |
|----------|-------------------|---------------|-------------------|-------------|
| Giảm CPU warmup | 99% | 30-50% | 70-80% | 99% |
| Giảm CPU live | 95% | 20-30% | 80-90% | 90% |
| Risk | MEDIUM | LOW | LOW | MEDIUM |
| Effort | 5-7 ngày | 1-2 ngày | 2-3 ngày | 5-7 ngày |
| Backward compat | ⚠️ Adapter | ✅ 100% | ✅ 100% | ⚠️ Adapter |
| Memory | ✅ Best | ❌ Worst | ⚠️ Medium | ✅ Good |

**Decision: C first. A as backup if not enough.**

---

## 4. Decision Matrix — REVISED (after adversarial audit)

### Selection reasoning chain (UPDATED):

```
44.0 (PROFILING — MANDATORY FIRST STEP, 1 day)
    ↓ Instrument timing per signal, per candle, per symbol
    ↓ Run 24h với 8 symbols → real bottleneck data
    ↓ DECISION POINT: data-driven priority, not assumptions

    Nếu bottleneck là DataFrame rebuild → 44.1 first
    Nếu bottleneck là structure_processor → 44.4 first
    Nếu bottleneck là signal duplication → 44.3 first
    Nếu bottleneck là Redis/DB → SKIP tất cả, fix nơi khác

44.1 (Batched DataFrame rebuild — threshold=10)
    ↓ Near-zero risk, 80%+ of circular buffer benefit
    ↓ Replaces circular buffer as primary strategy

44.2 (Incremental cache ATR/VolSMA with verification)
    ↓ Drift detection every 10 candles, full recalc every 50
    ✅ SNAPSHOT SCHEMA MUST CHANGE to save buffer state

44.3 (Dirty-flag per signal)
    ↓ Skip signals unchanged

44.4 (Structure processor optimization — reduce scan frequency)
    ↓ Scan every 5 candles instead of every candle
    ↓ Numba REJECTED — incompatible with pandas/dicts

44.5 (I/O parallel — asyncio.gather)
```

### Final Decision Matrix (REVISED):

| Phase | Dimension | Selected Approach | Risk | Effort | Key change from original |
|-------|-----------|------------------|------|--------|-------------------------|
| **44.0** | **Profiling** | **Instrument timing for all signals** | **LOW** | **1 ngày** | **MỚI — mandatory first step** |
| 44.1 | DataFrame rebuild | Batched lazy rebuild (threshold=10) | LOW | 2-3 ngày | Replaces circular buffer |
| 44.2 | Incremental cache | ATR/VolSMA with drift verification | LOW | 3-4 ngày | Checkpoint 10 nến, recalc 50 nến |
| 44.3 | Signal duplication | Dirty-Flag per Signal | LOW | 2-3 ngày | Unchanged from original |
| 44.4 | Structure processor | Reduce scan frequency (every 5 candles) | LOW | 2-3 ngày | Replaces Numba approach |
| 44.5 | I/O parallel | asyncio.gather for multi-stream | LOW | 2-3 ngày | Unchanged from original |

**Total estimated effort:** 12-16 days (6 sub-phases including profiling)

**Cumulative impact:** ~70-80% overall CPU reduction (multiplicative, not additive)

### Items REJECTED from original plan:

| Original Item | Reason for rejection |
|--------------|---------------------|
| Circular Buffer (44.6) | Index corruption risk — requires rewriting 14 signals |
| Numba for structure_processor | `@njit` incompatible with pandas/dicts — requires full rewrite |
| MTF Cache (44.5 original) | Phase 43 not executed — no production data to justify |
| Multi-instance deployment | Infrastructure complexity doesn't fit 1-person team |

### Critical changes from adversarial review:

| Aspect | Original | Revised |
|--------|----------|---------|
| First step | Dirty-Flag (44.1) | **Profiling (44.0)** |
| Checkpoint frequency | Every 100 candles | **Every 10 candles (verify), 50 (full recalc)** |
| Structure optimization | Not specified | **Reduce scan frequency** (not Numba) |
| Snapshot schema | Not mentioned | **MUST change to save buffer state** |
| Test coverage estimate | 140 test cases | **1,344 test cases** |
| Risk of incremental cache | LOW | **LOW only with verification layer** |

---

## 5. SWOT of the Decision Matrix Itself

### Strengths
- Each step delivers independent measurable value
- Risk increases gradually (LOW → MEDIUM)
- No backward-incompatible changes
- Measure-then-optimize: dirty-flag provides profiling data
- Cumulative multiplicative effect (~70-80% total)

### Weaknesses
- Band-aid optimization — doesn't fix root architecture
- Technical debt accumulation (complexity increases)
- Diminishing returns after 44.4
- **No real benchmark data** — percentages are complexity estimates, not measurements
- Depends on Phase 43 being executed first

### Opportunities
- Profiling data from 44.1 valuable for future optimizations
- Foundation for event-driven architecture
- Can skip steps based on profiling results
- Applicable to Nautilus backtest engine (larger benefit)

### Threats
- **Premature optimization** — real bottleneck may be Redis I/O, DB write, or network
- **Incremental drift** — ATR/VolSMA drift → wrong signals → wrong trades. **Most serious risk. Requires verification layer every 10 candles.**
- **Race conditions from 44.4** — introduces concurrency to sequential system
- **Testing burden** — 8 signals × 14 signals × 3 scenarios × 2 modes × 2 buffer states = **1,344 test cases** (not 140)
- **Phase 43 not yet executed** — optimizing undeployed code is wasted effort
- **Snapshot schema change required** — incremental buffers must be persisted, otherwise every restart = drift risk
- **Circular buffer index corruption** — if implemented, signals referencing historical candles may get wrong data

---

## 6. Assumptions to Verify

| Assumption | How to Verify | If Wrong |
|------------|--------------|----------|
| "structure_processor là signal nặng nhất" | Profile with `time.perf_counter_ns()` per signal | Prioritize incremental cache before dirty-flag |
| "Pickle overhead > signal cost" | Benchmark pickle.dumps(state) vs signal calc | ProcessPool (Way B Dim 3) becomes viable |
| "Warmup 1500 candles × N symbols" | Measure startup time | If <5s → DataFrame optimization lower priority |
| "10 symbols" | Check SYMBOLS in .env | If only 3 → sequential sufficient, no parallel needed |

**Most important question:** Do you have real profiling data? If yes, the matrix should be rebuilt from actual measurements.

---

## 7. Files Referenced

| File | Purpose |
|------|---------|
| `services/aureus-signal/engine/live_engine.py` | Main engine (lines 158-882) |
| `services/aureus-signal/engine/manager.py` | WindowManager (lines 85-142) |
| `services/aureus-signal/engine/state.py` | SymbolState, signal history bounds |
| `services/aureus-signal/engine/signal_factory.py` | Signal set creation (~14 signals) |
| `services/aureus-signal/engine/signals/ema.py` | EMA incremental cache pattern (lines 38-59) |
| `services/aureus-signal/engine/snapshot_utils.py` | MTF BB computation (lines 48-65) |
| `services/aureus-signal/engine/signals/structure.py` | CHOCH+OB processing |
| `services/aureus-signal/engine/signals/pivots.py` | ZigZagPro stateful engine |
