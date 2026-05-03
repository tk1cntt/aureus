# Báo cáo quick 260503-o5w: Kiểm tra log ManagePositionDecision breakout HOLD

## Kết luận ngắn

Log `ManagePositionDecision symbol=BTCUSD/ETHUSD profile=breakout_protect action=HOLD reason=breakout_profit_below_protection_threshold` không phải lỗi. Đây là quyết định `HOLD` bình thường của profile `breakout_protect` khi nhóm lệnh chưa đạt ngưỡng profit để bắt đầu bảo vệ SL.

Nguyên nhân log lặp: `OnTimer()` gọi `ManagePositionProfitBreakEvent()` liên tục; hàm này gom position theo `symbol + magic + direction`, rồi nhánh `ProcessBreakoutProtectPositionsByType()` log lại mỗi vòng nếu `net_profit` thấp hơn hoặc bằng `positions_count * InpBEProfitTarget / 2` vẫn đúng.

## Log này nghĩa là gì

- `profile=breakout_protect`: nhóm position dùng management profile `breakout_protect`.
- `action=HOLD`: provider chưa close, chưa move SL, chưa trail SL.
- `reason=breakout_profit_below_protection_threshold`: `net_profit` của group chưa vượt ngưỡng bảo vệ.
- Công thức threshold trong source: `positions_count * InpBEProfitTarget / 2`.
- `InpBEProfitTarget` default là `20.0`, nên threshold default là `positions_count * 10.0` USD.

## Vì sao lặp liên tục

Call path từ source:

1. `OnTimer()` chạy vòng timer provider.
2. `OnTimer()` gọi `ManagePositionProfitBreakEvent()`.
3. `ManagePositionProfitBreakEvent()` duyệt open positions, bỏ position không có magic hoặc symbol không nằm trong context provider.
4. Hàm gom từng group theo `symbol + magic + direction`.
5. `ProcessPositionsByType()` resolve management profile theo magic.
6. Với `PROFILE_BREAKOUT_PROTECT`, gọi `ProcessBreakoutProtectPositionsByType()`.
7. Nếu `net_profit` thấp hơn hoặc bằng `positions_count * InpBEProfitTarget / 2`, gọi `LogManagementDecision(..., "HOLD", "breakout_profit_below_protection_threshold", ...)` rồi return.

Vì condition profit vẫn đúng qua nhiều timer ticks, log cũ bị in lại liên tục trước khi fix.

## Source evidence

- `D:/Aureus/mql5/AureusProvider_v2.mq5:30`: `InpBEProfitTarget = 20.0`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:170`: `ShouldSuppressRepeatedHoldDecisionLog(...)` dùng key `symbol + magic + direction + reason` cho repeated HOLD suppression.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:195`: `LogManagementDecision(...)` giữ format `[ManagePositionDecision] symbol=... action=... reason=...`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:1881`: `ProcessBreakoutProtectPositionsByType(...)` xử lý profile `breakout_protect`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:1906`: điều kiện profit thấp hơn hoặc bằng `positions_count * InpBEProfitTarget / 2`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:1908`: log `HOLD` với reason `breakout_profit_below_protection_threshold`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:1996`: `ManagePositionProfitBreakEvent()` gom open positions.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:2059`: mỗi group được chuyển vào `ProcessPositionsByType(...)`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:3460`: `OnTimer()`.
- `D:/Aureus/mql5/AureusProvider_v2.mq5:3497`: timer gọi `ManagePositionProfitBreakEvent()`.
- `D:/Aureus/.planning/quick/260503-neg-fix-spam-managepositiondecision-hold-pro/260503-neg-SUMMARY.md`: quick trước thêm suppression theo key `symbol+magic+direction+reason` và bảo toàn CLOSE/error/non-HOLD logs.

## BTCUSD/ETHUSD vì sao xuất hiện

Source cho thấy `ManagePositionProfitBreakEvent()` chỉ xử lý position có:

- `magic != 0`
- `FindContextIndex(symbol) >= 0`
- group theo đúng `symbol + magic + direction`

Vì vậy BTCUSD/ETHUSD xuất hiện khi account đang có open position groups cho các symbol này trong context provider, với magic mapping resolve ra `breakout_protect`. Source không có runtime account snapshot trong quick này, nên không xác minh được ticket cụ thể, lot, profit từng position, hoặc mapping runtime đang loaded trong terminal.

## Fix recommendation

Áp dụng fix bắt buộc ở source: thêm `breakout_profit_below_protection_threshold` vào allowlist repeated HOLD suppression trong `ShouldSuppressRepeatedHoldDecisionLog(...)` và điều kiện gọi helper ở `LogManagementDecision(...)`.

Phạm vi giữ nguyên:

- Không đổi threshold profit.
- Không đổi logic close, move SL, trail SL.
- Không suppress `CLOSE`.
- Không suppress error log, close failure, market guard, `ORDER_FAILED`, unknown profile.
- Không suppress non-HOLD như `TRAIL_SL`, `MOVE_SL`.
- Không commit `mql5/AureusProvider_v2.ex5` hoặc `stable/`.

## Validation plan

1. Source assertion kiểm tra anchors: `InpBEProfitTarget`, `ShouldSuppressRepeatedHoldDecisionLog`, `LogManagementDecision`, `ProcessBreakoutProtectPositionsByType`, `breakout_profit_below_protection_threshold`, `ManagePositionProfitBreakEvent`.
2. Source assertion kiểm tra reason mới nằm trong body `ShouldSuppressRepeatedHoldDecisionLog(...)`.
3. Source assertion kiểm tra helper vẫn có gate `action != "HOLD"`.
4. Source assertion kiểm tra reasons cũ `profile_fallback` và `legacy_no_rule_matched` vẫn còn.
5. `git diff --check` cho `mql5/AureusProvider_v2.mq5` và report.
6. Nếu MetaEditor có trong PATH thì compile; nếu không có thì ghi limitation.
7. Chạy GitNexus impact/detect nếu CLI hỗ trợ; nếu MQL5 symbol không indexed hoặc command không có thì ghi limitation.

## Limitations

- GitNexus impact trước edit: `npx gitnexus impact --repo Aureus --direction upstream ShouldSuppressRepeatedHoldDecisionLog` trả `{ "error": "Target 'ShouldSuppressRepeatedHoldDecisionLog' not found" }`, nên MQL5 helper không được index theo symbol này trong GitNexus CLI hiện tại.
- Chưa có runtime MT5 account snapshot, nên chỉ kết luận BTCUSD/ETHUSD dựa trên source path và điều kiện lọc group, không xác minh ticket/live position cụ thể.
- MetaEditor compile phụ thuộc PATH local.
- MetaEditor availability check: `MetaEditor64.exe`, `metaeditor64.exe`, `MetaEditor.exe`, `metaeditor.exe` không có trong PATH, nên chưa compile MQL5 trong môi trường này.
- GitNexus detect changes trước commit: CLI sẽ được thử trước commit; nếu command không tồn tại, limitation này được ghi lại trong summary.
