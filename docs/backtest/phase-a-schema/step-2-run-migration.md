# Step 2: Chạy Migration trên TimescaleDB

> **Phase**: A — Schema & Migration  
> **Thời gian**: ~5 phút | **Risk**: Thấp  
> **Input**: File `migrate_backtest.sql` từ Step 1  
> **Output**: 2 bảng mới tồn tại trong TimescaleDB

---

## Mô tả

Copy file SQL vào Docker container TimescaleDB và chạy migration. Verify bảng được tạo thành công.

## Checklist

- [ ] Copy file SQL vào container
- [ ] Chạy migration via `psql`
- [ ] Verify `aureus_signal_snapshots` tồn tại
- [ ] Verify `aureus_backtest_runs` tồn tại
- [ ] Verify hypertable status
- [ ] Verify index tồn tại

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Chạy migration không error | [ ] |
| 2 | `\dt aureus_signal*` hiển thị bảng | [ ] |
| 3 | `\dt aureus_backtest*` hiển thị bảng | [ ] |
| 4 | Hypertable info query trả về row | [ ] |
| 5 | Bảng hiện tại (`aureus_candles`, etc.) KHÔNG bị ảnh hưởng | [ ] |

## Test

```bash
# Copy + Execute
docker cp services/aureus-db-writer/migrate_backtest.sql aureus_timescaledb:/tmp/
docker exec aureus_timescaledb psql -U aureus -d aureus -f /tmp/migrate_backtest.sql

# Verify tables exist
docker exec aureus_timescaledb psql -U aureus -d aureus -c "\dt aureus_signal*"
docker exec aureus_timescaledb psql -U aureus -d aureus -c "\dt aureus_backtest*"

# Verify hypertable
docker exec aureus_timescaledb psql -U aureus -d aureus -c \
  "SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'aureus_signal_snapshots'"

# Verify existing tables unaffected
docker exec aureus_timescaledb psql -U aureus -d aureus -c "SELECT count(*) FROM aureus_candles LIMIT 1"
docker exec aureus_timescaledb psql -U aureus -d aureus -c "SELECT count(*) FROM aureus_swing_points LIMIT 1"
```

## Rollback

```bash
# Nếu cần rollback:
docker exec aureus_timescaledb psql -U aureus -d aureus -c "DROP TABLE IF EXISTS aureus_signal_snapshots CASCADE"
docker exec aureus_timescaledb psql -U aureus -d aureus -c "DROP TABLE IF EXISTS aureus_backtest_runs CASCADE"
```
