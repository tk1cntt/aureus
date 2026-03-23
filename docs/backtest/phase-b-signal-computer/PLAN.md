# Phase B: Signal Computer (Offline Pre-computation)

> **Độ khó**: ⭐⭐ | **Ảnh hưởng Live**: Zero | **Thời gian**: 2-3 giờ  
> **Phụ thuộc**: Phase A (bảng `aureus_signal_snapshots` phải tồn tại)  
> **Mô tả**: Worker chạy offline, đọc candles lịch sử từ DB, tính toán tất cả signals, ghi kết quả vào `aureus_signal_snapshots`. Không ảnh hưởng live system.

---

## Checklist tính năng

- [ ] Script `signal_computer.py` chạy được standalone
- [ ] Factory function `create_signal_set()` tạo đúng bộ 18 signals
- [ ] Replay từng nến qua WindowManager + chạy ALL signals per-candle
- [ ] Batch insert snapshots (mỗi 500-1000 rows)
- [ ] Progress tracking qua Redis key
- [ ] `ON CONFLICT DO UPDATE` cho re-run
- [ ] CLI arguments: `--symbol`, `--start`, `--end`, `--months`
- [ ] Shared function `build_snapshot()` (dùng lại ở Phase C, D)

---

## Steps

### Step 1: Extract Signal Factory Function
- **File mới**: `services/aureus-signal/engine/signal_factory.py`
- **Mô tả**: Extract phần tạo signals từ `main.py` (dòng 132-151) thành factory function có thể reuse
- **Nội dung**:
  ```python
  def create_signal_set(symbol: str) -> Dict[str, BaseSignal]:
      """Creates the full set of signal calculators. Shared between live engine, signal_computer, and recovery."""
      # Exact same signal registration as main.py
  ```
- **Điều kiện hoàn thành**: Import được từ cả `main.py` lẫn `signal_computer.py`
- **Test**: `python -c "from engine.signal_factory import create_signal_set; print(len(create_signal_set('TEST')))"`  
  Expect: `18` (hoặc số signals đã đăng ký)

### Step 2: Create Shared `build_snapshot()` + `batch_insert_snapshots()`
- **File mới**: `services/aureus-signal/engine/snapshot_utils.py`
- **Mô tả**: Utility functions cho việc collect state → snapshot dict và batch insert vào DB
- **Nội dung**:
  ```python
  def build_snapshot(state, candle) -> Dict:
      """Collects all signal values from state into a flat dict for DB insertion."""
  
  async def batch_insert_snapshots(db_pool, symbol, snapshots: List[Dict]):
      """Batch INSERT ... ON CONFLICT DO UPDATE for signal snapshots."""
  ```
- **Điều kiện hoàn thành**: Cả 2 functions hoạt động đúng
- **Test**: Unit test: `build_snapshot()` trả về dict có đủ keys (atr, ema_21, ..., events, active_obs, swing_label)

### Step 3: Implement `signal_computer.py`
- **File mới**: `services/aureus-signal/signal_computer.py`
- **Mô tả**: Main script, chạy standalone
- **Logic**:
  1. Parse CLI args (symbol, start, end)
  2. Connect DB + Redis
  3. Load candles từ `aureus_candles`
  4. Tạo WindowManager + Signals (via `create_signal_set()`)
  5. Replay từng nến: update WindowManager → calculate ALL signals → `build_snapshot()` → append to batch
  6. Mỗi 500 rows → `batch_insert_snapshots()`
  7. Update progress key: `aureus:precompute:status:{symbol}`
- **Điều kiện hoàn thành**: Script chạy được, ghi data vào DB
- **Test**: Chạy cho 1 ngày data → kiểm tra số rows = số candles trong ngày (~1440)

### Step 4: Verify Data Accuracy
- **Mô tả**: So sánh output của signal_computer với live system
- **Test**:
  ```sql
  -- Kiểm tra EMA values khớp
  SELECT time, ema_21, ema_200, htf_trend, session 
  FROM aureus_signal_snapshots 
  WHERE symbol='XAUUSD' 
  ORDER BY time DESC LIMIT 10;
  
  -- Kiểm tra events có xuất hiện
  SELECT time, events 
  FROM aureus_signal_snapshots 
  WHERE symbol='XAUUSD' AND events IS NOT NULL 
  ORDER BY time DESC LIMIT 5;
  ```
- **Điều kiện hoàn thành**: EMA values hợp lý (tương đương live), events xuất hiện đúng chỗ

---

## Điều kiện nghiệm thu Phase B

| # | Điều kiện | Verified? |
|:---|:---|:---|
| B1 | `signal_computer.py` chạy được standalone | [ ] |
| B2 | Pre-compute 1 ngày (~1440 nến) hoàn thành < 10 giây | [ ] |
| B3 | Số rows trong DB = số candles (±1%) | [ ] |
| B4 | EMA/ATR values hợp lý (không null, không 0) | [ ] |
| B5 | Events (CHOCH/BOS/Sweep) xuất hiện đúng nến | [ ] |
| B6 | Re-run (ON CONFLICT) không duplicate data | [ ] |
| B7 | Progress tracking via Redis hoạt động | [ ] |
| B8 | Live system không bị ảnh hưởng | [ ] |

---

## Test End-to-End Phase B

```bash
# 1. Chạy pre-compute cho 1 tuần
cd services/aureus-signal
python signal_computer.py --symbol XAUUSD --start 2026-02-20 --end 2026-02-27

# 2. Kiểm tra row count
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*), min(time), max(time) 
FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
"

# 3. Kiểm tra data quality
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT time, ema_21, atr, htf_trend, session, 
       jsonb_array_length(COALESCE(events, '[]'::jsonb)) as event_count
FROM aureus_signal_snapshots 
WHERE symbol='XAUUSD' 
ORDER BY time DESC LIMIT 20
"

# 4. Re-run → verify no duplicates
python signal_computer.py --symbol XAUUSD --start 2026-02-20 --end 2026-02-27
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*) FROM aureus_signal_snapshots WHERE symbol='XAUUSD'
"
# Count phải giống lần đầu

# 5. Verify live system unaffected
curl http://localhost:8001/api/v1/state/XAUUSD | python -m json.tool | head -5
```
