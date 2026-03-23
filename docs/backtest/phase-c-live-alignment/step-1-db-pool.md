# Step 1: Thêm DB Pool vào Signal Engine

> **Phase**: C — Live System Alignment  
> **Thời gian**: ~15 phút | **Risk**: Thấp  
> **Input**: DB connection string (env var)  
> **Output**: `asyncpg.Pool` trong Signal Engine main

---

## Mô tả

Signal Engine hiện chỉ dùng Redis. Thêm asyncpg connection pool cho TimescaleDB. Pool tạo trong `main()`, truyền xuống các function cần dùng.

## Checklist

- [ ] Thêm `import asyncpg` vào `main.py`
- [ ] Thêm env var `POSTGRES_URL` vào docker-compose
- [ ] Tạo pool: `db_pool = await asyncpg.create_pool(...)`
- [ ] Pass `db_pool` vào places cần thiết
- [ ] Cleanup: `await db_pool.close()` khi shutdown
- [ ] Log "DB pool connected" khi thành công

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Signal Engine start không lỗi | [ ] |
| 2 | Log "DB pool connected" xuất hiện | [ ] |
| 3 | Pool connect tới TimescaleDB thành công | [ ] |
| 4 | Signal processing không bị ảnh hưởng | [ ] |

## Test

```bash
# Rebuild + restart
docker compose -f aureus-foundation.yml up -d --build aureus-signal

# Check logs
docker logs aureus_signal_engine --tail 20
# Expect: "DB pool connected" hoặc tương tự

# Verify signals still working
sleep 120  # Wait 2 minutes for 2 candles
curl http://localhost:8001/api/v1/state/XAUUSD | python -m json.tool | head -5
```

## Rollback

Remove `asyncpg.create_pool()` line, Signal Engine chạy như cũ.
