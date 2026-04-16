# Phase 43: b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the - Research

**Researched:** 2026-04-16
**Domain:** Multi-timeframe candle-color + Bollinger Bands snapshot persistence on M1 cadence
**Confidence:** HIGH

## User Constraints (from CONTEXT.md)

### Locked Decisions
### Màu nến đa khung thời gian
- **D-01:** Màu nến cho mỗi TF được xác định theo quy tắc thống nhất từ OHLC của nến TF đó:
  - `BULLISH` nếu `close > open`
  - `BEARISH` nếu `close < open`
  - `DOJI` nếu `close == open` (sau khi normalize theo digits của symbol)
- **D-02:** Lưu key rõ ràng theo TF trong snapshot: `candle_color_d1`, `candle_color_h1`, `candle_color_m30`, `candle_color_m15`, `candle_color_m5`.
- **D-03:** Giá trị màu nến phải uppercase để đồng nhất với các enum/status đã có trong hệ thống.

### Bollinger Bands đa khung thời gian
- **D-04:** BB cho mỗi TF lưu đủ 3 line chuẩn: `upper`, `middle`, `lower` (không chỉ status rút gọn), để downstream dùng linh hoạt cho dashboard/analytics.
- **D-05:** TF bắt buộc cho BB: `M1`, `M5`, `M15`, `M30`, `H1`.
- **D-06:** Cấu trúc đề xuất theo namespace `bb_<tf>` để dễ parse và tránh vỡ contract cũ, ví dụ:
  - `bb_m1: {upper, middle, lower}`
  - `bb_m5: {upper, middle, lower}`
  - ...

### Đồng bộ theo từng nến M1
- **D-07:** Mỗi khi chốt nến M1, ghi 1 snapshot DB; snapshot này chứa giá trị mới nhất khả dụng của tất cả TF yêu cầu.
- **D-08:** Với TF lớn hơn M1 (M5/M15/M30/H1/D1), dùng **last closed candle** tại thời điểm M1 đó (không dùng nến đang hình thành) để đảm bảo tính ổn định/replay được.
- **D-09:** Không chờ TF lớn đóng nến mới ghi DB; vẫn ghi mỗi M1 để giữ chuỗi dữ liệu liên tục cho phân tích theo trục thời gian M1.

### Quy ước lưu DB (naming/null/fallback)
- **D-10:** Nếu tại thời điểm M1 chưa đủ dữ liệu để tính màu nến/BB ở TF nào, lưu `null` cho TF đó (không dùng giá trị giả như 0 hay string placeholder).
- **D-11:** Không backfill nội suy trong phase này; planner có thể chọn xử lý data quality downstream nếu cần.
- **D-12:** Giữ compatibility: trường mới được bổ sung theo kiểu additive, không đổi nghĩa các field indicator đã có (`emas`, `atr_14`, `vol_sma_20`, `htf_trend`, `cisd_mtf`).

### Claude's Discretion
- Chi tiết vị trí code cụ thể để inject snapshot (module hiện có hay helper mới nhỏ)
- Cách tổ chức migration DB (JSONB-only hoặc cột tách) miễn đáp ứng naming đã chốt
- Mức log chi tiết cho trường hợp null ở TF lớn

### Deferred Ideas (OUT OF SCOPE)
### Reviewed Todos (not folded)
- `Investigate missing OB events in signal_history_normalized` — deferred vì ngoài scope phase 43 (liên quan event history integrity, không phải bổ sung indicator fields)
- `Remove market_regime use htf_trend` — deferred vì là thay đổi logic signal classification/regime, không phải mở rộng dữ liệu indicator đa TF theo yêu cầu hiện tại

## Project Constraints (from CLAUDE.md)

- Bắt buộc giao tiếp tiếng Việt. [VERIFIED: D:/Aureus/CLAUDE.md]
- Khi sửa code thực tế phải chạy GitNexus impact analysis trước khi sửa symbol, và detect_changes trước commit. [VERIFIED: D:/Aureus/CLAUDE.md]
- Ưu tiên thay đổi tối thiểu, không refactor lan sang vùng ngoài scope. [VERIFIED: D:/Aureus/CLAUDE.md]
- Không commit nếu chưa kiểm tra phạm vi thay đổi bằng GitNexus. [VERIFIED: D:/Aureus/CLAUDE.md]

