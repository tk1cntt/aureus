---
created: 2026-03-28T00:34:52.744Z
title: Remove market_regime use htf_trend
area: general
files:
  - services/aureus-signal/engine/signals/trend.py:55
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/engine/signals/sweep.py
---

## Problem

`htf_trend` và `market_regime` đang biểu diễn cùng nhóm trạng thái xu hướng/regime nhưng tồn tại dưới 2 tên khác nhau, gây dư thừa và dễ nhầm lẫn khi đọc logic signal/filter.

Mục tiêu: chuẩn hóa về một nguồn duy nhất là `htf_trend`, loại bỏ hoàn toàn `market_regime` khỏi luồng runtime/state để tránh drift schema và giảm lỗi mapping.

## Solution

- Dùng `htf_trend` làm field canonical cho toàn pipeline.
- Rà tất cả chỗ đọc/ghi `market_regime` (signal layer, filters, snapshots, schema normalize, tests) và migrate sang `htf_trend`.
- Thêm migration guard/backward compatibility ngắn hạn nếu cần restore state cũ.
- Cập nhật test contract + integration để đảm bảo không còn phụ thuộc `market_regime`.
