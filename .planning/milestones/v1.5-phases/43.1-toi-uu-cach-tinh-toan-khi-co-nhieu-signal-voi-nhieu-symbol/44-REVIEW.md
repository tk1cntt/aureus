# Phase 44 Architecture Review — Independent Advisor Audit

**Date:** 2026-04-17
**Reviewer:** Independent Architecture Advisor (self-review)
**Source:** `44-DISCUSSION.md` (original) → This document (adversarial audit)
**Status:** Audit complete

---

## Context thực tế đã xác minh từ codebase

| Tham số | Giá trị thực tế | Source |
|---------|----------------|--------|
| **Số symbols** | **8** (XAUUSD, BTCUSD, ETHUSD, USTEC, USDJPY, EURUSD, GBPUSD, AUDUSD) | `.env` line 4, 36 |
| **Max window** | **2000** (constructor default 3000, nhưng live_engine.py truyền 2000) | `live_engine.py:206` |
| **Warmup** | 1500 candles từ DB per symbol | `live_engine.py:340-346, 412-418` |
| **Signals/symbol** | ~14 (6 EMA + ATR + VolSMA + Trend + Session + Pivots + Structure + Sweep + 2 CHOCH + CISD + 2 FVG) | `signal_factory.py:108-167` |
| **DataFrame rebuild** | `pd.DataFrame(window)` MỌI nến — `manager.py:126` | `manager.py:126` |
| **EMA incremental** | Có cache O(1) với `state_obj.emas[period]` + fallback ewm | `ema.py:38-59` |
| **Processing model** | Sequential per-symbol trong 1 event loop, `symbol_lock` per symbol | `live_engine.py:613-866` |
| **Redis batch** | xreadgroup count=500, block=5000ms | `live_engine.py:620-624` |
| **Brain workers** | 2 workers cho AI queue | `live_engine.py:224` |
| **Signal history bound** | 200 records (pop(0) = O(n)) | `state.py:233` |
| **OBs bound** | 50 | `state.py:579` |
| **Swing points bound** | 500 | `pivots.py:250` |

### Chi phí thực tế (tính lại đúng):

- **Warmup per symbol:** 1500 × `pd.DataFrame(1..1500)` = Σ(1→1500) ≈ **1.125M row-conversions/symbol**
- **Warmup total (8 symbols):** ≈ **9M row-conversions**
- **Live mode:** 8 × 1440 candles/ngày × 2000 rows = **23.04M row-conversions/ngày**
- **Per-candle signal work:** ~14 signals × 2000-row scan ≈ 28K row-scans/candle
- **Structure processor worst case:** O(50 OBs × 2000 candles) = 100K ops/candle

---

# BƯỚC 1: Liệt kê và Phân rã (Neutral Listing)

Vấn đề: **"Tối ưu performance cho signal engine Python xử lý 8 symbols với pandas DataFrames và stateful indicators"**

## Các phương án phổ biến trong industry:

### Phương án 1: Pure Python + Pandas (Current State — baseline)
- Single-threaded asyncio event loop
- `pd.DataFrame(list_of_dicts)` rebuild mỗi nến
- EMA có incremental cache, signals khác full DataFrame scan
- Per-symbol Lock (sequential trong practice vì 1 consumer loop)

### Phương án 2: Incremental Calculation với NumPy
- Thay thế pandas operations bằng NumPy array math cho indicators
- Incremental formulas: ATR, SMA, BB (O(1) per candle)
- Circular/fixed-size buffer thay vì list append + DataFrame rebuild
- Vẫn single-threaded, vẫn pandas interface ở layer signals

### Phương án 3: Polars (Lazy Evaluation DataFrame)
- Replace pandas bằng Polars (Rust backend, SIMD, lazy evaluation)
- Lazy API: expression graph optimization tự động
- Streaming execution: không load toàn bộ vào memory
- Multi-threaded native (Rust bypasses GIL hoàn toàn)

