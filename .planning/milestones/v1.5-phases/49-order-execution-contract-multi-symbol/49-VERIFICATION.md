---
phase: 49-order-execution-contract-multi-symbol
verified: 2026-04-20T09:40:00Z
status: gaps_found
score: 3/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "ORDER_OPEN thiếu trace_id/symbol/side/qty bị reject với reason code ổn định."
    status: failed
    reason: "Execution client hiện trả reason code rời rạc (MISSING_TRACE_ID/INVALID_QTY/INVALID_SIDE), không còn reason code contract ORDER_OPEN_MISSING_CRITICAL_FIELD như must-have."
    artifacts:
      - path: "services/aureus-nautilus-node/execution_client.py"
        issue: "_validate_and_build_orders trả MISSING_TRACE_ID/INVALID_QTY thay vì ORDER_OPEN_MISSING_CRITICAL_FIELD"
      - path: "services/aureus-nautilus-node/tests/test_execution_client.py"
        issue: "Test kỳ vọng ORDER_OPEN_MISSING_CRITICAL_FIELD đang fail"
    missing:
      - "Chuẩn hóa reject critical fields về ORDER_OPEN_MISSING_CRITICAL_FIELD"
      - "Đồng bộ implementation và regression tests để không drift reason-code"
  - truth: "ORDER_OPEN hợp lệ tạo được ENTRY + contingent SL/TP theo đúng side và qty."
    status: failed
    reason: "Path consume không chấp nhận payload chỉ có quantity alias; code chỉ đọc qty nên reject INVALID_QTY, trái contract qty|quantity."
    artifacts:
      - path: "services/aureus-nautilus-node/execution_client.py"
        issue: "qty_raw chỉ lấy data.get('qty'), không fallback data.get('quantity')"
      - path: "services/aureus-nautilus-node/tests/test_execution_risk_controls.py"
        issue: "Test quantity alias kỳ vọng pass nhưng code không support"
    missing:
      - "Thêm canonicalization qty ưu tiên + fallback quantity ở execution boundary"
      - "Giữ contingent generation dùng qty canonical sau normalize"
  - truth: "Lifecycle report giữ được strategy_id/strategy_name/correlation context khi intent đã tồn tại."
    status: failed
    reason: "Bridge lifecycle handler có lỗi cú pháp (double else cùng cấp) nên module không import được; toàn bộ lifecycle lineage path không chạy."
    artifacts:
      - path: "services/aureus-nautilus-bridge/main.py"
        issue: "SyntaxError tại _handle_lifecycle_message (else ở line ~225)"
      - path: "services/aureus-nautilus-bridge/tests/test_bridge_lineage.py"
        issue: "Pytest fail ngay lúc collect vì main.py SyntaxError"
    missing:
      - "Sửa nhánh if/else trong _handle_lifecycle_message để module chạy được"
      - "Khôi phục pending_intents merge path để retention strategy/correlation hoạt động"
---

# Phase 49: order-execution-contract-multi-symbol Verification Report

**Phase Goal:** Chuẩn hóa ORDER_OPEN payload contract và execution consume path multi-symbol để loại bỏ reject sai và hardcode XAUUSD.
**Verified:** 2026-04-20T09:40:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | ORDER_OPEN thiếu trace_id/symbol/side/qty bị reject với reason code ổn định. | ✗ FAILED | `execution_client.py` trả `MISSING_TRACE_ID`/`INVALID_QTY`; test `test_order_open_missing_critical_field_has_stable_reason_code` fail. |
| 2 | ORDER_OPEN hợp lệ tạo được ENTRY + contingent SL/TP theo đúng side và qty. | ✗ FAILED | `execution_client.py` không fallback `quantity`; test `test_valid_order_generates_entry_plus_sl_tp_contingents` (quantity alias) fail. |
| 3 | trace_id duplicate bị chặn deterministic, không phát sinh order mới. | ✓ VERIFIED | `_seen_trace_ids` vẫn enforce; test duplicate trong `test_execution_risk_controls.py` đúng hành vi. |
| 4 | Execution client poll được nhiều stream orders theo symbol thay vì mặc định singleton XAUUSD. | ✓ VERIFIED | `_discover_order_streams()` scan `aureus:stream:*:orders`, lọc whitelist, không inject `XAUUSD`; test policy/contract hiện diện. |
| 5 | Mọi mismatch symbol giữa stream và payload bị reject reason code SYMBOL_STREAM_MISMATCH. | ✓ VERIFIED | `_validate_and_build_orders` check `_stream_symbol != symbol` và trả `SYMBOL_STREAM_MISMATCH` + metric counter. |
| 6 | Bridge lifecycle giữ lineage strategy/correlation và fallback tối thiểu hợp lệ. | ✗ FAILED | `services/aureus-nautilus-bridge/main.py` có SyntaxError ở `_handle_lifecycle_message`; `pytest test_bridge_lineage.py` lỗi collect. |

