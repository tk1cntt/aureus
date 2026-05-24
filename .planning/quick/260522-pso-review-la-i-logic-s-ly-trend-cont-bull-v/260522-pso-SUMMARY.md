# 260522-PSO SUMMARY

## Kết luận

Có bug runtime thật: `TREND_CONT_BULL` / `TREND_CONT_BEAR` không vào lệnh hôm nay vì filter `trend_cont_poc_cisd` cần `current_poc = tpo_d0.POC`, nhưng snapshot DB runtime mới nhất đang ghi `d0_poc` và `d0_close` rỗng. `d1_poc` / `d1_close` có dữ liệu.

Không sửa code trong lượt này vì Task 1 chỉ mới chứng minh lỗi nguồn dữ liệu runtime; cần fix surgical ở nguồn sinh/persist `tpo_d0` sau khi chạy GitNexus impact cho symbol liên quan.

## Evidence source

### Source seed strategy

File: `services/aureus-signal/engine/strategies/seed_strategies.py`

- `TREND_CONT_BULL` có `context_filters = [{"type": "trend_cont_poc_cisd", "direction": "bullish"}]`
- sequence: `choch_up`
- direction: `BUY`
- `TREND_CONT_BEAR` có `context_filters = [{"type": "trend_cont_poc_cisd", "direction": "bearish"}]`
- sequence: `choch_down`
- direction: `SELL`

### Source evaluator

File: `services/aureus-signal/engine/strategies/template.py`

Filter `trend_cont_poc_cisd` đọc:

- `previous_close = _tpo_value("tpo_d1", ["CLOSE", "close"])`
- `previous_poc = _tpo_value("tpo_d1", ["POC", "poc"])`
- `current_poc = _tpo_value("tpo_d0", ["POC", "poc"])`
- `current_close` từ `last_candle`, log close, hoặc `current_signal.close`
- H1 CISD từ `transient_signals`: `cisd_h1_bullish`, `cisd_h1_bearish`, hoặc `cisd_h1.direction/status/value`

Fail closed nếu thiếu 1 trong 4 giá trị hoặc H1 CISD không đúng hướng.

### GitNexus evidence

Command:

```bash
npx gitnexus query "TREND_CONT_BULL TREND_CONT_BEAR trend_cont_poc_cisd strategy evaluation" --repo Aureus
npx gitnexus context TemplateStrategy --repo Aureus
```

Result:

- Query tìm đúng vùng tests/context filter, không có process mapped.
- `TemplateStrategy` symbol: `services/aureus-signal/engine/strategies/template.py:15-1069`
- Methods liên quan: `_evaluate_context`, `_evaluate_sequence`, `evaluate`, `on_bar_close`, `build_order_plan`.

### DB runtime template

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT name, config->'context_filters' AS context_filters, config->'sequence' AS sequence, min_score FROM aureus_strategy_templates WHERE name IN ('TREND_CONT_BULL','TREND_CONT_BEAR') ORDER BY name;\""
```

Result:

| name | context_filters | sequence | min_score |
| --- | --- | --- | --- |
| TREND_CONT_BEAR | `[{"type":"trend_cont_poc_cisd","direction":"bearish"}]` | `choch_down` | 3 |
| TREND_CONT_BULL | `[{"type":"trend_cont_poc_cisd","direction":"bullish"}]` | `choch_up` | 3 |

DB seed đúng, runtime không chỉ source.

### DB runtime symbol assignments

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT ss.symbol, st.name, ss.is_active, ss.created_at FROM aureus_symbol_strategies ss JOIN aureus_strategy_templates st ON st.id = ss.strategy_id WHERE st.name IN ('TREND_CONT_BULL','TREND_CONT_BEAR') ORDER BY ss.symbol, st.name;\""
```

Result: 16 active links, both strategies active for:

- AUDUSD
- BTCUSD
- ETHUSD
- EURUSD
- GBPUSD
- USDJPY
- USTEC
- XAUUSD