### Phương án 4: Multi-process / Worker Pool
- ProcessPoolExecutor cho CPU-bound signal calculations
- Shared memory (mmap, multiprocessing.Array) cho DataFrame sharing
- Message queue (ZeroMQ, Redis Pub/Sub) inter-process communication
- Main process chỉ orchestrate I/O, workers tính toán

### Phương án 5: Event-Driven / Reactive Architecture
- Observer pattern: signals subscribe vào state changes, không bị "gọi"
- Lazy evaluation: chỉ tính khi có consumer cần kết quả
- Computation graph (DAG) của dependencies giữa indicators
- Framework: RxPy, hoặc custom pub/sub

### Phương án 6: GPU / CUDA Acceleration
- Offload indicator calculations sang GPU (cuDF, RAPIDS)
- Batch process nhiều symbols cùng lúc trên GPU cores
- Zero-copy transfer từ host memory (pinned memory)

### Phương án 7: Compiled Code (Numba / Cython)
- JIT compile signal calculations với Numba `@njit`
- Cython cho tight loops (structure detection, sweep scanning)
- Vẫn giữ pandas interface nhưng core computation được compiled

### Phương án 8: Microservice Architecture (Horizontal Scale)
- Split symbols thành multiple service instances (ví dụ: 2 instances × 4 symbols)
- Mỗi instance độc lập: riêng Redis consumer group, DB connection pool
- Docker Compose orchestration
- Load balancer phân phối symbols vào instances

---

# BƯỚC 2: Phân tích theo Tiêu chí (Attribute Mapping)

## 2.1 — Hiệu năng / Tốc độ thực thi

| Phương án | Warmup speed | Live per-candle | Multi-symbol throughput | CPU bound handling |
|-----------|-------------|-----------------|------------------------|-------------------|
| 1. Pure Pandas (current) | Chậm nhất O(n²) | Chậm O(n) rebuild + O(n) scan | N×T sequential | GIL block |
| 2. Incremental NumPy | Nhanh O(n) batch | Nhanh nhất O(1) per candle | N×T nhưng T rất nhỏ | GIL block nhưng T đủ nhỏ |
| 3. Polars | Nhanh (lazy, streaming) | Nhanh 3-10x pandas | Multi-threaded native | Bypasses GIL |
| 4. Multi-process | Nhanh nếu parallelizable | Phụ thuộc pickle overhead | T/n_workers | True parallelism |
| 5. Event-Driven | Nhanh (lazy) | Nhanh nhất O(chỉ signals cần) | Phụ thuộc scheduler | GIL block |
| 6. GPU | Rất nhanh (batch lớn) | Nhanh (GPU kernel) | Rất nhanh | GPU parallelism |
| 7. Numba/Cython | Nhanh (compiled) | Nhanh 10-100x tight loops | GIL block nhưng T nhỏ | Compiled native speed |
| 8. Microservice | Nhanh per instance | Như current | T per instance | Parallel instances |

**Mạnh nhất về hiệu năng thuần:** GPU (6) > Event-Driven (5) > Incremental NumPy (2) ≈ Numba (7)

## 2.2 — Khả năng bảo trì / Cộng đồng

| Phương án | Độ phức tạp | Tài liệu/community | Dễ hire | Dễ debug | Backward compat |
|-----------|------------|-------------------|---------|----------|----------------|
| 1. Pure Pandas | Thấp | Rất lớn | Rất dễ | Rất dễ | N/A (baseline) |
| 2. Incremental NumPy | Trung bình | Rất lớn | Dễ | Dễ | ✅ Cao |
| 3. Polars | Trung bình | Đang phát triển | Trung bình | Trung bình | ⚠️ API khác pandas |
| 4. Multi-process | Cao | Lớn | Dễ | Khó (IPC) | ⚠️ Cần serialization |
| 5. Event-Driven | Rất cao | Trung bình | Khó | Rất khó (async) | ❌ Rewrite core |
| 6. GPU | Rất cao | Nhỏ (niche) | Rất khó | Rất khó | ❌ Infrastructure change |
| 7. Numba/Cython | Cao | Trung bình | Trung bình | Khó | ⚠️ Rewrite signals |
| 8. Microservice | Cao | Lớn | Dễ | Trung bình | ✅ Code không đổi |

