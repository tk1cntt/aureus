---
phase: 260430-qmk-update-checkdcaentryconditionfromcisd-dc
verified: 2026-04-30T12:21:51Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Chạy trên MetaTrader với nhiều position cùng chart symbol nhưng khác magic, sau đó tạo CISD confirmation BUY/SELL"
    expected: "CheckDCAEntryConditionFromCISD chỉ gọi DoDCA cho group có position khớp _Symbol + direction và magic được derive từ active position; không mở/modify DCA cho strategy magic khác"
    why_human: "CISD gate phụ thuộc state nến H1/LTF và live MT5 positions; không thể xác nhận hoàn toàn bằng grep/compile tĩnh"
  - test: "Chạy DoDCA/post-market-fill trên symbol khác chart symbol trong terminal MT5"
    expected: "DCA order mới dùng symbol/magic của command, SetExpertMagicNumber(magic), và TP modify chỉ áp dụng các ticket cùng symbol + magic"
    why_human: "Cần broker/terminal state thật để xác nhận OrderSend/PositionModify runtime"
---

# Quick 260430-qmk: Update CheckDCAEntryConditionFromCISD DCA Scope Verification Report

**Task Goal:** Update `CheckDCAEntryConditionFromCISD` DCA entry by strategy and symbol in `mql5/AureusProvider_v2.mq5`; update `DoDCA` to calculate values by matching strategy and symbol.
**Verified:** 2026-04-30T12:21:51Z
**Status:** human_needed
**Re-verification:** Không — verification lần đầu, không có VERIFICATION.md trước đó trong `D:/Aureus/.planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc`.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CISD DCA gate evaluates DCA entry using the matching strategy magic and symbol, not only the chart symbol. | VERIFIED | `CheckDCAEntryConditionFromCISD` gọi `FindDCAMagicForSymbolDirection(_Symbol, POSITION_TYPE_BUY/SELL)` trước khi gọi `DoDCA(1/-1, _Symbol, magic)` tại `D:/Aureus/mql5/AureusProvider_v2.mq5:1581-1600`; helper lọc `POSITION_SYMBOL == symbol` và direction tại `1513-1527`. |
| 2 | DoDCA calculates profit, swap, volume, TP, and position updates only from positions matching the requested strategy magic and symbol. | VERIFIED | `DoDCA(int order_type_signal, string symbol, long magic)` tại `1195`; vòng collect positions lọc `POSITION_SYMBOL == symbol`, `POSITION_MAGIC == magic`, và type tại `1222-1224`; profit/swap/volume/weighted price chỉ cộng trong block đã lọc tại `1230-1235`; TP modify cũng lọc cùng symbol+magic+type tại `1433-1435`. Các SymbolInfo/iBar/iLow/iHigh/open order dùng scoped `symbol`; `trade.SetExpertMagicNumber(magic)` trước Buy/Sell tại `1418-1423`. |
| 3 | Existing ExecuteOpenOrder duplicate guard continues rejecting active position/order with the same symbol and magic before ACK/order side effects. | VERIFIED | Guard PositionsTotal tại `1676-1692` và OrdersTotal tại `1695-1710` trả `SendNACK(cmdId, "STRATEGY_ORDER_EXISTS")`; `SendACK(cmdId)` chỉ xảy ra sau đó tại `1722`. |
| 4 | `mql5/AureusProvider_v2.mq5` compiles in MetaEditor with 0 errors and 0 warnings. | VERIFIED | `D:/Aureus/mql5/AureusProvider_v2_compile.log:46` ghi `Result: 0 errors, 0 warnings, 1662 msec elapsed, cpu='X64 Regular'`. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | Strategy+symbol scoped `CheckDCAEntryConditionFromCISD` and `DoDCA` logic, contains `void DoDCA` | VERIFIED | File tồn tại; `DoDCA(int order_type_signal, string symbol, long magic)` substantive; callers updated tại `1586`, `1600`, `2050`. |
| `D:/Aureus/.planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-SUMMARY.md` | Execution summary with GitNexus impact attempts, compile result, and duplicate guard preservation note | VERIFIED | File tồn tại; summary ghi impact fallback tại dòng 69-84, compile result tại 86-95, duplicate guard preservation tại 97-104. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `AureusProvider_v2.mq5::CheckDCAEntryConditionFromCISD` | `AureusProvider_v2.mq5::DoDCA` | Call passes symbol and strategy magic used by matching DCA positions | WIRED | `DoDCA(1, _Symbol, magic)` và `DoDCA(-1, _Symbol, magic)` sau khi magic được derive từ active position cùng symbol+direction. |
| `AureusProvider_v2.mq5::DoDCA` | MT5 position/order state | `PositionGetString(POSITION_SYMBOL)` and `PositionGetInteger(POSITION_MAGIC)` filters | WIRED | Vòng collect và modify TP đều lọc symbol+magic; open DCA set expert magic trước Buy/Sell. |
| `AureusProvider_v2.mq5::ExecuteOpenOrder` | Duplicate active strategy guard | Same symbol + magic checks over `PositionsTotal` and `OrdersTotal` before `SendACK` | WIRED | `STRATEGY_ORDER_EXISTS` xuất hiện ở cả position guard và order guard trước `SendACK(cmdId)`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5::DoDCA` | `symbol`, `magic`, `target_positions`, `total_profit`, `total_swap`, `total_volume`, `new_tp_price` | `ExecuteOpenOrder` command fields and live MT5 `PositionsTotal`/`PositionGet*`; CISD path derives magic from live positions | Yes | FLOWING |
| `D:/Aureus/mql5/AureusProvider_v2.mq5::CheckDCAEntryConditionFromCISD` | `magic`, `g_h1_signalType`, setup state | Live MT5 candles via `iClose/iOpen/iTime` and positions via `FindDCAMagicForSymbolDirection` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| MetaEditor compile produced clean result | Read `D:/Aureus/mql5/AureusProvider_v2_compile.log` | `Result: 0 errors, 0 warnings` found | PASS |
| DCA callers all pass explicit symbol+magic | Static grep for `DoDCA\(` in `D:/Aureus/mql5/AureusProvider_v2.mq5` | Only definition plus calls at `1586`, `1600`, `2050`, all with 3 args | PASS |
| Duplicate guard remains before ACK | Static line inspection of `STRATEGY_ORDER_EXISTS` and `SendACK(cmdId)` | Guards at `1676-1710`; ACK at `1722` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| QUICK-260430-QMK | `D:/Aureus/.planning/quick/260430-qmk-update-checkdcaentryconditionfromcisd-dc/260430-qmk-PLAN.md` | Scope CISD-triggered DCA and DoDCA calculations/modifications by strategy magic + symbol while preserving duplicate guard and clean compile | SATISFIED | All 4 must-have truths verified by code and compile log evidence above. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `D:/Aureus/mql5/AureusProvider_v2.mq5` | 781 | Grep matched `return StringToDouble(...)` due broad `return ...` pattern, not a stub | Info | False positive; parser function returns parsed value, no impact on goal. |

### Human Verification Required

#### 1. CISD DCA group isolation in live MT5

**Test:** Chạy provider trên MetaTrader với nhiều position cùng chart symbol nhưng khác magic, sau đó tạo CISD confirmation BUY/SELL.
**Expected:** `CheckDCAEntryConditionFromCISD` chỉ gọi `DoDCA` cho group có position khớp `_Symbol + direction` và magic được derive từ active position; không mở/modify DCA cho strategy magic khác.
**Why human:** CISD gate phụ thuộc state nến H1/LTF và live MT5 positions; không thể xác nhận hoàn toàn bằng grep/compile tĩnh.

#### 2. Post-market-fill DCA on non-chart symbol

**Test:** Chạy `ExecuteOpenOrder` MARKET path trên symbol khác chart symbol với magic cụ thể trong terminal MT5.
**Expected:** Post-fill gọi `DoDCA(..., symbol, magic)`; DCA order mới dùng symbol/magic của command, `SetExpertMagicNumber(magic)`, và TP modify chỉ áp dụng các ticket cùng symbol + magic.
**Why human:** Cần broker/terminal state thật để xác nhận `OrderSend`/`PositionModify` runtime.

### Gaps Summary

Không có gap blocking được phát hiện trong code tĩnh hoặc compile log. Trạng thái là `human_needed` vì hai hành vi trading runtime phụ thuộc terminal MT5/live account state và cần kiểm thử người dùng để xác nhận end-to-end.

---

_Verified: 2026-04-30T12:21:51Z_
_Verifier: Claude (gsd-verifier)_
