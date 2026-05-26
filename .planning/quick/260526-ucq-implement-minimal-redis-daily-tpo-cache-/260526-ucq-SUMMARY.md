---
phase: 260526-ucq-implement-minimal-redis-daily-tpo-cache-
plan: 01
subsystem: aureus-signal
tags: [quick, tpo, redis, postgres, signal-snapshot]
requires: [aureus_candles, Redis, SymbolState, TPOSignal]
provides: [minimal Redis daily TPO cache, D1-D3 preload, real e2e verifier]
affects: [services/aureus-signal]
tech_stack_added: [redis.asyncio verifier usage, asyncpg verifier usage]
key_files:
  created:
    - services/aureus-signal/engine/tpo_daily_cache.py
    - services/aureus-signal/tests/test_tpo_daily_cache.py
    - services/aureus-signal/tests/test_tpo_daily_cache_live_engine.py
    - services/aureus-signal/scripts/verify_tpo_daily_cache_e2e.py
  modified:
    - services/aureus-signal/engine/state.py
    - services/aureus-signal/engine/signals/tpo.py
    - services/aureus-signal/engine/live_engine.py
decisions:
  - Redis daily TPO chỉ dùng key aureus:tpo:daily:{symbol}:{yyyyMMdd}.
  - D0 vẫn tính từ DataFrame live; D1-D3 ưu tiên state.tpo_daily_cache rồi fallback _compute_daily().
  - Startup preload lỗi Redis/DB thì log warning và giữ fallback cũ.
metrics:
  completed_at: 2026-05-26T00:00:00Z
  tasks_completed: 3
  tests_passed: 9
---

# Quick 260526-ucq: Tóm tắt Redis daily TPO cache tối thiểu

Một dòng: Redis daily TPO cache D1-D3 tối thiểu, build từ aureus_candles khi key thiếu/invalid, nạp vào SymbolState trước TPOSignal hot path.

## Kết quả

- Thêm helper `services/aureus-signal/engine/tpo_daily_cache.py`:
  - Key duy nhất: `aureus:tpo:daily:{symbol}:{yyyyMMdd}`.
  - Validate Redis JSON: `schema_version`, `symbol`, `timeframe`, `yyyymmdd`, `is_closed`, `bars_count`, và POC/VAH/VAL/OPEN/HIGH/LOW/CLOSE.
  - Redis miss/invalid -> query `aureus_candles` đúng UTC day -> DataFrame `t,o,h,l,c,v` -> reuse `TPOSignal._build_tpo_block` -> SET cùng key -> state.
  - DB empty -> không tạo fake TPO, không SET Redis.
- Thêm `SymbolState.tpo_daily_cache` trong `reset()`.
- Sửa `TPOSignal.calculate()`:
  - `tpo_d0` vẫn live từ DataFrame.
  - `tpo_d1`, `tpo_d2`, `tpo_d3` ưu tiên `state.tpo_daily_cache[yyyyMMdd]`.
  - Cache miss giữ fallback `_compute_daily()`.
  - H1/M30 không đổi.
- Sửa `live_engine.py`:
  - Preload D1-D3 sau warmup/delta state có latest candle, trước TPO calc khởi tạo.
  - Nếu preload lỗi, log warning và tiếp tục fallback live-window.
- Thêm unit/fake integration tests và real Postgres + Redis verifier script.

## Blast radius GitNexus trước edit

- `TPOSignal.calculate`: CLI target `TPOSignal.calculate` không tìm thấy; fallback `calculate` resolve sai sang `volume_sma.py`, risk LOW, 0 upstream. Limitation do index stale/ambiguous.
- `SymbolState.reset`: CLI target `SymbolState.reset` không tìm thấy; fallback `reset` resolve sai sang `stable/FenixAI_tradingBot`, risk LOW, 1 upstream. Limitation do index stale/ambiguous.
- `run_signal_engine`: risk LOW, 1 direct caller `services/aureus-signal/main.py`, 0 process affected.

Không có HIGH/CRITICAL risk bị bỏ qua.

## Verification đã chạy

1. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus/services/aureus-signal && ../../.venv/bin/python -m pytest tests/test_tpo_daily_cache.py tests/test_tpo_daily_cache_live_engine.py -q"`
   - Kết quả: `9 passed in 6.73s`.
2. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && docker compose -f docker-compose.dev.yml ps aureus_redis_dev aureus_timescaledb_dev || docker compose -f docker-compose.dev.yml ps"`
   - Kết quả: Redis và TimescaleDB Up.
3. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/scripts/verify_tpo_daily_cache_e2e.py --symbol XAUUSD --redis-url redis://localhost:6380/0 --dsn postgresql://aureus:aureus@localhost:5433/aureus"`
   - Kết quả: fail `InvalidPasswordError`.
   - Xử lý theo `RUN_SERVICES.md` và `.env`: retry DSN đúng repo.
4. `wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./.venv/bin/python services/aureus-signal/scripts/verify_tpo_daily_cache_e2e.py --symbol XAUUSD --redis-url redis://localhost:6380/0 --dsn postgresql://aureus:aureus_password@localhost:5433/aureus"`
   - Kết quả: `{"ok": true, "symbol": "XAUUSD", "dates": ["20260525", "20260524", "20260523"]}`.
5. Window/LIMIT guard:
   - Kết quả: `window_and_limit_unchanged`.

## GitNexus change verification

- `npx gitnexus status`: index stale, indexed commit `29c5b28`, current commit `5b861ad`.
- `npx gitnexus detect-changes --repo Aureus --scope all`: CLI báo `unknown command 'detect-changes'`.
- `npx gitnexus detect_changes --repo Aureus --scope all`: CLI báo `unknown command 'detect_changes'`.
- Limitation: MCP detect_changes không có trong environment; CLI detect command không tồn tại. Đã fallback `npx gitnexus status` và `git -C D:/Aureus diff --stat` theo yêu cầu.

## Deviations from Plan

### Auto-fixed Issues

Không có deviation code ngoài plan.

### Verification adjustment

- DSN trong plan dùng `postgresql://aureus:aureus@localhost:5433/aureus` nhưng runtime password là `aureus_password`. Retry bằng DSN từ repo `.env` để e2e chạy thật với TimescaleDB dev.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: db_seed_verifier | services/aureus-signal/scripts/verify_tpo_daily_cache_e2e.py | Verifier có thể seed M1 rows vào `aureus_candles` cho D1-D3 nếu thiếu fixture rows; đúng plan e2e, không thêm schema/key mới. |

## Known Stubs

Không có stub ảnh hưởng mục tiêu plan.

## Self-Check: PASSED

- File tạo mới tồn tại: `services/aureus-signal/engine/tpo_daily_cache.py`, `tests/test_tpo_daily_cache.py`, `tests/test_tpo_daily_cache_live_engine.py`, `scripts/verify_tpo_daily_cache_e2e.py`.
- File sửa đúng phạm vi: `state.py`, `tpo.py`, `live_engine.py`.
- Không đổi `WindowManager(max_window=2000)`.
- Không đổi `LIMIT 1500`.
- Không tạo status/lock/index/readiness/invalidation Redis key.
