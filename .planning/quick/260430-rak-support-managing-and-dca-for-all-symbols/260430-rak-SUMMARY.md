---
phase: quick-260430-rak-support-managing-and-dca-for-all-symbols
plan: 01
subsystem: mql5-provider
tags: [mql5, dca, cisd, multi-symbol, safety]
dependency_graph:
  requires: [260430-qmk]
  provides: [multi-symbol-provider-dca-cisd]
  affects: [mql5/AureusProvider_v2.mq5]
tech_stack:
  added: []
  patterns: [per-symbol-state-array, explicit-symbol-parameter]
key_files:
  created: []
  modified:
    - mql5/AureusProvider_v2.mq5
    - mql5/AureusProvider_v2_compile.log
decisions:
  - "Giữ `_Period` cho LTF scan như plan yêu cầu, chỉ thay `_Symbol` bằng symbol explicit trong CISD/DCA helper path."
metrics:
  duration: "~6 phút"
  completed_date: "2026-04-30T12:48:00Z"
---

# Quick 260430-rak: Support managing and DCA for all symbols Summary

Provider-local CISD/DCA gate đã chuyển từ chart-symbol-bound sang quét toàn bộ symbol trong `InpSymbols`, với trạng thái DCA gate tách riêng theo từng symbol và compile MetaEditor sạch 0 lỗi, 0 warning.

## Kết quả chính

- Thêm `CISDDCAState` để lưu riêng theo symbol: H1 signal type/time, LTF scan start, last trade signal time, current H1 signal time, bull/bear setup.
- `UpdateCISDDCAH1State` nhận `string symbol` và `CISDDCAState &state`, không còn dùng `_Symbol` để xác định symbol dữ liệu H1.
- `CheckDCAEntryConditionFromCISD` nhận `string symbol` và `CISDDCAState &state`, dùng explicit symbol cho `Bars`, `iBarShift`, `iOpen`, `iClose`, `iTime`, `FindDCAMagicForSymbolDirection`, và `DoDCA`.
- `OnTimer` gọi CISD/DCA gate trong loop `g_symbolCount`, dùng `g_contexts[i].symbol` và `g_cisdDCAStates[i]`.
- Giữ nguyên safety invariant: DCA vẫn gọi `DoDCA(direction, symbol, magic)` sau khi magic được resolve cùng symbol + direction; duplicate strategy guard trong `ExecuteOpenOrder` vẫn match cả symbol và magic cho positions/pending orders.

## Verification

- Compile command đã chạy trực tiếp MetaEditor:
  - `"/e/Openclaw/MetaTrader5/MetaEditor64.exe" /compile:"D:/Aureus/mql5/AureusProvider_v2.mq5" /log:"D:/Aureus/mql5/AureusProvider_v2_compile.log"`
- Compile log xác nhận: `Result: 0 errors, 0 warnings`.
- Node check compile log đã pass với UTF-16LE parsing.
- Manual diff review xác nhận code change chỉ ở `mql5/AureusProvider_v2.mq5`; compile evidence ở `mql5/AureusProvider_v2_compile.log`.

## GitNexus impact / detect_changes

GitNexus CLI được thử theo yêu cầu trước khi sửa các symbol liên quan:

- Lần đầu thiếu repo explicit: CLI báo có nhiều repo indexed và yêu cầu chỉ định repo.
- Chạy lại với `--repo Aureus`:
  - `OnTimer`: `Target 'OnTimer' not found`
  - `CheckDCAEntryConditionFromCISD`: `Target 'CheckDCAEntryConditionFromCISD' not found`
  - `UpdateCISDDCAH1State`: `Target 'UpdateCISDDCAH1State' not found`
  - `DoDCA`: `Target 'DoDCA' not found`

Fallback evidence: GitNexus không resolve được các symbol MQL5 này trong index hiện tại, nên blast radius được kiểm bằng code-local search/diff:

- Direct caller của `UpdateCISDDCAH1State`: `CheckDCAEntryConditionFromCISD`.
- Direct caller của `CheckDCAEntryConditionFromCISD`: `OnTimer`.
- Direct caller của `DoDCA`: `CheckDCAEntryConditionFromCISD` và command path hiện hữu quanh dòng `DoDCA(direction == "BUY" ? 1 : -1, symbol, magic)`.
- Risk đánh giá: MEDIUM vì timer-driven DCA có thể mở/modify live trades, nhưng thay đổi được giới hạn trong provider-local DCA/CISD path và giữ symbol+magic boundary.

`npx gitnexus detect_changes --repo Aureus` cũng được thử nhưng CLI báo `error: unknown command 'detect_changes'`. Fallback: dùng `git diff` và targeted grep để xác nhận scope và invariant.

## Deviations from Plan

None - plan executed đúng phạm vi. Không có thay đổi kiến trúc, database, socket, backfill, reporting hoặc order execution ngoài DCA/CISD timer path.

## Auto-fixed Issues

Không có.

## Threat Flags

Không có threat surface mới ngoài trust boundary đã được plan nêu. Thay đổi chỉ thu hẹp/đúng hóa symbol scoping cho timer-driven broker trade operations.

## Known Stubs

Không có stub mới.

## Commits

- `c470aed` - `fix(quick-260430-rak): scan DCA CISD for all provider symbols`
- `328891d` - `chore(quick-260430-rak): record clean provider compile`

## Self-Check: PASSED

- Xác nhận tồn tại `D:/Aureus/mql5/AureusProvider_v2.mq5`.
- Xác nhận tồn tại `D:/Aureus/mql5/AureusProvider_v2_compile.log`.
- Xác nhận tồn tại `D:/Aureus/.planning/quick/260430-rak-support-managing-and-dca-for-all-symbols/260430-rak-SUMMARY.md`.
- Xác nhận commit `c470aed` và `328891d` có trong git log.