### DB trade result today

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT strategy_name, COUNT(*) AS total, MIN(entry_time) AS first_entry, MAX(entry_time) AS last_entry FROM aureus_trade_journal WHERE strategy_name IN ('TREND_CONT_BULL','TREND_CONT_BEAR') AND COALESCE(entry_time, created_at) >= '2026-05-22 00:00:00+00' GROUP BY strategy_name ORDER BY strategy_name;\""
```

Result: `0 rows`.

Yesterday baseline still active before issue window:

| strategy_name | total | wins | losses | winrate_pct | pnl | first_entry | last_entry |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| TREND_CONT_BEAR | 26 | 9 | 15 | 37.50 | -240.75 | 2026-05-21 02:24:07+00 | 2026-05-21 18:09:15+00 |
| TREND_CONT_BULL | 25 | 12 | 12 | 50.00 | 263.41 | 2026-05-21 02:00:23+00 | 2026-05-21 19:46:05+00 |

### DB signal snapshot evidence: root cause

Command:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker exec -i aureus_timescaledb_dev psql -U aureus -d aureus -c \"SELECT trace_id, symbol, timeframe, created_at, d0_poc, d0_close, d1_poc, d1_close FROM aureus_trade_signal_snapshots ORDER BY created_at DESC LIMIT 10;\""
```

Result sample:

| trace_id | symbol | timeframe | created_at | d0_poc | d0_close | d1_poc | d1_close |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BTCUSD:607:1779461220 | BTCUSD | M1 | 2026-05-22 14:51:04+00 | null | null | 77169.7 | 77625.97 |
| USTEC:607:1779460740 | USTEC | M1 | 2026-05-22 14:45:21+00 | null | null | 29145 | 29360 |
| XAUUSD:607:1779460320 | XAUUSD | M1 | 2026-05-22 14:37:01+00 | null | null | 4532.68 | 4543.05 |
| EURUSD:642:1779460200 | EURUSD | M1 | 2026-05-22 14:31:03+00 | null | null | 1.16214 | 1.16171 |

Meaning:

- `tpo_d1` works: prior day POC/close available.
- `tpo_d0` missing in persisted runtime evidence.
- `trend_cont_poc_cisd` requires D0 POC. Missing D0 POC makes filter fail closed.
- This matches symptom: no `TREND_CONT_BULL/BEAR` orders today after filter addition.

### Runtime logs

Signal service recent logs show indicator activity and TPO profiling, no crash:

- `tpo` profiling present in `aureus-signal-dev`.
- CISD events present, e.g. BTCUSD bullish/bearish, XAUUSD bullish, EURUSD bearish.
- No filtered signal log lines for `TREND_CONT_BULL/BEAR` found in `aureus-signal-dev` grep.

Executor log grep produced no useful filtered output in this pass. Tail command ran background due large output; no conclusion from it here.

## Test

Initial repo-root command failed due import path:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python -m pytest services/aureus-signal/tests/test_seed_strategies_context_filters.py -q"
```

Error:

```text
ModuleNotFoundError: No module named 'engine'
```

Per `RUN_SERVICES.md`, reran from service path:

```bash
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && PYTHONPATH=. ../../.venv/bin/python -m pytest tests/test_seed_strategies_context_filters.py -q"
```

Result:

```text
13 passed in 5.25s
```

## Commands with errors and handling

- `aureus_symbol_strategies.strategy_template_id` wrong column. Inspected schema, correct column is `strategy_id`.
- `aureus_trade_journal.opened_at` wrong column. Inspected schema, correct timing columns include `entry_time`, `created_at`.
- WSL intermittently returned `Wsl/Service/0x8007274c`; retried same command successfully.
- `docker logs ... grep ...` sometimes returned no output; treated as no matching lines, not runtime crash.

## Code changes

None in this quick execution.

Reason: Task 1 found concrete runtime data bug, but no symbol edited yet. Next fix must target TPO D0 generation/persistence path, after `gitnexus_impact` on exact symbol.

## Next recommended surgical fix

Fix likely area:

- `services/aureus-signal/engine/signals/tpo.py` `TPOSignal._compute_daily()` / `_build_tpo_block()` if D0 block returns null.
- Or `services/aureus-signal/engine/signal_event_publisher.py` `_build_signal_snapshot_from_indicator_snapshot()` if D0 block exists in state but not persisted.
- Or `services/aureus-trader/journal.py` if payload has D0 but DB insert maps null.

Required next steps before edit:

1. Query live signal payload/state path to see whether `indicator_snapshot.tpo_d0` is null before publishing.
2. Run `gitnexus_impact` for exact symbol to edit.
3. Add regression test proving `d0_poc` persists when `tpo_d0.POC` exists.
4. Run DB E2E because database-related behavior affects signal snapshots.