## Summary

Phase 43 là phase mở rộng snapshot/persistence, không đổi trigger/notification logic. [VERIFIED: D:/Aureus/.planning/phases/43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the/43-CONTEXT.md] Hiện pipeline đã có điểm gắn snapshot theo từng M1 trong `live_engine.py` thông qua `build_snapshot()` và insert vào `aureus_signal_snapshots`, nên hướng đúng là mở rộng snapshot schema + builder, không tạo pipeline mới. [VERIFIED: D:/Aureus/services/aureus-signal/engine/live_engine.py, D:/Aureus/services/aureus-signal/engine/snapshot_utils.py]

Codebase đã có resampler M1→TF lớn với boundary UTC chuẩn và semantics “last row là forming candle”. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/resampler.py] Do decision D-08 yêu cầu dùng last closed candle, planner phải ép rule chọn candle HTF áp chót khi row cuối đang forming, tránh nhiễu replay. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/resampler.py, D:/Aureus/.planning/phases/43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the/43-CONTEXT.md]

Schema DB hiện chưa có cột cho candle_color_* và bb_*. [VERIFIED: D:/Aureus/services/aureus-db-writer/schema.sql] Vì `insert_single_snapshot()` dùng danh sách cột tĩnh, phase này bắt buộc có migration + cập nhật SQL insert/upsert đồng bộ. [VERIFIED: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py]

