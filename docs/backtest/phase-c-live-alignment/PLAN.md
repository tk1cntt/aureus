# Phase C: Live System Alignment

> **Độ khó**: ⭐⭐ | **Ảnh hưởng Live**: Thấp (thêm async write) | **Thời gian**: 1-2 giờ  
> **Phụ thuộc**: Phase A (schema), Phase B (shared functions)  
> **Mô tả**: Live Signal Engine cũng ghi signal snapshots mỗi nến (async, fire-and-forget). Data liền mạch giữa pre-computed (cũ) và live (mới).

---

## Checklist tính năng

- [ ] Function `write_signal_snapshot()` trong `main.py`
- [ ] Gọi via `asyncio.create_task()` (không block main loop)
- [ ] Dùng `build_snapshot()` từ `snapshot_utils.py` (shared với Phase B)
- [ ] `ON CONFLICT DO UPDATE` cho idempotent
- [ ] Error handling — log error nhưng KHÔNG crash main loop
- [ ] DB connection pool cho async writes

---

## Steps

### Step 1: Thêm DB Pool vào Signal Engine
- **File**: `services/aureus-signal/main.py`
- **Mô tả**: Signal Engine hiện tại chỉ dùng Redis. Cần thêm asyncpg connection pool cho TimescaleDB
- **Vị trí**: Trong `main()` function, sau khi tạo Redis connection
- **Nội dung**:
  ```python
  db_pool = await asyncpg.create_pool(os.getenv("POSTGRES_URL", "postgresql://aureus:aureus@localhost:5432/aureus"))
  ```
- **Điều kiện hoàn thành**: Pool connect thành công khi Signal Engine start
- **Test**: Restart Signal Engine → log cho thấy "DB pool connected"

### Step 2: Thêm `write_signal_snapshot()` function
- **File**: `services/aureus-signal/main.py`
- **Mô tả**: Async function ghi 1 snapshot row, dùng `build_snapshot()` từ Phase B
- **Vị trí**: Sau dòng ~390 (sau vòng lặp signal calculation)
- **Logic**:
  1. `snapshot = build_snapshot(state, candle)` (from snapshot_utils)
  2. `await db_pool.execute(INSERT ... ON CONFLICT DO UPDATE)`
  3. Wrap trong try/except — log error nhưng KHÔNG re-raise
- **Điều kiện hoàn thành**: Function không crash main loop khi DB down
- **Test**: Tạm disconnect DB → log error, live system tiếp tục bình thường

### Step 3: Integrate vào main loop
- **File**: `services/aureus-signal/main.py`
- **Vị trí**: Sau signal calculation loop + Redis state.set()
- **Nội dung**:
  ```python
  asyncio.create_task(write_signal_snapshot(db_pool, symbol, ts_unix, state))
  ```
- **Điều kiện hoàn thành**: Snapshot được ghi mỗi nến mới
- **Test**: Chờ 3 nến mới → query DB → verify 3 rows mới

### Step 4: Rebuild & Test
- **Mô tả**: Rebuild Docker image, restart, verify
- **Điều kiện hoàn thành**: Signal Engine chạy bình thường + ghi snapshots
- **Test**: Monitor logs 5 phút, kiểm tra:
  - Không có error mới
  - Latency signal processing không tăng đáng kể
  - DB có rows mới mỗi phút

---

## Điều kiện nghiệm thu Phase C

| # | Điều kiện | Verified? |
|:---|:---|:---|
| C1 | Live Signal Engine ghi snapshot mỗi nến mới | [ ] |
| C2 | Signal processing latency tăng < 2ms | [ ] |
| C3 | DB error KHÔNG crash live system | [ ] |
| C4 | Snapshot format giống Phase B (cùng `build_snapshot()`) | [ ] |
| C5 | `ON CONFLICT DO UPDATE` hoạt động | [ ] |
| C6 | Redis state vẫn được cập nhật bình thường | [ ] |
| C7 | Dashboard vẫn hoạt động bình thường | [ ] |

---

## Test End-to-End Phase C

```bash
# 1. Rebuild + restart
docker compose -f aureus-foundation.yml up -d --build aureus-signal

# 2. Monitor logs (5 phút)
docker logs -f aureus_signal_engine --since 1m

# 3. Kiểm tra snapshots
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT time, symbol, ema_21, atr, session 
FROM aureus_signal_snapshots 
WHERE time > NOW() - INTERVAL '10 minutes'
ORDER BY time DESC
"

# 4. Kiểm tra dashboard vẫn OK
curl http://localhost:8001/api/v1/state/XAUUSD | python -m json.tool | head -3

# 5. Simulate DB failure → verify graceful handling
# (Tạm stop TimescaleDB container 30s → check signal engine logs)
```