**Mạnh nhất về bảo trì:** Incremental NumPy (2) — ecosystem lớn nhất, backward compatible cao nhất.

## 2.3 — Trade-off Analysis chi tiết

### Trade-off: Phương án 2 (Incremental) vs 3 (Polars)

**Chọn 2 thay vì 3 → ĐƯỢC:**
- Zero library change — pandas vẫn là interface, signals không cần sửa API
- NumPy đã có trong dependencies, không thêm dependency mới
- Debug bằng tools quen thuộc (pdb, print, logging)
- Backward compatible 100% — không break signals hiện tại

**Chọn 2 thay vì 3 → MẤT:**
- Polars multi-threaded native — bypasses GIL, tận dụng 8 cores tự động
- Polars lazy evaluation tự động optimize expression graph
- Polars xử lý DataFrame lớn 5-10x nhanh hơn pandas
- Future-proof: Polars đang tăng trưởng mạnh, pandas decline trong data engineering

**Verdict:** Với 8 symbols × 2000 rows, pandas đủ nhanh nếu không rebuild mỗi nến. Polars overkill cho dataset này.

### Trade-off: Phương án 2 (Incremental) vs 4 (Multi-process)

**Chọn 2 thay vì 4 → ĐƯỢC:**
- Không pickle/serialize SymbolState (nested dicts, 50 OBs, 500 swing points, ZigZagPro object, 200 signal history records → vài trăm KB per pickle)
- Không tăng memory N× — mỗi process cần copy DataFrame + State
- Không cần IPC — all in-memory communication
- Đơn giản debug — 1 process, linear execution

**Chọn 2 thay vì 4 → MẤT:**
- Không bypass được GIL — CPU-bound signals (structure, pivots) vẫn chạy single-threaded
- Không thể tận dụng 8 cores — chỉ dùng 1 core
- Nếu signal optimization không đủ → không có fallback parallelism

**Verdict:** Pickle overhead ước tính 5-10ms cho SymbolState phức tạp. Signal calc chỉ 1-3ms. Multi-process có negative ROI cho use case này.

### Trade-off: Phương án 2 (Incremental) vs 5 (Event-Driven)

**Chọn 2 thay vì 5 → ĐƯỢC:**
- Giữ linear execution flow — debug đơn giản
- Không rewrite core engine (live_engine.py 1200 lines)
- Risk thấp — mỗi change isolated
- Team 1 người có thể maintain

**Chọn 2 thay vì 5 → MẤT:**
- Không eliminate redundant calculations — vẫn gọi signals nhưng có dirty-flag skip
- Không natural path sang parallel — vẫn sequential
- Không tự động dependency resolution

**Verdict:** Event-driven là architectural shift, không phải optimization. Với stability priority #1 và 2-3 tuần time budget → không khả thi.

### Trade-off: Phương án 7 (Numba) vs 2 (Incremental)

**Chọn 7 thay vì 2 → ĐƯỢC:**
- Không cần thay đổi data structures — vẫn pandas DataFrame
- Speedup 10-100x cho tight loops (nếu @njit nopython mode hoạt động)
- Chỉ thêm decorator, không rewrite core logic (trong lý thuyết)

**Chọn 7 thay vì 2 → MẤT:**
- `@njit` không support pandas objects, dict comprehensions, nhiều Python builtins
- Signals hiện tại dùng quá nhiều pandas patterns → phải rewrite thành pure NumPy
- `@jit` object mode = zero speedup, chỉ thêm compilation overhead
- Compilation time lúc startup làm warmup chậm hơn
- Debug khó — compiled code traceback ít informative

