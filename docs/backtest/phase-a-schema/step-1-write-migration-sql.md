# Step 1: Viết Migration SQL

> **Phase**: A — Schema & Migration  
> **Thời gian**: ~10 phút | **Risk**: Rất thấp  
> **Input**: Schema design từ BACKTEST_ARCHITECTURE_PLAN.md Section 3  
> **Output**: File `services/aureus-db-writer/migrate_backtest.sql`

---

## Mô tả

Tạo file SQL migration chứa CREATE TABLE cho 2 bảng mới. File phải idempotent (chạy lại không lỗi).

## Checklist

- [ ] `CREATE TABLE IF NOT EXISTS aureus_signal_snapshots`
  - [ ] Columns: time (TIMESTAMPTZ), symbol (TEXT)
  - [ ] Continuous signals: atr, ema_21, ema_34, ema_55, ema_89, ema_100, ema_200, vol_sma_20
  - [ ] Text signals: htf_trend, market_regime, session
  - [ ] JSONB: events, active_obs
  - [ ] Text: swing_label
  - [ ] UNIQUE constraint: (time, symbol)
- [ ] `SELECT create_hypertable(...)` with `if_not_exists => TRUE`
- [ ] `CREATE INDEX IF NOT EXISTS idx_signal_snapshots_sym_time`
- [ ] `CREATE TABLE IF NOT EXISTS aureus_backtest_runs`
  - [ ] Columns: id (SERIAL PK), created_at, symbol, start_time, end_time
  - [ ] strategy_ids (INTEGER[]), status (TEXT), stats (JSONB), trades (JSONB), equity_curve (JSONB)
- [ ] File syntax-checked (no SQL errors)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | File tồn tại tại đúng path | [ ] |
| 2 | SQL syntax valid (psql --echo-errors) | [ ] |
| 3 | Chạy 2 lần liên tiếp không lỗi (idempotent) | [ ] |
| 4 | Bảng có đúng columns + types | [ ] |

## Test

```bash
# Syntax check (dry run)
cat services/aureus-db-writer/migrate_backtest.sql

# Verify column list matches design
grep -i "CREATE TABLE" services/aureus-db-writer/migrate_backtest.sql
```
