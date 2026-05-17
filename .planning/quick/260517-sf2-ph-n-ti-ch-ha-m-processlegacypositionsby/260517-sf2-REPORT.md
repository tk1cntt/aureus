# Báo cáo quick 260517-sf2: Phân tích `ProcessLegacyPositionsByType`

## Phạm vi

- Chỉ phân tích/reporting.
- Không sửa `mql5/AureusProvider_v2.mq5`.
- Mục tiêu: giải thích vì sao nhánh `legacy_stale_profitable_single` đóng cả lệnh đang lời tốt, rồi đề xuất điều kiện an toàn cho plan fix sau.

## GitNexus context/query

Lệnh đã chạy:

```bash
npx gitnexus context ProcessLegacyPositionsByType --repo Aureus
npx gitnexus query "legacy_stale_profitable_single ProcessLegacyPositionsByType" --repo Aureus
```

Kết quả:

- `context`: GitNexus trả `Symbol 'ProcessLegacyPositionsByType' not found`.
- `query`: không có `processes` và không có `process_symbols` cho symbol MQL5 này; chỉ trả các definition không liên quan trong Python/stable tree.
- Kết luận: index GitNexus hiện chưa nắm được symbol MQL5 `ProcessLegacyPositionsByType`, nên caller/callee/execution flow phải xác nhận bằng đọc source trực tiếp.

Blast radius phân tích từ source:

| Thành phần | Vai trò | Quan hệ |
|---|---|---|
| `ManagePositionProfitBreakEvent()` | Entry quản lý position đang mở | group theo `symbol + magic + direction`, tính `total_profit`, `total_volume`, `weighted_price_sum`, `earliest_open_time`, rồi gọi `ProcessPositionsByType(...)` |
| `ProcessPositionsByType(...)` | Router profile quản lý lệnh | gọi `ResolveManagementProfile(...)`; nếu không match profile riêng thì rơi vào `ProcessLegacyPositionsByType(...)` |
| `ProcessLegacyPositionsByType(...)` | Legacy/default-old handler | có nhánh `legacy_stale_profitable_single` close market khi single position quá 30 phút và lời ròng dương |
| `ClosePositionTickets(...)` | Thực thi close | log `CLOSE`, rồi gọi `trade.PositionClose(ticket)` cho từng ticket |
| `ProcessBreakoutProtectPositionsByType(...)` | Profile so sánh | cùng điều kiện stale single profitable nhưng dùng `MovePositionsSL(...)` về weighted average, không close market ngay |

Luồng xác nhận:

```text
ManagePositionProfitBreakEvent
  -> ProcessPositionsByType
    -> ProcessLegacyPositionsByType
      -> ClosePositionTickets(reason="legacy_stale_profitable_single")
```

## Root cause close nhầm lệnh lời tốt

Trong `ProcessLegacyPositionsByType(...)`, `net_profit` được tính lại bằng:

```text
net_profit = total_profit - total_commission + total_swap
```

Nguồn dữ liệu:

- `total_profit`: tổng `POSITION_PROFIT` của nhóm position cùng `symbol + magic + direction`.
- `total_commission`: `total_volume * GetPositionCommissionCostPerLot(symbol)`.
- `total_swap`: tổng `POSITION_SWAP` theo ticket.
- `age_seconds`: `TimeCurrent() - earliest_open_time`.
- `positions_count`: `ArraySize(tickets)`.

Nhánh gây lỗi semantic:

```text
positions_count == 1 && age_seconds > 1800 && net_profit > 0
```

Hành động nhánh này:

```text
ClosePositionTickets(..., "legacy_stale_profitable_single", "P-08")
```

Vì sao đóng cả lệnh lời tốt:

- Điều kiện `net_profit > 0` quá rộng: mọi lệnh single quá 30 phút chỉ cần lời ròng dương đều bị close.
- Không có ngưỡng phân biệt lời nhỏ/chớm hòa vốn với lời đủ tốt, ví dụ `InpBEProfitTarget`.
- Không đo độ mạnh profit theo money threshold, pip distance, R multiple, hoặc trend/structure.
- Không lưu MFE/MAE nên snapshot hiện tại không biết lệnh từng âm rồi hồi về hòa hay luôn chạy đúng hướng.
- Không xét current SL/TP như dấu hiệu lệnh đã được bảo vệ hay chưa.
- `ProcessBreakoutProtectPositionsByType(...)` cho thấy alternative an toàn hơn: cùng stale single profitable nhưng chỉ `MovePositionsSL(...)` về `weighted_avg_open_price`, không close market.

Kết luận root cause: legacy handler dùng time-stop với điều kiện profit dương tối thiểu, nên nó biến mọi single position profitable sau 30 phút thành tín hiệu close, kể cả lệnh đang có lợi nhuận tốt và có thể tiếp tục chạy.

## Ma trận nhận dạng 3 trạng thái

Dữ liệu hiện provider có thể dùng ngay:

- `positions_count`
- `age_seconds`
- `net_profit`
- `weighted_avg_open_price = weighted_price_sum / total_volume`
- Giá hiện tại `Bid/Ask` từ symbol
- `SYMBOL_TRADE_TICK_VALUE`, `SYMBOL_POINT`
- Current `POSITION_SL`, `POSITION_TP` nếu `PositionSelectByTicket(...)`
- `InpBEProfitTarget`

Dữ liệu còn thiếu nếu muốn phân loại chuẩn:

- MFE: max favorable excursion theo ticket.
- MAE: max adverse excursion theo ticket.
- `max_drawdown_since_open` hoặc `min_profit_since_open`.
- Lịch sử state profit theo ticket để biết lệnh đã từng âm hay chưa.

| Case | Dấu hiệu hiện có | Hạn chế | Hành động đề xuất |
|---|---|---|---|
| 1. Sideway không có lợi nhuận | `positions_count == 1`, `age_seconds > 1800`, `net_profit` quanh 0 hoặc dương rất nhỏ, distance từ `weighted_avg_open_price` đến Bid/Ask nhỏ, chưa đạt `InpBEProfitTarget` | Snapshot không chứng minh được thị trường sideway, chỉ thấy lời nhỏ sau thời gian dài | Có thể close nhẹ nếu mục tiêu là giải phóng margin, hoặc move SL về cost rồi chờ thêm; cần threshold nhỏ rõ ràng |
| 2. Âm rồi hồi hòa/chớm lời | `age_seconds > 1800`, `0 < net_profit < InpBEProfitTarget` hoặc `< positions_count * InpBEProfitTarget / 2`, profit chưa đủ bảo vệ | Không biết chắc quá khứ âm vì provider chưa lưu MFE/MAE/MAE negative; chỉ dùng proxy near breakeven | Ưu tiên `MOVE_SL` về breakeven/cost; close chỉ khi user muốn thoát lệnh hồi hòa sau thời gian dài |
| 3. Lời tốt cần giữ | `net_profit >= InpBEProfitTarget` hoặc đạt money/R threshold; distance/pips khỏi entry rõ; có thể có SL/TP đã đặt | Chưa có R multiple nếu không biết initial risk; chưa có MFE để biết profit đang mở rộng hay đã retrace | Không close market. HOLD hoặc `MovePositionsSL(...)` về breakeven/weighted avg, sau đó trailing theo structure giống breakout/trend profiles |

## Khuyến nghị solution an toàn

### Phương án 1: tối thiểu, ít rủi ro nhất

Thay semantic nhánh legacy stale single:

```text
if positions_count == 1 && age_seconds > 1800:
  if 0 < net_profit && net_profit < small_profit_threshold:
    ClosePositionTickets(..., "legacy_stale_small_profit_single", ...)
  else if net_profit >= InpBEProfitTarget:
    HOLD hoặc MovePositionsSL(... weighted_avg_open_price ...)
```

Biến thể threshold:

```text
0 < net_profit && net_profit < positions_count * InpBEProfitTarget / 2
```

Ưu điểm:

- Chặn close nhầm lệnh lời tốt.
- Ít thay đổi logic.
- Giữ tinh thần legacy time-stop cho lệnh lời quá nhỏ sau 30 phút.

Nhược điểm:

- Vẫn chưa phân biệt chuẩn case sideway với âm-rồi-hòa vì chưa có MFE/MAE.

### Phương án 2: đưa legacy single stale gần `breakout_protect`

Với `positions_count == 1 && age_seconds > 1800 && net_profit > 0`:

- Nếu lời nhỏ/near breakeven: `MOVE_SL` về `weighted_avg_open_price` hoặc close tùy mục tiêu vận hành.
- Nếu `net_profit >= InpBEProfitTarget`: không close; trailing SL theo structure nếu có target hợp lệ.
- Dùng `MovePositionsSL(...)` giống `ProcessBreakoutProtectPositionsByType(...)` để bảo vệ lệnh thay vì đóng sớm.

Ưu điểm:

- Phù hợp hơn với lệnh đang chạy tốt.
- Có precedent trong source hiện tại: breakout profile đã làm như vậy.

Nhược điểm:

- Thay đổi behavior legacy rộng hơn phương án 1.

### Phương án 3: chuẩn nhất, cần plan lớn hơn

Thêm tracking per-ticket:

- MFE
- MAE
- min/max profit since open
- drawdown/retrace từ peak profit

Sau đó phân loại:

- Âm rồi hồi hòa: MAE âm sâu, current profit gần 0.
- Lời tốt thật: MFE/current profit cao, drawdown còn trong ngưỡng.
- Sideway: MFE/MAE nhỏ, profit quanh 0 lâu.

Ưu điểm:

- Phân biệt đúng 3 trạng thái theo lịch sử.

Nhược điểm:

- Đây là thay đổi lớn hơn: cần state store trong provider hoặc global arrays/maps, cần test runtime kỹ.

## Kết luận

- Không implement trong quick này.
- Fix sau nên bắt đầu từ `ProcessLegacyPositionsByType`.
- Trước khi edit phải chạy GitNexus impact theo CLAUDE.md: `gitnexus_impact({target: "ProcessLegacyPositionsByType", direction: "upstream"})` hoặc CLI tương đương nếu MCP không có.
- Điều kiện an toàn tối thiểu cần user duyệt: không close market nếu `net_profit >= InpBEProfitTarget`; với lệnh stale single lời tốt thì HOLD hoặc `MovePositionsSL` về breakeven/weighted avg/trailing.

## Kiểm tra threat model

- `T-260517-sf2-01`: Đã giữ đúng phạm vi chỉ phân tích, không sửa source.
- `T-260517-sf2-02`: Không thay đổi runtime close attempts.
- `T-260517-sf2-03`: Report trích đúng reason `legacy_stale_profitable_single` để fix sau giữ log/reason rõ.