**Score:** 3/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `services/aureus-nautilus-node/execution_client.py` | Contract validation + idempotency + multi-stream consume | ⚠️ HOLLOW — wired but data/contract drift | File substantive + wired, nhưng contract qty alias/reason code lệch must-have. |
| `services/aureus-nautilus-node/settings.py` | Multi-symbol whitelist validation | ✓ VERIFIED | Enforce `NAUTILUS_SYMBOL_WHITELIST` non-empty; bỏ default singleton XAUUSD. |
| `services/aureus-nautilus-node/tests/test_execution_client.py` | Regression contract tests | ⚠️ ORPHANED-CONTRACT | Test chứa kỳ vọng contract mới nhưng implementation không đáp ứng (4 failed). |
| `services/aureus-nautilus-node/tests/test_execution_risk_controls.py` | Contingent + duplicate tests | ✓ VERIFIED | Cover duplicate + contingent path, dù contingent alias quantity đang lệch implementation. |
| `services/aureus-nautilus-node/tests/test_execution_multi_symbol_contract.py` | Multi-symbol contract tests | ✓ VERIFIED | Có test mismatch/cursor độc lập. |
| `services/aureus-nautilus-bridge/mapper.py` | Canonical qty|quantity + lineage passthrough | ✓ VERIFIED | `quantity` canonical, fallback `qty`, passthrough strategy/correlation fields. |
| `services/aureus-nautilus-bridge/main.py` | Lifecycle lineage retention + minimal fallback | ✗ STUB/BROKEN | SyntaxError khiến artifact không runnable. |
| `services/aureus-nautilus-bridge/tests/test_bridge_lineage.py` | Regression lifecycle lineage | ✗ BLOCKED | Không chạy được do import `main.py` lỗi cú pháp. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `orders.py` | `execution_client.py` | Redis stream ORDER_OPEN payload | WIRED | gsd-tools verify key-links: pattern found. |
| `settings.py` | `execution_client.py` | `symbol_whitelist` policy | WIRED | `_build_policy` consume whitelist từ settings. |
| `execution_client.py` | `test_execution_client_policy.py` | mismatch guard | WIRED | Test assert `SYMBOL_STREAM_MISMATCH` tồn tại. |
| `main.py` | `mapper.py` | `map_order_intent` before normalize | PARTIAL | Call-site có, nhưng runtime broken bởi SyntaxError nên link không hoạt động thực thi. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `execution_client.py` | `qty` cho ENTRY/SL/TP | payload `data` từ Redis stream | Partial | ⚠️ STATIC CONTRACT DRIFT — chỉ đọc `qty`, không nhận `quantity`. |
| `execution_client.py` | `stream_symbol` mismatch guard | `_extract_stream_symbol` từ stream key | Yes | ✓ FLOWING |
| `main.py` lifecycle path | `order_payload` + pending_intents merge | lifecycle report + `pending_intents` | No (code không compile) | ✗ DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Execution contract regression | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py -q` | 4 failed (reason code/quantity alias/fallback metrics drift) | ✗ FAIL |
| Bridge lineage regression | `python3 -m pytest D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_lineage.py -q` | Import error: SyntaxError in `main.py` | ✗ FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ORDER-01 | 49-01, 49-02 | Nhận strategy match từ Redis pub/sub | ✗ BLOCKED | Multi-stream poll có, nhưng contract validation drift làm reject sai payload hợp lệ. |
| ORDER-02 | 49-01 | Tạo/gửi market order | ✗ BLOCKED | Hành vi contingent/entry với payload `quantity` fail; test regression đang đỏ. |
| ORDER-03 | 49-03 | Pending order (limit/stop) execution path | ✗ BLOCKED | Bridge lifecycle handler không compile, path mapper->lifecycle không chạy. |
| PH45-05 | 49-01 | Idempotency strict theo trace_id | ✓ SATISFIED | `_seen_trace_ids` + reason `DUPLICATE_TRACE_ID` vẫn hoạt động. |
| PH45-06 | 49-02 | Per-symbol circuit/backlog runtime independence | ? NEEDS HUMAN | Đã có code/test per-stream cursor; cần runtime integration với Redis tải thật để xác nhận hành vi vận hành. |
| PH45-07 | 49-03 | Rollout/lineage evidence per-symbol | ✗ BLOCKED | Lineage path chính bị chặn do SyntaxError ở bridge main lifecycle handler. |

Orphaned requirements from phase plans vs REQUIREMENTS.md: **None** (ORDER-01, ORDER-02, ORDER-03, PH45-05, PH45-06, PH45-07 đều đã được account).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `services/aureus-nautilus-bridge/main.py` | ~225 | Double `else` cùng block trong `_handle_lifecycle_message` | 🛑 Blocker | Module không import được, chặn toàn bộ lifecycle flow + tests. |
| `services/aureus-nautilus-node/execution_client.py` | 152-186 | Contract drift: reason code granular thay vì stable critical-field code | ⚠️ Warning | Vi phạm must-have deterministic reason code; regression test fail. |
| `services/aureus-nautilus-node/execution_client.py` | 175-177 | Không có qty/quantity canonical fallback | ⚠️ Warning | Payload hợp lệ theo alias bị reject sai `INVALID_QTY`. |

### Human Verification Required

### 1. Multi-symbol runtime fairness under real Redis load

**Test:** Chạy node execution trên môi trường staging với >=2 symbols active, bơm ORDER_OPEN liên tục và theo dõi per-symbol lag/backlog.
**Expected:** Không starvation giữa symbols; cursor theo stream tiến độc lập; mismatch guard chỉ reject đúng stream-symbol lệch.
**Why human:** Cần môi trường runtime thật (Redis streams live + load profile), không thể xác minh đầy đủ chỉ bằng static check.

## Gaps Summary

Phase 49 chưa đạt goal vì có 3 blocker chính trên đường contract thực thi:
1. Contract-first validation bị lệch: reason code critical fields không còn ổn định theo must-have.
2. Qty alias canonicalization bị regression: payload dùng `quantity` vẫn bị reject.
3. Bridge lifecycle path bị lỗi cú pháp, khiến lineage/fallback multi-symbol không thể chạy.

Do đó trạng thái là `gaps_found` (không phải `human_needed`) vì tồn tại lỗi code/blocker cụ thể cần sửa trước.

---

_Verified: 2026-04-20T09:40:00Z_
_Verifier: Claude (gsd-verifier)_
