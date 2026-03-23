# Phase D: Recovery Enhancement

> **Độ khó**: ⭐⭐⭐ | **Ảnh hưởng Live**: Trung bình (sửa recalculate_all_signals) | **Thời gian**: 2-3 giờ  
> **Phụ thuộc**: Phase A (schema), Phase B (signal_factory, snapshot_utils)  
> **Mô tả**: Sửa bug critical trong `recalculate_all_signals()` — chạy signals per-candle thay vì chỉ nến cuối, đồng thời ghi signal snapshots cho backfilled data. Thêm snapshot gap detection vào GapDetector.

---

## Checklist tính năng

- [ ] `recalculate_all_signals()` chạy signals PER-CANDLE
- [ ] Ghi signal snapshots cho mỗi nến trong quá trình recalculation
- [ ] Batch insert snapshots (mỗi 500 rows)
- [ ] `GapDetector.find_snapshot_gaps()` — detect missing snapshots
- [ ] `integrity_and_recalc_task` check cả candle gaps lẫn snapshot gaps
- [ ] `lookback_hours` configurable via env var
- [ ] Rollback plan nếu recalc chậm hơn dự kiến

---

## Steps

### Step 1: Refactor `recalculate_all_signals()` — Per-candle Signal Calculation
- **File**: `services/aureus-signal/main.py` (dòng 576-622)
- **Mô tả**: Thay vì chạy signals 1 lần cuối, chạy cho từng nến
- **Thay đổi**:
  - Vòng lặp `for row in reversed(rows)`: Sau `window_manager.update()`, thêm signal calculation + `build_snapshot()`
  - Clear `state.transient_signals = {}` trước mỗi nến
  - Batch insert snapshots mỗi 500 rows
  - Tăng tối thiểu `len(df) >= 5` trước khi chạy signals
- **Điều kiện hoàn thành**: Recalc tạo signal_history đầy đủ + ghi snapshots
- **Test**:
  ```bash
  # Trigger manual recovery
  curl -X POST http://localhost:8001/api/v1/recovery/force/XAUUSD
  # Check snapshots được tạo
  docker exec aureus_timescaledb psql -U aureus -d aureus -c "
  SELECT count(*) FROM aureus_signal_snapshots 
  WHERE symbol='XAUUSD' AND time > NOW() - INTERVAL '24 hours'
  "
  ```

### Step 2: Thêm `find_snapshot_gaps()` vào GapDetector
- **File**: `services/aureus-signal/engine/gap_detector.py`
- **Mô tả**: Method mới so sánh candles vs snapshots để tìm nến có candle nhưng thiếu snapshot
- **Logic**:
  ```sql
  SELECT c.time
  FROM aureus_candles c
  LEFT JOIN aureus_signal_snapshots s ON c.time = s.time AND c.symbol = s.symbol
  WHERE c.symbol = $1 AND c.time > NOW() - INTERVAL '{lookback_hours} hours'
    AND s.time IS NULL
  ORDER BY c.time ASC
  ```
- **Điều kiện hoàn thành**: Detect đúng nến thiếu snapshot
- **Test**: Delete 10 snapshots → call `find_snapshot_gaps()` → expect trả về 10 gaps

### Step 3: Update `integrity_and_recalc_task` — Check Snapshot Gaps
- **File**: `services/aureus-signal/main.py` (dòng 624-675)
- **Mô tả**: Thêm logic check snapshot gaps bên cạnh candle gaps
- **Logic**: Sau khi candle gaps cleared → check snapshot gaps → trigger recalc nếu có
- **Điều kiện hoàn thành**: Tự động detect và bù snapshots thiếu
- **Test**: Delete vài snapshots → chờ → verify chúng được tạo lại

### Step 4: Config `lookback_hours` via Env Var
- **File**: `services/aureus-signal/engine/gap_detector.py`
- **Mô tả**: Thêm env var `GAP_LOOKBACK_HOURS` (default 24, max 168 = 1 tuần)
- **Điều kiện hoàn thành**: Env var hoạt động
- **Test**: Set `GAP_LOOKBACK_HOURS=48` → verify GapDetector check 48 giờ

---

## Điều kiện nghiệm thu Phase D

| # | Điều kiện | Verified? |
|:---|:---|:---|
| D1 | `recalculate_all_signals()` chạy signals per-candle | [ ] |
| D2 | Recalc 2000 nến hoàn thành < 30 giây | [ ] |
| D3 | Signal snapshots được ghi cho mọi nến trong recalc | [ ] |
| D4 | `signal_history` có đầy đủ events (không chỉ nến cuối) | [ ] |
| D5 | `find_snapshot_gaps()` detect đúng | [ ] |
| D6 | Auto-recovery hoạt động: delete snapshots → chúng được tạo lại | [ ] |
| D7 | Live system tiếp tục bình thường sau recalc | [ ] |
| D8 | Dashboard state không bị mất sau recalc | [ ] |

---

## Test End-to-End Phase D

```bash
# 1. Simulate downtime: Stop signal engine 5 phút → restart
docker stop aureus_signal_engine
sleep 300
docker start aureus_signal_engine

# 2. Wait for recovery (watch logs)
docker logs -f aureus_signal_engine --since 1m
# Expect: "[Integrity] Found X gaps" → "[Recalc] Complete"

# 3. Verify candles were backfilled
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT count(*) FROM aureus_candles 
WHERE symbol='XAUUSD' AND time > NOW() - INTERVAL '30 minutes'
"

# 4. Verify snapshots also exist for backfilled period
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT c.time, s.time IS NOT NULL as has_snapshot
FROM aureus_candles c
LEFT JOIN aureus_signal_snapshots s ON c.time = s.time AND c.symbol = s.symbol
WHERE c.symbol='XAUUSD' AND c.time > NOW() - INTERVAL '30 minutes'
ORDER BY c.time DESC
"
# Expect: ALL rows have has_snapshot = true

# 5. Verify dashboard still works
curl http://localhost:8001/api/v1/state/XAUUSD | python -m json.tool | head -5
```

## Rollback Plan

Nếu recalc gây performance issue cho live system:
1. Revert `recalculate_all_signals()` về phiên bản cũ (chỉ chạy signals nến cuối)
2. Giữ `write_signal_snapshot()` từ Phase C (async, không ảnh hưởng)
3. Dùng `signal_computer.py` từ Phase B để bù snapshots manually
