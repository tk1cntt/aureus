---
phase: 31-mt5-history-sync
verified: 2026-04-20T14:00:00Z
status: human_needed
score: 2/2 requirements have evidence
overrides_applied: 0
human_verification:
  - test: "MT5 live close/order lifecycle timing"
    expected: "OnTradeTransaction push + poll reconciliation cùng phản ánh đúng trade close trong runtime thật"
    why_human: "Cần MT5 terminal + broker/session live; không thể xác nhận đầy đủ chỉ bằng docs/tests hiện có"
---

# Phase 31: MT5 History Sync Verification Report

**Phase Goal:** Đồng bộ lịch sử trade theo hybrid path (push realtime + poll reconciliation) để giảm mất dữ liệu khi disconnect/restart.
**Verified:** 2026-04-20T14:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification backfill for phase 47

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | DB writer có cơ chế recover message unacked khi startup để giảm mất order events sau gián đoạn. | ✓ VERIFIED | `services/aureus-db-writer/main.py` có `check_xpending()` + gọi trước main loop (theo `31-01-SUMMARY.md`). Validation map có test `tests/test_xpending.py` và `tests/test_order_persistence.py`. |
| 2 | Reconciliation loop poll MT5 history có thể phát hiện trade thiếu và insert lại với trạng thái `RECONCILED`. | ✓ VERIFIED | `services/aureus-db-writer/main.py` có `reconciliation_loop()`/`run_reconciliation()`; schema có `aureus_reconciliation_log` tại `services/aureus-db-writer/schema.sql`; validation map liệt kê `tests/test_reconciliation.py` cases (`missing_trade_detection`, `reconciled_insert`, `discrepancy_log`). |

### Requirements Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| TRADE-03 | human_needed | **Artifact/code-path:** `mql5/AureusProvider.mq5` (history response path), `services/aureus-db-writer/main.py` (`check_xpending`, order persistence flow). **Test/command:** `python3 -m pytest services/aureus-db-writer/tests/test_order_persistence.py -q -x` (plan verify target). **Flow/key-link:** `OnTradeTransaction`/order event push path + startup XPENDING recovery. **Manual gate:** cần MT5 live để xác nhận timing close notification E2E. |
| TRADE-04 | human_needed | **Artifact/code-path:** `services/aureus-db-writer/main.py` (`reconciliation_loop`, `run_reconciliation`, `insert_reconciled_trade`), `services/aureus-db-writer/schema.sql` (`aureus_reconciliation_log`), `mql5/AureusProvider.mq5` (`REQUEST_TRADE_HISTORY`). **Test/command:** `python3 -m pytest services/aureus-db-writer/tests/test_reconciliation.py -q -x` (plan verify target). **Flow/key-link:** DB query recent trades → publish `REQUEST_TRADE_HISTORY` → receive `TRADE_HISTORY` → detect missing ticket → insert `RECONCILED`. **Manual gate:** cần môi trường MT5+Redis+Postgres live để xác nhận discrepancy thực tế. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `services/aureus-db-writer/main.py` | `mql5/AureusProvider.mq5` | Redis publish `REQUEST_TRADE_HISTORY` ↔ EA `TRADE_HISTORY` response | ✓ WIRED | Bằng chứng từ `31-01-SUMMARY.md` + plan 31 key link pattern `REQUEST_TRADE_HISTORY.*TRADE_HISTORY`. |
| `services/aureus-db-writer/main.py` | `services/aureus-db-writer/main.py` | Startup gọi `await self.check_xpending()` trước vòng lặp chính | ✓ WIRED | Có trong plan 31 key link và summary implementation details. |
| Push path (`OnTradeTransaction`) | Poll fallback (`reconciliation_loop`) | Hybrid coverage cho close history sync | ✓ WIRED (partial runtime) | Static+test evidence có; runtime timing cần manual confirmation để chốt full E2E. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Order persistence + reconciliation unit/integration checks | `python3 -m pytest services/aureus-db-writer/tests/test_order_persistence.py services/aureus-db-writer/tests/test_reconciliation.py -q -x` | Pending run in phase 47-02 execution | ⏳ PENDING |

### Human Verification Required

1. **MT5 close notification runtime timing**
   - **Test:** chạy terminal MT5 test, mở/đóng lệnh thật, đối chiếu timestamps giữa event push và dữ liệu reconciliation.
   - **Expected:** close trade xuất hiện đúng qua ít nhất 1 trong 2 path (push realtime hoặc poll fallback), không mất dữ liệu cuối cùng.
   - **Why human:** cần runtime hạ tầng live, không thể suy luận hoàn toàn từ artifact.

## Gaps Summary

Không có gap implementation mới được tạo trong phase 47. Các thiếu hụt của phase 31 hiện là **verification runtime confidence** (manual gate), không phải yêu cầu sửa logic trong phase này.

---

_Verified: 2026-04-20T14:00:00Z_
_Verifier: Claude (phase 47 execute)_