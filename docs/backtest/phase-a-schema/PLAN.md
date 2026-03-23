# Phase A: Schema & Migration

> **Độ khó**: ⭐ | **Ảnh hưởng Live**: Zero | **Thời gian**: ~30 phút  
> **Phụ thuộc**: Không  
> **Mô tả**: Tạo 2 bảng mới trong TimescaleDB. Không đụng code runtime.

---

## Checklist tính năng

- [ ] Bảng `aureus_signal_snapshots` (hypertable)
- [ ] Bảng `aureus_backtest_runs`
- [ ] Index cho query performance
- [ ] Migration script có thể chạy idempotent (IF NOT EXISTS)

---

## Steps

### Step 1: Viết Migration SQL
- **File**: `services/aureus-db-writer/migrate_backtest.sql`
- **Nội dung**:
  - `CREATE TABLE IF NOT EXISTS aureus_signal_snapshots` với columns: time, symbol, atr, ema_21..ema_200, vol_sma_20, htf_trend, market_regime, session, events (JSONB), active_obs (JSONB), swing_label
  - `UNIQUE (time, symbol)`
  - `SELECT create_hypertable(...)` 
  - `CREATE INDEX idx_signal_snapshots_sym_time`
  - `CREATE TABLE IF NOT EXISTS aureus_backtest_runs` với columns: id, created_at, symbol, start_time, end_time, strategy_ids, status, stats, trades, equity_curve
- **Điều kiện hoàn thành**: File SQL không có syntax error
- **Test**: `cat migrate_backtest.sql` → review syntax

### Step 2: Chạy Migration trên TimescaleDB
- **Lệnh**: 
  ```bash
  docker cp migrate_backtest.sql aureus_timescaledb:/tmp/
  docker exec aureus_timescaledb psql -U aureus -d aureus -f /tmp/migrate_backtest.sql
  ```
- **Điều kiện hoàn thành**: Không có error
- **Test**:
  ```bash
  docker exec aureus_timescaledb psql -U aureus -d aureus -c "\dt aureus_signal*"
  docker exec aureus_timescaledb psql -U aureus -d aureus -c "\dt aureus_backtest*"
  ```

### Step 3: Verify Schema
- **Test**: Insert 1 test row + SELECT + DELETE
  ```sql
  INSERT INTO aureus_signal_snapshots (time, symbol, atr) VALUES (NOW(), 'TEST', 5.0);
  SELECT * FROM aureus_signal_snapshots WHERE symbol = 'TEST';
  DELETE FROM aureus_signal_snapshots WHERE symbol = 'TEST';
  ```
- **Điều kiện hoàn thành**: Insert/Select/Delete thành công, hypertable hoạt động

---

## Điều kiện nghiệm thu Phase A

| # | Điều kiện | Verified? |
|:---|:---|:---|
| A1 | Bảng `aureus_signal_snapshots` tồn tại và là hypertable | [ ] |
| A2 | Bảng `aureus_backtest_runs` tồn tại | [ ] |
| A3 | Index `idx_signal_snapshots_sym_time` tồn tại | [ ] |
| A4 | UNIQUE constraint (time, symbol) hoạt động | [ ] |
| A5 | ON CONFLICT DO UPDATE hoạt động | [ ] |
| A6 | Bảng hiện tại (candles, swing_points, etc.) KHÔNG bị ảnh hưởng | [ ] |

---

## Test End-to-End Phase A

```bash
# 1. Kiểm tra tất cả tables
docker exec aureus_timescaledb psql -U aureus -d aureus -c "\dt aureus_*"

# 2. Kiểm tra hypertable
docker exec aureus_timescaledb psql -U aureus -d aureus -c "SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'aureus_signal_snapshots'"

# 3. Kiểm tra UNIQUE constraint
docker exec aureus_timescaledb psql -U aureus -d aureus -c "
INSERT INTO aureus_signal_snapshots (time, symbol, atr) VALUES ('2025-01-01', 'TEST', 1.0);
INSERT INTO aureus_signal_snapshots (time, symbol, atr) VALUES ('2025-01-01', 'TEST', 2.0) ON CONFLICT (time, symbol) DO UPDATE SET atr = 2.0;
SELECT atr FROM aureus_signal_snapshots WHERE symbol = 'TEST';
-- Expect: atr = 2.0
DELETE FROM aureus_signal_snapshots WHERE symbol = 'TEST';
"

# 4. Kiểm tra live tables not affected
docker exec aureus_timescaledb psql -U aureus -d aureus -c "SELECT count(*) FROM aureus_candles LIMIT 1"
```