**Primary recommendation:** Mở rộng `build_snapshot()` + `schema.sql` + `insert_single_snapshot()/batch_insert_snapshots()` theo hướng additive columns, tính MTF từ `resample_to_tf()` với strict rule last-closed + null-first.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.9 | Runtime cho signal/db-writer | Đang là runtime hiện diện trên máy và phù hợp codebase hiện tại. [VERIFIED: local `python --version`] |
| pandas | 3.0.1 | Resample M1→M5/M15/M30/H1/D1, xử lý OHLCV | `resample_to_tf()` phụ thuộc pandas DataFrame/resample API. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/resampler.py, D:/Aureus/services/aureus-signal/requirements.txt] |
| asyncpg | 0.31.0 | Insert/upsert snapshot vào TimescaleDB/PostgreSQL | Toàn bộ insert snapshot đang dùng asyncpg pool + execute/executemany. [VERIFIED: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py, D:/Aureus/services/aureus-db-writer/main.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis (redis-py async) | 7.2.0 | Stream ingestion + state/event bus | Dùng cho live stream M1, không thay đổi trong phase nhưng là dependency pipeline. [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt, D:/Aureus/services/aureus-db-writer/main.py] |
| numpy | 2.4.2 | Tính toán số học indicator (qua stack pandas/engine) | Dùng khi implement BB calculation ổn định theo vectorized ops. [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Column-per-field cho BB/candle-color | JSONB blob duy nhất | JSONB giảm migration churn nhưng giảm khả năng query/index trực tiếp theo TF line. [ASSUMED] |
| Tự viết resample loop | pandas resample hiện có | Tự viết dễ sai boundary/forming-candle semantics. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/resampler.py] |

**Installation:**
```bash
pip install -r D:/Aureus/services/aureus-signal/requirements.txt
pip install -r D:/Aureus/services/aureus-db-writer/requirements.txt
```

**Version verification:** Dự án phase này dùng Python stack (không phải npm package flow). Phiên bản được xác minh từ requirements nội bộ + runtime local. [VERIFIED: D:/Aureus/services/aureus-signal/requirements.txt, D:/Aureus/services/aureus-db-writer/requirements.txt, local runtime]

## Architecture Patterns

### Recommended Project Structure
```text
services/aureus-signal/engine/
├── snapshot_utils.py      # Build + insert snapshot row (điểm mở rộng chính)
├── signals/resampler.py   # M1→HTF resample + forming semantics
├── live_engine.py         # Trigger build_snapshot mỗi M1
└── state_snapshot.py      # Unified snapshot object (nên sync field mới)

services/aureus-db-writer/
└── schema.sql             # DB schema authoritative cho aureus_signal_snapshots
```

### Pattern 1: Additive Snapshot Extension
**What:** Thêm field mới vào snapshot dict + SQL insert/upsert mà không đổi nghĩa field cũ.
**When to use:** Mọi phase mở rộng indicator data nhưng cần backward compatibility.
**Example:**
```python
# Source: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py
return {
  'time': dt,
  'symbol': symbol,
  'atr': state.atr if state.atr else None,
  # ... existing fields giữ nguyên
  # + candle_color_* / bb_* thêm mới theo additive
}
```

### Pattern 2: Last-Closed HTF Sampling
**What:** Với TF > M1, luôn đọc nến đã đóng gần nhất tại thời điểm M1.
**When to use:** Mọi dữ liệu MTF cần replay ổn định.
**Example:**
```python
# Source: D:/Aureus/services/aureus-signal/engine/signals/resampler.py
# The last row is the forming (incomplete) HTF candle.
# => planner must use previous row for last-closed semantics
```

### Anti-Patterns to Avoid
- **Đọc nến HTF forming:** gây jitter giá trị BB/color giữa các lần replay. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/resampler.py]
- **Đổ giá trị giả (0/"NA") thay vì null:** vi phạm D-10, làm sai downstream analytics. [VERIFIED: D:/Aureus/.planning/phases/43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the/43-CONTEXT.md]
- **Sửa contract field cũ:** trái D-12 và dễ phá consumer cũ. [VERIFIED: D:/Aureus/.planning/phases/43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the/43-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resample time boundary M1→HTF | Vòng lặp tự gom candle | `resample_to_tf()` hiện có | Đã chuẩn hóa UTC boundary + OHLC aggregation. [VERIFIED: D:/Aureus/services/aureus-signal/engine/signals/resampler.py] |
| Snapshot persistence semantics | SQL string ad-hoc ở nhiều nơi | `insert_single_snapshot` + `batch_insert_snapshots` | Tránh lệch schema/ON CONFLICT giữa code paths. [VERIFIED: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py] |
| Signal-state serialization mới | Class custom khác | `StateSnapshot` hiện có | Đã là format thống nhất live/db/backtest. [VERIFIED: D:/Aureus/services/aureus-signal/engine/state_snapshot.py] |

**Key insight:** Độ khó phase này nằm ở đồng bộ contract giữa builder↔schema↔upsert, không nằm ở thuật toán phức tạp.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Bảng `aureus_signal_snapshots` đã chứa historical rows nhưng chưa có field candle_color/bb. [VERIFIED: D:/Aureus/services/aureus-db-writer/schema.sql] | **Data migration + code edit**: ALTER TABLE add columns nullable; không cần backfill (theo D-11). |
| Live service config | Không thấy evidence config UI-only ngoài git cho phase này trong phạm vi đã kiểm tra. [ASSUMED] | Xác nhận thủ công khi triển khai prod (nếu có dashboard query hardcoded). |
| OS-registered state | Không có thành phần OS registration liên quan trực tiếp tên field snapshot. [ASSUMED] | None (code edit only). |
| Secrets/env vars | Không có env key hiện tại dành riêng cho BB/candle_color. [VERIFIED: D:/Aureus/services/aureus-signal/engine/live_engine.py] | None (code edit only). |
| Build artifacts | Không có artifact mang schema field name mới; rủi ro nằm ở migration chưa apply. [ASSUMED] | Chạy migration/schema apply trước deploy service. |

## Common Pitfalls

### Pitfall 1: Off-by-one khi lấy HTF candle
**What goes wrong:** Lấy row cuối từ resample làm last-closed, nhưng thực tế đó là forming.
**Why it happens:** Docstring resampler ghi rõ row cuối là incomplete candle.
**How to avoid:** Luôn kiểm tra đủ >=2 rows rồi lấy `iloc[-2]` cho TF> M1.
**Warning signs:** BB/color HTF thay đổi khi replay cùng timestamp M1.

### Pitfall 2: Quên cập nhật cả single insert và batch insert
**What goes wrong:** Một đường ghi DB thành công, đường còn lại fail do mismatch số cột.
**Why it happens:** `insert_single_snapshot` và `batch_insert_snapshots` giữ SQL độc lập.
**How to avoid:** Cập nhật cùng lúc 3 nơi: schema + single + batch.
**Warning signs:** Log warning insert failed chỉ xuất hiện ở một chế độ chạy.

### Pitfall 3: Không normalize DOJI theo digits
**What goes wrong:** Sai phân loại DOJI do float precision.
**Why it happens:** So sánh trực tiếp `close == open` trên float raw.
**How to avoid:** Round theo symbol digits rồi so sánh.
**Warning signs:** Tỷ lệ DOJI bất thường thấp/0 trên symbol digits cao.

## Code Examples

Verified patterns from official sources in-repo:

### Build snapshot row from state
```python
# Source: D:/Aureus/services/aureus-signal/engine/snapshot_utils.py
snapshot = build_snapshot(state, data)
await insert_single_snapshot(db_pool, snapshot)
```

### Resample M1 to higher timeframe
```python
# Source: D:/Aureus/services/aureus-signal/engine/signals/resampler.py
htf = resample_to_tf(df_m1, "M15")
# htf.iloc[-1] is forming candle per module contract
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Snapshot tập trung EMA/ATR/trend/session + events | Snapshot đã trở thành trung tâm hợp nhất state (thêm strategy_progress, obs_full...) | Qua các phase trước (ít nhất Phase 7+) [VERIFIED: snapshot_utils.py, state_snapshot.py] | Dễ mở rộng thêm field indicator nếu giữ additive contract |
| Telegram indicator snapshot là lightweight riêng | DB snapshot vẫn dùng heavy snapshot_utils path | Phase 40 [VERIFIED: 40-CONTEXT + indicator_snapshot.py] | Phase 43 nên mở rộng DB snapshot path, không lẫn với Telegram formatter |

**Deprecated/outdated:**
- Không có cơ chế BB MTF trong `aureus_signal_snapshots` hiện tại. [VERIFIED: D:/Aureus/services/aureus-db-writer/schema.sql]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Không có live service config ngoài git cần sửa cho field mới | Runtime State Inventory | Có thể thiếu bước cập nhật dashboard/query ở hệ thống ngoài repo |
| A2 | Không có OS-registered state liên quan phase này | Runtime State Inventory | Rủi ro thấp, chủ yếu ảnh hưởng checklist deploy |
| A3 | Không có build artifact cần rename đặc thù | Runtime State Inventory | Có thể thiếu bước reinstall nếu deploy dùng image cũ |

## Open Questions (RESOLVED)

1. **DB modeling cho BB nên tách cột hay JSONB?** **RESOLVED**
   - Resolution: Chốt dùng **JSONB object per timeframe** theo naming đã khóa trong CONTEXT: `bb_m1`, `bb_m5`, `bb_m15`, `bb_m30`, `bb_h1`, mỗi field có shape `{upper, middle, lower}`.
   - Why: Bám đúng D-06, giữ contract object ổn định, giảm migration churn so với tách 15 cột số riêng lẻ.
   - Verification impact: Plan phải có migration additive + test payload shape cho từng `bb_<tf>` key.

2. **Nguồn dữ liệu BB nên tính online hay lấy từ signal module có sẵn?** **RESOLVED**
   - Resolution: Chốt theo thứ tự ưu tiên: **(a)** reuse nếu tìm thấy module BB đã tồn tại trong codebase; **(b)** nếu không có thì implement tính BB tối thiểu trong snapshot path bằng pandas rolling chuẩn, không thêm pipeline mới.
   - Why: Giữ thay đổi tối thiểu, đúng boundary phase (snapshot/persistence), tránh mở rộng scope sang hệ signal trigger.
   - Verification impact: Plan phải có task kiểm tra tồn tại BB module trước khi code và có test chứng minh output `upper/middle/lower` hợp lệ + null-first khi thiếu dữ liệu.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python | Signal engine/db-writer execution | ✓ | 3.12.9 | — |
| pip | Install dependencies | ✓ | 26.0.1 | — |
| node/npm | gsd tooling/scripts | ✓ | node v22.22.0 / npm 11.12.0 | — |
| docker | Local containerized integration test | ✗ | — | Chạy test đơn vị Python trực tiếp |
| redis-cli | Probe Redis local | ✗ | — | Dùng app-level integration test/mock Redis |
| psql | Probe Postgres local | ✗ | — | Dùng asyncpg app connection + migration logs |

**Missing dependencies with no fallback:**
- None blocking for code-level implementation.

**Missing dependencies with fallback:**
- docker, redis-cli, psql.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | unittest/pytest-style test discovery (Python) [VERIFIED: test files imports] |
| Config file | none — see Wave 0 |
| Quick run command | `python -m pytest D:/Aureus/services/aureus-signal/tests/test_indicator_snapshot.py -q` [ASSUMED] |
| Full suite command | `python -m pytest D:/Aureus/services/aureus-signal/tests D:/Aureus/services/aureus-signal/unittest -q` [ASSUMED] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PH43-01 | Persist `candle_color_{d1,h1,m30,m15,m5}` per M1 | unit + integration | `python -m pytest .../test_snapshot_mtf_fields.py -q` | ❌ Wave 0 |
| PH43-02 | Persist `bb_{m1,m5,m15,m30,h1}` as `{upper,middle,lower}` | unit + integration | `python -m pytest .../test_snapshot_bb_mtf.py -q` | ❌ Wave 0 |
| PH43-03 | TF> M1 uses last-closed candle | unit | `python -m pytest .../test_mtf_last_closed_rule.py -q` | ❌ Wave 0 |
| PH43-04 | Null-first when insufficient data | unit | `python -m pytest .../test_snapshot_null_policy.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command + targeted new tests
- **Per wave merge:** full suite command
- **Phase gate:** full suite green trước `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `services/aureus-signal/tests/test_snapshot_mtf_fields.py` — covers PH43-01
- [ ] `services/aureus-signal/tests/test_snapshot_bb_mtf.py` — covers PH43-02
- [ ] `services/aureus-signal/tests/test_mtf_last_closed_rule.py` — covers PH43-03
- [ ] `services/aureus-signal/tests/test_snapshot_null_policy.py` — covers PH43-04
- [ ] Xác nhận lệnh pytest khả dụng trong môi trường hiện tại (không thấy config file test runner)

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (phase chỉ mở rộng indicator snapshot nội bộ) |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Validate payload shape + null handling trước insert snapshot [VERIFIED: snapshot_utils.py pattern] |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for Python + Redis Stream + Timescale stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JSON payload shape drift làm lỗi insert | Tampering | Strict schema/mapping test cho snapshot keys; additive-only migration |
| Timestamp parsing ambiguity (ms vs s) | Tampering | Normalize timestamp branch như code hiện hữu trước insert [VERIFIED: aureus-db-writer/main.py] |
| Null/placeholder confusion gây analytics sai | Integrity | Enforce null-first policy (D-10) |

## Sources

### Primary (HIGH confidence)
- `D:/Aureus/.planning/phases/43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the/43-CONTEXT.md` - locked decisions, scope, constraints
- `D:/Aureus/services/aureus-signal/engine/snapshot_utils.py` - snapshot build/insert SQL contracts
- `D:/Aureus/services/aureus-signal/engine/signals/resampler.py` - HTF resample semantics, forming candle note
- `D:/Aureus/services/aureus-db-writer/schema.sql` - current DB schema for `aureus_signal_snapshots`
- `D:/Aureus/services/aureus-signal/engine/live_engine.py` - M1 pipeline + snapshot insertion hook
- `D:/Aureus/services/aureus-signal/engine/state_snapshot.py` - unified snapshot object structure
- `D:/Aureus/CLAUDE.md` - project constraints and mandatory process rules

### Secondary (MEDIUM confidence)
- `D:/Aureus/.planning/phases/40-signal-classification-indicator-event-based/40-CONTEXT.md` - established additive snapshot/payload pattern
- `D:/Aureus/.planning/phases/41-b-sl-pivot-point/41-CONTEXT.md` - recent conventions for constrained phase planning
- `D:/Aureus/.planning/phases/42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry/42-CONTEXT.md` - cross-layer propagation conventions

### Tertiary (LOW confidence)
- Không dùng nguồn web ngoài cho claims kỹ thuật cốt lõi phase này.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - dựa trên dependency files + code imports/runtime probes
- Architecture: HIGH - dựa trực tiếp vào canonical refs và implementation hiện tại
- Pitfalls: MEDIUM - một phần là suy luận kỹ thuật từ flow hiện có

**Research date:** 2026-04-16
**Valid until:** 2026-05-16
