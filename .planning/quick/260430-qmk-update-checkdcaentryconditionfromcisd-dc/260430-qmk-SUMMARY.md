---
phase: 260430-qmk-update-checkdcaentryconditionfromcisd-dc
plan: 01
subsystem: mql5-trading
tags: [mql5, mt5, dca, cisd, magic, symbol-scope]
requires:
  - quick: 260430-oa4
    provides: Provider-safe DoDCA baseline in AureusProvider_v2
  - quick: 260430-ouw
    provides: CISD-gated DCA trigger in AureusProvider_v2
  - quick: 260430-q4z
    provides: Duplicate strategy order guard by symbol + magic
provides:
  - Strategy+symbol scoped DoDCA calculations, open order, and TP modifications
  - CISD DCA trigger that derives active strategy magic before calling DoDCA
  - Compile evidence for AureusProvider_v2 with 0 errors and 0 warnings
affects: [AureusProvider_v2, MT5 DCA execution, CISD DCA gate]
tech-stack:
  added: []
  patterns:
    - Explicit symbol + magic scope for DCA position grouping
    - Trade magic set before CTrade DCA order open
key-files:
  created:
    - .planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md
  modified:
    - mql5/AureusProvider_v2.mq5
key-decisions:
  - "Giữ CheckDCAEntryConditionFromCISD chart-symbol-local như hiện trạng nhưng derive magic từ active position cùng symbol + direction trước khi gọi DoDCA."
  - "Không refactor ExecuteOpenOrder; chỉ đổi post-market-fill DoDCA call sang truyền symbol + magic và giữ duplicate guard trước ACK."
patterns-established:
  - "DoDCA nhận explicit order_type_signal, symbol, magic và mọi vòng đọc/sửa position phải lọc cùng symbol + magic."
requirements-completed: [QUICK-260430-QMK]
duration: 42min
completed: 2026-04-30
---

# Quick 260430-qmk: Update CheckDCAEntryConditionFromCISD DCA Scope Summary

**DCA trong AureusProvider_v2 hiện được gom nhóm theo đúng `symbol + magic`, tránh trộn position giữa strategy/symbol khi CISD hoặc post-fill kích hoạt DCA.**

## Performance

- **Duration:** 42 phút
- **Started:** 2026-04-30T00:00:00Z
- **Completed:** 2026-04-30
- **Tasks:** 3/3
- **Files modified:** 1 code file, 1 summary file

## Accomplishments

- `DoDCA` đổi từ chart-symbol implicit sang explicit scope `DoDCA(int order_type_signal, string symbol, long magic)`.
- Các vòng collect position và modify TP trong DCA đều lọc `POSITION_SYMBOL == symbol` và `POSITION_MAGIC == magic`.
- Các phép đọc giá, tick value, point, volume limit, normalize digits, open DCA order dùng scoped `symbol`; trước khi open gọi `trade.SetExpertMagicNumber(magic)`.
- `CheckDCAEntryConditionFromCISD` không còn gọi `DoDCA` chart-only; trước khi fire BUY/SELL DCA sẽ tìm active position cùng `_Symbol` + direction để lấy magic, chỉ gọi khi có strategy group hợp lệ.
- Post-market-fill trong `ExecuteOpenOrder` gọi `DoDCA(..., symbol, magic)` cho symbol/magic vừa khớp, không còn giới hạn `symbol == _Symbol`.
- Duplicate guard `STRATEGY_ORDER_EXISTS` trong `ExecuteOpenOrder` được giữ nguyên về hành vi: active position hoặc pending order cùng `symbol + magic` bị NACK trước ACK/order side effects.

## Task Commits

1. **Task 1: Perform GitNexus impact attempts and confirm surgical edit scope** - nằm trong `3b12a40` (fix)
2. **Task 2: Scope DoDCA and CISD trigger by strategy magic and symbol** - `3b12a40` (fix)
3. **Task 3: Verify compile log, duplicate guard, and changed-symbol scope** - code trong `3b12a40`; summary do orchestrator docs step xử lý theo constraint

## Files Created/Modified

- `D:/Aureus/mql5/AureusProvider_v2.mq5` - cập nhật DCA strategy/symbol scoping và caller tương ứng.
- `D:/Aureus/.planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md` - ghi execution summary, impact fallback, compile result.

## GitNexus Impact Attempts

GitNexus MCP tools không có trong toolset hiện tại, nên đã dùng CLI theo `D:/Aureus/CLAUDE.md`:

- `npx gitnexus impact DoDCA --direction upstream` -> lỗi CLI option: `unknown option '--target'`.
- `npx gitnexus impact DoDCA -d upstream` -> lỗi nhiều repo indexed, yêu cầu `repo`.
- `npx gitnexus impact DoDCA -d upstream -r Aureus` -> `Target 'DoDCA' not found`.
- `npx gitnexus impact CheckDCAEntryConditionFromCISD -d upstream -r Aureus` -> `Target 'CheckDCAEntryConditionFromCISD' not found`.

Fallback evidence thủ công:

- Direct caller của `DoDCA` trước/sau sửa:
  - `CheckDCAEntryConditionFromCISD` gọi khi CISD LTF confirmation fire BUY/SELL.
  - `ExecuteOpenOrder` gọi sau market order fill path.
- Direct runtime caller của `CheckDCAEntryConditionFromCISD`: `OnTimer`.
- Scope sửa chỉ nằm trong `mql5/AureusProvider_v2.mq5`; không sửa JSON parsing, socket, candle/backfill, journal event, hoặc duplicate guard logic.

## Verification

- Compile command thực tế đã chạy thành công qua Git Bash path:
  - `"/e/Openclaw/MetaTrader5/MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log"`
- Compile log `D:/Aureus/mql5/AureusProvider_v2_compile.log` ghi:
  - `Result: 0 errors, 0 warnings, 1662 msec elapsed, cpu='X64 Regular'`
- `git -C D:/Aureus diff --check -- mql5/AureusProvider_v2.mq5` pass.
- `git -C D:/Aureus diff -- mql5/AureusProvider_v2.mq5 | git -C D:/Aureus apply --check --cached` pass trước commit.
- `gitnexus detect_changes` không có command CLI tương ứng trong `npx gitnexus --help`; fallback bằng diff scope và manual symbol review.
- `npx gitnexus analyze D:/Aureus` sau commit bị chặn bởi `EPERM: operation not permitted, open 'D:\Aureus\AGENTS.md'`; đây là index refresh issue, không ảnh hưởng compile/code change.

## Duplicate Guard Preservation

Đã kiểm tra `ExecuteOpenOrder` vẫn có hai guard trước `SendACK(cmdId)`:

- Vòng `PositionsTotal()` reject khi `PositionGetString(POSITION_SYMBOL) == symbol && PositionGetInteger(POSITION_MAGIC) == magic`, trả `SendNACK(cmdId, "STRATEGY_ORDER_EXISTS")`.
- Vòng `OrdersTotal()` reject khi `OrderGetString(ORDER_SYMBOL) == symbol && OrderGetInteger(ORDER_MAGIC) == magic`, trả `SendNACK(cmdId, "STRATEGY_ORDER_EXISTS")`.

Không đổi thứ tự guard/ACK: duplicate vẫn bị chặn trước ACK và trước order side effects.

## Decisions Made

- Không tạo persistence/state mới cho strategy magic; `CheckDCAEntryConditionFromCISD` derive magic từ active position đúng `_Symbol + direction`, đúng yêu cầu surgical.
- `DoDCA` được phép chạy cho post-fill symbol khác chart symbol vì toàn bộ symbol-dependent API trong DCA đã dùng explicit `symbol`.
- Không commit compile log hoặc `.ex5` artifact; chỉ commit code theo constraint task atomically, docs artifacts để orchestrator xử lý.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Sửa cách gọi MetaEditor từ bash/Git Bash**
- **Found during:** Task 2 verification
- **Issue:** Command `cmd /c ""E:\Openclaw\...` bị shell quote làm hỏng thành `'ompile:D:Aureus...' is not recognized`.
- **Fix:** Tham khảo `D:/Aureus/RUN_SERVICES.md` theo CLAUDE.md khi command lỗi, sau đó dùng path Git Bash trực tiếp `"/e/Openclaw/MetaTrader5/MetaEditor64.exe" ...`.
- **Files modified:** Không có code change ngoài task.
- **Verification:** Compile log báo 0 errors, 0 warnings.
- **Committed in:** N/A, command/process fix.

**Total deviations:** 1 auto-fixed (blocking command quoting)
**Impact on plan:** Không đổi scope triển khai; chỉ giúp hoàn tất verification bắt buộc.

## Issues Encountered

- GitNexus không resolve được MQL5 symbols `DoDCA` và `CheckDCAEntryConditionFromCISD`; đã ghi fallback evidence ở trên.
- `npx gitnexus analyze D:/Aureus` sau commit lỗi quyền ghi `D:/Aureus/AGENTS.md`; cần xử lý permission/index refresh ngoài quick task nếu muốn cập nhật index ngay.
- MetaEditor trả exit code 1 dù compile log báo `0 errors, 0 warnings`; trạng thái pass dựa trên log chính thức theo yêu cầu plan.

## Known Stubs

Không phát hiện stub mới trong phần code đã sửa.

## Threat Flags

Không có surface bảo mật mới ngoài trust boundary đã nêu trong plan. Thay đổi giảm rủi ro tampering/elevation bằng cách filter DCA theo `symbol + magic`.

## Self-Check: PASSED

- `D:/Aureus/mql5/AureusProvider_v2.mq5` tồn tại và đã được commit trong `3b12a40`.
- `D:/Aureus/.planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md` tồn tại.
- Commit `3b12a40` tồn tại trong repo `D:/Aureus`.
- Compile log xác nhận 0 errors, 0 warnings.

---
*Quick: 260430-qmk-update-checkdcaentryconditionfromcisd-dc*
*Completed: 2026-04-30*