**Verdict:** Numba chỉ hiệu quả nếu signal code đã là pure NumPy. Current code dùng pandas extensively → phải rewrite trước → negate benefit.

---

# BƯỚC 3: Đề xuất dựa trên Context

## Ngữ cảnh thực tế của Aureus:

| Context ID | Context | Impact lên decision |
|------------|---------|-------------------|
| **C1** | ~14 signals, 8 symbols, 2000 window, 1 core engine file | Dataset nhỏ — không cần GPU/Polars |
| **C2** | 1 developer, mạnh Python/pandas | Không có bandwidth cho rewrite lớn |
| **C3** | Production live trade — stability #1 | Risk tolerance cực thấp |
| **C4** | 2-3 tuần time budget | Không thể làm event-driven hay microservice |
| **C5** | Docker Compose, 1 server, 8 cores | Infrastructure đơn giản |
| **C6** | pandas, numpy, asyncio — có sẵn | Incremental NumPy fit tự nhiên |
| **C7** | Sai signal = mất tiền thật | Silent bugs là risk lớn nhất |
| **C8** | Phase 43 chưa execute/deploy | Chưa có production data để profile |

## Đề xuất TỐI ƯU: PHƯƠNG ÁN 2 (Incremental NumPy) — có guardrails

### Tại sao LOẠI các phương án khác:

| Phương án | Lý do loại (cụ thể) |
|-----------|-------------------|
| **1. Giữ nguyên** | Warmup O(n²) với 8 symbols = 9M row-conversions. Live mode 23M/ngày. Có bottleneck thực tế. |
| **3. Polars** | Rewrite 14 signals từ pandas→Polars API = 2-3 tuần. Polars API không 100% compatible (một số operations khác). Không có Polars experience trong team. Không đáng cho dataset 2000 rows. |
| **4. Multi-process** | Pickle SymbolState: nested dicts + 50 OBs + 500 swing points + ZigZagPro + 200 signal history ≈ 300-500KB. Pickle cost ≈ 5-10ms. Signal calc ≈ 1-3ms. **Negative ROI.** Memory tăng 8× = 8 process copies. |
| **5. Event-Driven** | Rewrite live_engine.py (1200 lines) + signal_factory.py + tất cả 14 signals. 3-4 tuần. Race condition risk CRITICAL. Silent bug risk cao. |
| **6. GPU** | GPU cần batch lớn (>1000 parallel streams) để amortize transfer cost. 8 symbols quá nhỏ. Cần CUDA server — infrastructure change. |
| **7. Numba** | `@njit` không support pandas. Signals dùng `df.iterrows()`, dict ops, list comprehensions. Phải rewrite pure NumPy trước → effort bằng rewrite luôn. `@jit` object mode = zero speedup. |
| **8. Microservice** | 8 symbols trên 1 server chưa bottleneck capacity — bottleneck là per-symbol CPU. Team 1 người không maintain được distributed system. |

### Kiến trúc đề xuất: Incremental NumPy với 4 lớp bảo vệ

```
Lớp 1: Circular/Fixed-size NumPy buffer cho OHLCV storage
       ↓ Thay thế pd.DataFrame(window) → zero allocation append
       ↓ to_dataframe() lazy chỉ khi signal cần

Lớp 2: Incremental indicator cache trong SymbolState
       ↓ ATR: (prev × (n-1) + TR) / n → O(1)
       ↓ VolSMA: prev - old/n + new/n → O(1) với circular buffer
       ↓ BB: SMA + std trên buffer 20 → O(20) ≈ O(1)

Lớp 3: Verification layer (drift detection)
       ↓ Mỗi 10 nến: so sánh incremental vs full calc
       ↓ Nếu diff > threshold (0.01%) → alert + full recalc
       ↓ Mỗi 100 nến:强制 full recalc checkpoint

Lớp 4: Dirty-flag per signal
       ↓ Hash(input candle + state fingerprint)
       ↓ Same hash → skip signal calculation
       ↓ Different → calculate + update hash
```

