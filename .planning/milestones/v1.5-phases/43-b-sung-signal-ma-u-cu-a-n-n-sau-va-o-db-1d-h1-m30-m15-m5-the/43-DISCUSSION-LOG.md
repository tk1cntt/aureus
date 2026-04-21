# Phase 43: b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves alternatives considered.

**Date:** 2026-04-16
**Phase:** 43-b-sung-signal-ma-u-cu-a-n-n-sau-va-o-db-1d-h1-m30-m15-m5-the
**Areas discussed:** Màu nến đa khung thời gian, BB đa khung thời gian, Đồng bộ theo M1, Quy ước lưu DB

---

## Màu nến đa khung thời gian

| Option | Description | Selected |
|--------|-------------|----------|
| BULL/BEAR/DOJI theo close-open (Recommended) | Quy tắc đơn giản, ổn định, dễ test và đồng nhất giữa TF | ✓ |
| Chỉ BULL/BEAR (không DOJI) | Giảm state nhưng mất thông tin trạng thái trung tính | |
| Dựa theo body/threshold phức tạp | Giàu thông tin hơn nhưng tăng complexity và khó nhất quán | |

**User's choice:** Chốt theo hướng recommended cho toàn bộ area.
**Notes:** Người dùng yêu cầu chốt cả 4 area và muốn suggest tốt nhất.

---

## Bollinger Bands đa khung thời gian

| Option | Description | Selected |
|--------|-------------|----------|
| Lưu đủ upper/middle/lower cho mỗi TF (Recommended) | Dữ liệu đầy đủ cho hiển thị + phân tích downstream | ✓ |
| Chỉ lưu status vị trí giá so với BB | Nhẹ dữ liệu hơn nhưng mất khả năng tái tính toán/visual chi tiết | |
| Lưu thêm width/z-score ngay trong phase này | Mạnh cho analytics nhưng vượt scope yêu cầu hiện tại | |

**User's choice:** Chốt theo hướng recommended cho toàn bộ area.
**Notes:** TF yêu cầu BB: M1, M5, M15, M30, H1.

---

## Đồng bộ theo từng nến M1

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot mỗi M1, TF lớn dùng last closed (Recommended) | Ổn định, replay-friendly, không rung dữ liệu forming candle | ✓ |
| Chỉ ghi khi TF lớn đóng nến | Nhẹ hơn nhưng không còn granular theo M1 | |
| Dùng cả nến đang hình thành TF lớn | Cập nhật nhanh nhưng nhiễu và khó đối chiếu | |

**User's choice:** Chốt theo hướng recommended cho toàn bộ area.
**Notes:** Duy trì chuỗi dữ liệu M1 liên tục cho analytics.

---

## Quy ước lưu DB (naming/null/fallback)

| Option | Description | Selected |
|--------|-------------|----------|
| Additive fields + null khi thiếu dữ liệu (Recommended) | Không phá contract cũ, phân biệt rõ missing data | ✓ |
| Fallback giá trị giả (0 / UNKNOWN) | Dễ hiển thị nhưng gây nhiễu semantic dữ liệu | |
| Backfill nội suy ngay trong phase này | Dữ liệu dày hơn nhưng tăng scope/complexity | |

**User's choice:** Chốt theo hướng recommended cho toàn bộ area.
**Notes:** Không fold todo ngoài scope; chỉ làm đúng yêu cầu phase.

---

## Claude's Discretion

- Chi tiết tổ chức code khi mở rộng indicator snapshot helper
- Cách migration DB cụ thể miễn giữ contract additive
- Mức độ logging cho nhánh thiếu dữ liệu TF lớn

## Deferred Ideas

- Investigate missing OB events in signal_history_normalized
- Remove market_regime use htf_trend
