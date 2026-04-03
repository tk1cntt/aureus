---
phase: 15.8
slug: signal-nautilus-order-open-delivery-diagnosis-contract-alignment
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-26
updated: 2026-03-26
---

# Phase 15.8 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest + runtime log/metric evidence |
| Config file | existing service test configuration |
| Quick run command | `pytest services/aureus-signal/tests -q` |
| Full suite command | `pytest services/aureus-signal/tests services/aureus-nautilus-node/tests -q` |
| Estimated runtime | ~90-240s |

## Sampling Rate
- Sau mỗi task contract/wiring diagnosis: chạy quick command liên quan.
- Sau mỗi wave plan: chạy full suite command.
- Trước `/gsd-verify-work`: full suite phải xanh.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|
| 15.8-01-T1 | 01 | 1 | Internal runtime integration debug/alignment | static + runtime evidence | `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.8"` | ✅ | ⬜ pending |
| 15.8-01-T2 | 01 | 1 | Stream/symbol contract alignment | focused tests + integration logs | `pytest services/aureus-signal/tests -q` | ✅ | ⬜ pending |
| 15.8-01-T3 | 01 | 1 | ORDER_OPEN payload contract + observability | integration + diagnostics | `pytest services/aureus-nautilus-node/tests -q` | ✅ | ⬜ pending |

## Wave 0 Requirements
- Existing test infrastructure available.
- Không cần cài framework mới ở phase này.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Theo dõi chuỗi stream multi-symbol từ publish tới consume | Internal runtime integration debug/alignment | Cần quan sát runtime log/metric liên service | Publish test event cho `XAUUSD` + `ETHUSD`, xác nhận cả 2 được consume hoặc reject đúng taxonomy reason-code |

## Validation Sign-Off
- [x] Có mapping verify cho mọi task của plan 01.
- [x] Có quick/full command rõ ràng, không watch-mode.
- [x] Wave 0 không thiếu dependency.
- [x] `nyquist_compliant: true` đã set.
- [ ] Approval: pending execution evidence.