### Expected outcome với 8 symbols:

| Metric | Current (ước lượng) | Proposed | Reduction |
|--------|-------------------|----------|-----------|
| Warmup (8 symbols) | 30-60s | 5-10s | 80%+ |
| Per-candle CPU | 50-100ms | 10-20ms | 70-80% |
| DataFrame allocs/ngày | 23.04M | 2.3M (batched 10:1) | 90% |
| Structure processor | 5-20ms/candle | 1-5ms/candle (dirty-flag) | 75% |

---

# BƯỚC 4: Chế độ Phản biện Nghịch đảo (Adversarial Mode)

Giả sử chọn **Phương án 2 (Incremental NumPy) có guardrails**. Đây là 3 kịch bản THẤT BẠI cụ thể:

## Kịch bản thất bại #1: Incremental Drift → Signal Sai → Trade Sai (SILENT FAILURE)

### Cơ chế failure:

```
T0: Service restart → ATR incremental cache initialized từ snapshot
    Nhưng snapshot KHÔNG lưu ATR buffer (chỉ lưu ema, swing_points, OBs, FVGs)
    → ATR buffer phải rebuild từ scratch → cần 14 candles warmup
    → Trong 14 candles đầu: ATR tính từ incremental formula với initial value WRONG

T0+14 candles: ATR đã "ổn định" nhưng đã drift 0.3% so với full calc

T0+2000 candles (1.4 ngày): Drift 2% → SL pivot tính sai → SL đặt sai vị trí

T0+10000 candles (7 ngày): Drift 5% → ATR 12.50 báo thành 13.12
    → Strategy dựa trên ATR để tính RR ratio → entry sai
    → Không ai biết cho đến khi audit PnL thấy anomalous trades
```

### Root causes (3 con đường drift):

1. **Snapshot không lưu buffer state:** `SymbolState.to_dict()` và `from_db_row()` hiện tại chỉ lưu emas, swing_points, OBs, FVGs. KHÔNG lưu ATR/VolSMA/BB buffers. Sau restart → buffers empty → incremental formula bắt đầu từ giá trị khởi tạo sai.

2. **Candle skip (network issue):** Gateway miss 1 candle → circular buffer bị gap → incremental formula dùng "previous" value sai → drift từ đó.

3. **Floating point accumulation:** Mỗi incremental step có error ~1e-15. Sau 20,000 candles: total error ~2e-11 × 20000 ≈ 2e-7. Nhỏ — nhưng nếu checkpoint interval dài (100 nến) và initial value đã sai → drift compound.

### Hậu quả cụ thể:
- SL theo ATR: sai → stop loss quá xa (lỗ lớn) hoặc quá gần (stop sớm)
- RR ratio 1.5: tính dựa trên ATR → sai → lot size sai
- **Không crash, không error log** — silent failure

### Mitigation đề xuất trong thiết kế gốc: "Checkpoint mỗi 100 nến"

**Vấn đề với mitigation này:** 100 nến M1 = 100 phút. Nếu initial checkpoint sai → 100 phút trade sai. **Không đủ chặt.**

**Mitigation đúng:** 
- Verification mỗi 10 nến (so sánh incremental vs full calc, threshold 0.01%)
- Full recalc checkpoint mỗi 50 nến (không phải 100)
- Snapshot PHẢI lưu buffer state (ATR prev value, VolSMA buffer, BB buffer)
- Alert nếu diff > 0.1% → auto recalc

---

## Kịch bản thất bại #2: Circular Buffer Index Corruption → Signal Tính trên Data Sai

### Cơ chế failure:

