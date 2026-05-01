---
phase: 260501-eka-implement-history-based-cooldown-in-aure
plan: 01
status: completed
completed_date: "2026-05-01"
code_commit: e2c49ee
key_files:
  modified:
    - mql5/AureusProvider_v2.mq5
verification:
  - static PLAN checks passed
  - git diff --check passed
  - MetaEditor compiler unavailable in PATH
  - GitNexus CLI impact/detect_changes unavailable via documented commands
---

# Quick 260501-eka: Implement history-based cooldown in AureusProvider_v2 Summary

Đã thêm cooldown dựa trên MT5 deal history cho `AureusProvider_v2`, scoped đúng theo `symbol + magic + direction`, để chặn mở lại lệnh quá sớm sau SL hoặc burst close cùng scope.

## Kết quả chính

- Thêm `HistoryCooldownState` và helper provider-local trong `mql5/AureusProvider_v2.mq5`.
- Bootstrap cooldown từ history trong `OnInit` sau khi parse `InpSymbols`.
- Cập nhật realtime từ `OnTradeTransaction` bằng close deal `DEAL_ENTRY_OUT`, không phụ thuộc socket connection cho cooldown state.
- Enforce trong `ExecuteOpenOrder` sau unsupported-symbol ignore và trước duplicate active order/ACK/order side effects.
- Supported scope đang cooldown bị `SendNACK(cmdId, "HISTORY_COOLDOWN_ACTIVE")`.
- Unsupported symbol vẫn chỉ log và return local, không terminal NACK.
- Không chặn `CLOSE_ORDER`, `REQUEST_*`, `REQUEST_BACKFILL`, `REQUEST_BACKFILL_COUNT`.

## Quy tắc cooldown

- Single close reason `DEAL_REASON_SL`: cooldown 30 phút cho đúng `symbol + magic + direction`.
- Multiple close cùng scope trong vòng 2 giây: cooldown 60 phút từ latest close time.
- Không implement slow TP cooldown.
- Direction lấy theo original position direction: close deal `DEAL_TYPE_BUY` nghĩa là original `SELL`, close deal `DEAL_TYPE_SELL` nghĩa là original `BUY`.

## Verification

- Static checks từ plan đã pass:
  - Có `HISTORY_COOLDOWN_ACTIVE`, `BootstrapHistoryCooldowns`, `ApplyCloseDealToHistoryCooldown`, `SetHistoryCooldown`, `DEAL_REASON_SL`, `30 * 60`, `60 * 60`.
  - Cooldown check nằm sau branch `SYMBOL_NOT_ALLOWED` và trước `SendACK(cmdId)`.
  - `ExecuteCloseOrder` không chứa `HISTORY_COOLDOWN_ACTIVE`.
  - `OnTradeTransaction` gọi `ApplyCloseDealToHistoryCooldown`.
  - Helper cooldown không dùng `_Symbol` làm scope.
- `git diff --check -- mql5/AureusProvider_v2.mq5` pass.
- Không tìm thấy `metaeditor64.exe`/`MetaEditor64.exe` trong PATH nên chưa compile MQL5 được trong môi trường này.

## GitNexus

- Đã thử chạy impact trước khi sửa các symbol `OnInit`, `ExecuteOpenOrder`, `OnTradeTransaction` bằng CLI `npx gitnexus impact --target ... --direction upstream` nhưng CLI báo `unknown option '--target'`.
- Đã thử `npx gitnexus detect_changes` và `npx gitnexus detect-changes` trước commit nhưng CLI báo unknown command.
- Fallback đã dùng direct file evidence + static plan checks + `git diff --check`; diff chỉ nằm trong `mql5/AureusProvider_v2.mq5` cho vùng helper cooldown, `OnInit`, `ExecuteOpenOrder`, `OnTradeTransaction`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Realtime cooldown không phụ thuộc socket connection**
- **Found during:** Task 2
- **Issue:** `OnTradeTransaction` ban đầu return sớm nếu socket chưa connected, có thể bỏ lỡ update cooldown realtime.
- **Fix:** Chọn history deal trước, apply cooldown state trước gate socket push event; ORDER_CLOSED push vẫn giữ nguyên yêu cầu socket connected.
- **Files modified:** `mql5/AureusProvider_v2.mq5`
- **Commit:** e2c49ee

## Known Stubs

None.

## Threat Flags

None beyond planned trust boundaries.

## Commits

- `e2c49ee` - `feat(260501-eka): add provider history cooldown`
