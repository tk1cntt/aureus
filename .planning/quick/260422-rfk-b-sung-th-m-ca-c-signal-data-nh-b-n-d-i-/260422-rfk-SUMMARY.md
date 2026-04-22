# Quick Task 260422-rfk Summary

## Goal
Mở rộng schema `aureus_trade_signal_snapshots` để lưu trực tiếp bộ signal fields mới (atr/ema/session/candle_color/bb/cisd) và loại bỏ các cột cũ không còn dùng (`timeframe`, `signal_schema_version`, `signal_snapshot`, `cisd_direction`, `ema21`, `ema55`).

## Changes

### 1) Migration schema snapshot mới
- Updated: `services/aureus-db-writer/migrations/add_trade_evaluations.sql`
- Bảng `aureus_trade_signal_snapshots` đã:
  - Thêm các cột numeric/enums mới theo yêu cầu:
    - `atr`, `ema_21`, `ema_34`, `ema_55`, `ema_89`, `ema_100`, `ema_200`, `vol_sma_20`
    - `session`
    - `candle_color_d1`, `candle_color_h1`, `candle_color_m30`, `candle_color_m15`, `candle_color_m5`
    - `bb_m1_up/dn`, `bb_m5_up/dn`, `bb_m15_up/dn`, `bb_m30_up/dn`, `bb_h1_up/dn`
    - `cisd_m5`, `cisd_m15`, `cisd_m30`, `cisd_h1`
  - Bỏ các cột cũ không cần thiết theo yêu cầu user.
  - Chuyển uniqueness sang `UNIQUE(trade_journal_id)` để idempotent theo trade.
  - Bổ sung index runtime cho truy vấn theo symbol/session/time.

### 2) Runtime pipeline persist snapshot theo schema mới
- Updated: `services/aureus-trader/journal.py`
- `on_order_opened` insert snapshot theo cột mới.
- Chuẩn hoá enum/polarity tại runtime:
  - `session`: `ASIAN/LONDON/NEWYORK` -> `1/2/3`
  - `candle_color_*`, `cisd_*`: `BULL/BEAR` -> `1/-1`
- Không còn ghi JSON `signal_snapshot` hay các cột legacy đã loại bỏ.

### 3) Recompute/backfill đồng bộ schema mới
- Updated: `services/aureus-trader/recompute_evaluations.py`
- `recompute_batch` insert snapshot theo bộ cột mới, tương thích idempotent theo `trade_journal_id`.

### 4) Test cập nhật theo contract mới
- Updated:
  - `services/aureus-trader/tests/test_signal_snapshot_pipeline.py`
  - `services/aureus-trader/tests/test_signal_snapshot_recompute.py`
  - `services/aureus-trader/tests/test_signal_snapshot_migration.py`
  - `services/aureus-db-writer/tests/test_evaluation_migration.py`
- Bổ sung/điều chỉnh assert:
  - Không còn cột legacy trong DDL snapshot table.
  - Query insert snapshot runtime/recompute dùng cột mới.
  - Mapping enum/polarity vào mã số đúng yêu cầu.
  - Idempotency rerun không tạo bản ghi snapshot trùng.

## Verification
- `pytest services/aureus-trader/tests/test_signal_snapshot_pipeline.py services/aureus-trader/tests/test_signal_snapshot_recompute.py services/aureus-trader/tests/test_signal_snapshot_migration.py services/aureus-db-writer/tests/test_evaluation_migration.py -q`
- Result: **17 passed**

## Outcome
Pipeline lưu signal snapshot đã chuyển hoàn toàn sang mô hình cột chuẩn hoá mới, phù hợp yêu cầu mở rộng dữ liệu và loại bỏ cột legacy.