```python
# Circular buffer: head = 25000 (sau 17 ngày chạy), max_size = 2000
# idx = 25000 % 2000 = 1000
# Write new candle vào index 1000

# Signal structure_processor đang giữ reference:
#   t_breakout = df.iloc[500]['t']  # từ nến trước
#   mitigation_candles = df[df['t'] > t_breakout]

# Nhưng index 500 trong circular buffer có thể ĐÃ bị overwrite 
# bởi nến mới (vì circular wrap around)
# → df[df['t'] > t_breakout] trả về candles KHÔNG PHẢI thời điểm cần
# → Structure detection sai → CHOCH miss hoặc false positive
```

### Tại sao xảy ra:

1. **DataFrame from circular buffer không stable:** Mỗi lần gọi `to_dataframe()`, data có thể khác nếu buffer đã overwrite giữa các calls. Signal A gọi `to_dataframe()` → nhận df_1. 50ms sau, Signal B gọi → nhận df_2 khác (vì candles mới đã overwrite).

2. **Historical reference invalidation:** Signals như `structure_processor` cần scan historical candles (không chỉ current). `_verify_mitigations()` trong `structure.py` làm `df[df['t'] > t_breakout]` để tìm candles sau breakout. Nếu buffer đã overwrite candles trong range này → query trả về data sai.

3. **Update same-timestamp candle:** Code hiện tại support update candle cũ (cùng timestamp) — `manager.py:104-112`. Trong circular buffer, tìm và update candle cũ không O(1) — phải scan toàn bộ buffer. Nếu implement sai → update nhầm slot.

### Hậu quả cụ thể:
- CHOCH detection sai → strategy trigger false entry
- OB mitigation check sai → trade không exit khi nên
- Swing point detection sai → SL pivot point sai
- **Khó debug:** không crash — chỉ sai kết quả, khó reproduce

### Mitigation đề xuất trong thiết kế gốc: "Signals phải adapt để đọc từ numpy arrays"

**Vấn đề với mitigation này:** Có 14 signals. Chỉ cần **1 signal** quên adapt (vẫn dùng old DataFrame reference) → data corruption. Không có compile-time check nào bắt được bug này — chỉ phát hiện khi test.

**Mitigation đúng:**
- KHÔNG thay đổi interface signals — vẫn trả về DataFrame
- Internal circular buffer → `to_dataframe()` luôn tạo DataFrame **mới** từ buffer state tại thời điểm gọi
- Signals không được giữ reference DataFrame qua nhiều candles
- Test: mỗi signal phải test với circular buffer wrap-around scenario (head > max_size)

---

## Kịch bản thất bại #3: Numba @njit + Pandas Incompatibility → Zero Benefit hoặc Crash

### Cơ chế failure:

```python
# structure.py hiện tại dùng:
# - dict operations: transient_signals[tag] = signal
# - list comprehensions: [p for p in labeled_pivots if ...]
# - df.iterrows(): for idx, row in df[df['t'] > t_breakout].iterrows()
# - Custom objects: state.swing_points (list of dicts)
# - pandas ops: df.iloc, df[df['t'] > t]

@njit  # nopython mode
def verify_mitigations(ob_list, df_close, df_high, df_low, df_t):
    for ob in ob_list:  # ERROR: nopython không support dict iteration
        t_breakout = ob['t_breakout']  # ERROR: dict key access trong nopython
        for idx in range(len(df_t)):
            if df_t[idx] > t_breakout:  # OK
                ...
```

### Tại sao xảy ra:

1. **Numba nopython mode (@njit) không support:**
   - Dict operations (key access, iteration)
   - List of dicts
   - pandas objects (DataFrame, Series)
   - Nhiều Python builtins (hasattr, getattr, isinstance với complex types)
   - Custom class methods

2. **Signal code hiện tại dùng TẤT CẢ những thứ trên:**
   - `structure.py`: dict ops, list of dicts (OBs), df.iterrows()
   - `pivots.py`: dict ops, list of dicts (swing points)
   - `sweep.py`: dict ops, list of dicts

3. **Nếu fallback sang @jit (object mode):** Zero speedup, chỉ thêm compilation overhead (~100ms compile per call).

