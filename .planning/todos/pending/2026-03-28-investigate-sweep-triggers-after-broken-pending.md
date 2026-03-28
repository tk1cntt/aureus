---
created: 2026-03-28T00:36:30.000Z
title: Investigate missing OB events in signal_history_normalized
area: general
files:
  - services/aureus-signal/engine/signals/sweep.py
  - services/aureus-signal/engine/signals/structure.py
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/engine/backtest_engine.py
  - services/aureus-signal/engine/state.py
---

## Problem

Hiện tại runtime chỉ quan sát thấy event `BROKEN_PENDING` được trigger, còn các event sweep/state tiếp theo không xuất hiện như mong đợi. Điều này làm luồng state machine của sweep bị dừng sớm và gây thiếu tín hiệu downstream.

Đã phát sinh thêm case: khi `choch down` và giá thực tế có sweep qua một OB, hệ thống vẫn không emit sweep event. Giả thuyết hiện tại là tại thời điểm evaluate event, trạng thái OB chưa được update kịp nên điều kiện sweep không đạt và event bị bỏ lỡ (lack event).

Case mới cần điều tra thêm: event OB `MITIGATED` xảy ra nhưng không thấy xuất hiện trong `signal_history_normalized`. Cần xác minh liệu dữ liệu event không được tạo từ source, hay có tạo nhưng bị mất ở bước normalize/map sang output contract.

Ngoài ra logic hiện tại còn có `Regime Check` (lọc theo trend/regime) trong `SweepSignal`, trong khi sweep có thể xảy ra ở mọi bối cảnh trend. Điều kiện này có thể đang chặn trigger hợp lệ.

## Solution

- Điều tra đầy đủ state transition trong `SweepSignal` từ `BROKEN_PENDING` sang các trạng thái kế tiếp để xác định điểm chặn trigger.
- Trace thứ tự xử lý giữa cập nhật trạng thái OB (`_update_ob_states`) và khối phát event (`calculate`) trong cùng candle/tick, đặc biệt ở case `choch down` + sweep qua OB.
- Rà cơ chế dedup/guard theo tick-candle (`already_swept`, `status_tag`) để xác nhận có vô tình nuốt event hay không.
- Kiểm tra pipeline ghi/chuẩn hóa `signal_history`: từ nơi phát event OB (`structure.py`/`sweep.py`) đến nơi build `signal_history_normalized` để xác định mất dữ liệu ở source hay ở mapping.
- Bổ sung/cập nhật test cho case `MITIGATED` và `choch down` sweep qua OB để đảm bảo event xuất hiện đúng trong `signal_history_normalized`.
- Loại bỏ điều kiện `Regime Check` khỏi điều kiện phát sinh sweep event.
