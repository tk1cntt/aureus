# Step 3: Tích hợp vào Main Loop

> **Phase**: C — Live System Alignment  
> **Thời gian**: ~10 phút | **Risk**: Trung bình (đụng main loop)  
> **Input**: Function `write_signal_snapshot()` từ Step 2  
> **Output**: Live system ghi snapshot mỗi nến mới

---

## Mô tả

Thêm 1 dòng `asyncio.create_task(write_signal_snapshot(...))` vào main loop SAU khi tất cả signals đã chạy xong và Redis state đã được update. Đây là step có risk cao nhất trong Phase C.

## Checklist

- [ ] Dòng `asyncio.create_task()` đặt SAU signal calculation + Redis update
- [ ] Fire-and-forget: không `await` task trong main loop
- [ ] Verify: task failure KHÔNG propagate lên main loop
- [ ] Verify: main loop latency không tăng đáng kể

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Live system ghi snapshot mỗi nến mới | [ ] |
| 2 | Main loop latency tăng < 1ms | [ ] |
| 3 | Task failure (DB down) KHÔNG crash main loop | [ ] |
| 4 | Redis state vẫn cập nhật bình thường | [ ] |

## Test

```bash
# 1. Restart Signal Engine
docker compose -f aureus-foundation.yml up -d --build aureus-signal

# 2. Wait 3 minutes (3 candles)
sleep 180

# 3. Check snapshots in DB
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
SELECT time, symbol, atr, ema_21, session
FROM aureus_signal_snapshots 
WHERE time > NOW() - INTERVAL '5 minutes'
ORDER BY time DESC
"
# Expect: 2-3 rows

# 4. Verify Redis state still working
curl http://localhost:8001/api/v1/state/XAUUSD | python -m json.tool | head -5

# 5. Simulate DB failure (stop TimescaleDB 30s)
docker stop aureus_timescaledb
sleep 30
docker logs aureus_signal_engine --tail 10
# Expect: error log but NO crash
docker start aureus_timescaledb
```

## Rollback

Comment out dòng `asyncio.create_task(write_signal_snapshot(...))`. Live system hoạt động như trước.