### Hậu quả cụ thể:
- **Trường hợp 1:** Numba compile error → code không chạy → phải revert
- **Trường hợp 2:** Numba fallback object mode → zero speedup → wasted effort
- **Trường hợp 3:** Rewrite structure.py thành pure NumPy → effort 3-5 ngày, risk cao (phải match chính xác logic hiện tại)

### Mitigation đề xuất trong thiết kế gốc: "Chỉ thêm decorator"

**Vấn đề với mitigation này:** **SAI HOÀN TOÀN.** Không thể "chỉ thêm decorator" cho code dùng pandas/dicts. Phải rewrite toàn bộ function thành pure NumPy với typed arrays.

**Mitigation đúng:**
- **LOẠI Numba khỏi Phase 44** — effort không justify benefit
- Thay vào đó: optimize structure_processor bằng cách **giảm scan frequency** (chỉ verify mitigations mỗi 5 nến thay vì mỗi nến)
- Nếu vẫn muốn compile: dùng Cython cho specific functions, nhưng effort tương đương rewrite

---

## Rủi ro kiến trúc tiềm ẩn thường bị bỏ qua

### R1: Tight Coupling giữa WindowManager và Signal Interface

**Problem:** Signals nhận `pd.DataFrame` với columns `t, o, h, l, c, v`. Nếu thay đổi internal storage từ `list → circular buffer → NumPy`, **tất cả 14 signals** đều bị ảnh hưởng, kể cả signals không được optimize. Đây là tight coupling — không thể optimize storage layer mà không review toàn bộ signal code.

**Evidence:** `ema.py:30-31` dùng `df.iloc[-1]['c']`, `structure.py` dùng `df.iterrows()`, `pivots.py` dùng `df` để scan price action. Mỗi signal access DataFrame theo cách khác nhau.

**Impact:** Bất kỳ thay đổi nào ở `WindowManager.update()` return type hoặc DataFrame structure → phải test lại 14 signals × 8 symbols = 112 combinations.

### R2: Snapshot Schema Must Change cho Incremental Buffers

**Problem:** `SymbolState` được restore từ DB snapshot (`aureus_signal_snapshots`). Snapshot hiện tại lưu: swing_points, OBs, FVGs, emas, tracking_vars. Incremental cache thêm: ATR prev_value, VolSMA circular buffer (20 items), BB circular buffer (20 items).

**Evidence:** `live_engine.py:368-369` — `snap.restore_to_state(state)` restore từ DB row. Nếu DB row không có buffer fields → buffers empty → drift từ restart.

**Impact:** Phải thay đổi snapshot schema (additive columns) + migration script. Nếu không → mỗi restart = drift risk.

### R3: Testing Matrix Explosion

**Problem:** 8 symbols × 14 signals × 3 scenarios (normal/drift/corruption) × 2 modes (warmup/live) × 2 buffer states (empty/partial) = **1,344 test cases**.

**Evidence:** Team 1 người. Coverage thực tế sẽ thấp. Silent bugs (drift, index corruption) không bị bắt bởi unit tests thông thường — cần integration tests với real data.

**Impact:** Bugs phát hiện trong production, không trong testing.

### R4: Phase 43 chưa execute → Không có production data

**Problem:** Toàn bộ phân tích dựa trên complexity analysis, không phải benchmark thực tế. Có thể bottleneck thực sự không phải là DataFrame rebuild mà là:
- Redis I/O (`xreadgroup` block 5000ms)
- DB batch insert (`executemany` với ON CONFLICT)
- AI validator network call
- Strategy evaluation (evaluate_all sequential)

**Impact:** Tối ưu sai chỗ — giảm 80% DataFrame CPU nhưng total latency chỉ giảm 10% vì bottleneck ở nơi khác.

---

# REVISED DECISION MATRIX (sau adversarial review)

Sau khi tự tấn công lựa chọn ban đầu, đây là đề xuất ĐIỀU CHỈNH:

| Phase | Approach | Risk | Effort | Key change từ original | Why |
|-------|----------|------|--------|----------------------|-----|
| **44.0** | **Profiling first** — instrument timing cho mọi signal | LOW | 1 ngày | **MỚI** | Chưa có data thực tế → đo trước khi optimize |
| **44.1** | **Batched DataFrame rebuild** (threshold=10) | LOW | 2-3 ngày | Thay circular buffer | Same 80% benefit, near-zero risk |
| **44.2** | **Incremental cache ATR/VolSMA** với verification layer | LOW | 3-4 ngày | Thêm drift detection | Checkpoint mỗi 10 nến, full recalc mỗi 50 nến |
| **44.3** | **Dirty-flag per signal** | LOW | 2-3 ngày | Giữ nguyên | Skip signals không thay đổi |
| **44.4** | **Structure processor optimization** — giảm scan frequency | LOW | 2-3 ngày | Thay Numba | Scan mỗi 5 nến thay vì mỗi nến |
| **44.5** | **I/O parallel** (asyncio.gather) | LOW | 2-3 ngày | Giữ nguyên | Multi-stream read concurrent |

### Những gì BỊ LOẠI so với discussion gốc:

| Item gốc | Lý do loại |
|----------|-----------|
| **Circular buffer (44.6)** | Index corruption risk — cần rewrite quá nhiều signals |
| **Numba cho structure (44.4 original)** | `@njit` incompatible với pandas/dicts → phải rewrite hoàn toàn |
| **MTF Cache (44.5 original)** | Phase 43 chưa execute → chưa có data để justify |
| **Multi-instance (44.D original)** | Infrastructure complexity không phù hợp team 1 người |

### Thứ tự thực thi MỚI — có Phase 44.0:

```
44.0: PROFILING (1 ngày)
    ↓ Instrument: time.perf_counter_ns() cho mỗi signal
    ↓ Instrument: DataFrame rebuild time
    ↓ Instrument: total per-candle latency
    ↓ Run 24h với 8 symbols → có data thực tế
    ↓ DECISION POINT: Data cho thấy bottleneck nào?
    
    Nếu bottleneck là DataFrame rebuild → 44.1 first
    Nếu bottleneck là structure_processor → 44.4 first  
    Nếu bottleneck là signal duplication → 44.3 first
    Nếu bottleneck là Redis/DB → SKIP tất cả, fix nơi khác
```

**Đây là thay đổi quan trọng nhất:** Discussion gốc nhảy thẳng vào optimization mà không có profiling data. Revised plan BẮT BUỘC profiling trước — 1 ngày investment để đảm bảo optimize đúng chỗ.

---

## Summary: Decision khác biệt giữa Original vs Reviewed

| Aspect | Original 44-DISCUSSION.md | Reviewed 44-REVIEW.md |
|--------|--------------------------|----------------------|
| **Bắt đầu với** | Dirty-flag (44.1) | **Profiling (44.0)** |
| **DataFrame strategy** | Circular buffer (44.6 last resort) | **Batched rebuild (44.1 first)** |
| **Structure optimization** | Không đề cập cụ thể | **Giảm scan frequency (44.4)** |
| **Numba** | Không đề cập | **Đề xuất rồi LOẠI** |
| **Drift detection** | "Checkpoint mỗi 100 nến" | **Verify mỗi 10 nến, checkpoint mỗi 50** |
| **Snapshot schema** | Không đề cập | **PHẢI thay đổi để lưu buffers** |
| **Testing scope** | "140 test cases" | **"1,344 test cases"** |
| **Risk assessment** | LOW cho incremental cache | **LOW nếu có verification layer, HIGH nếu không** |
| **Đuôi recommendation** | 44.1→44.2→44.3→44.4→44.5→44.6 | **44.0→(data-driven)→44.1/44.3/44.4 tùy bottleneck** |
