---
phase: 15.9
slug: enrich-signal-history-with-semantic-metadata
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-27
updated: 2026-03-27
---

# Phase 15.9 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest + focused runtime smoke |
| Config file | existing service test configuration |
| Quick run command | `pytest tests/test_decision_trace_schema.py tests/test_signal_contract_normalization.py -q` |
| Full suite command | `pytest tests/test_decision_trace_schema.py tests/test_signal_contract_normalization.py tests/test_state_snapshot.py -q` |
| Estimated runtime | ~30-120s |

## Sampling Rate
- Sau mỗi task reconcile contract: chạy quick command
- Sau khi hoàn tất plan wave: chạy full suite command
- Trước verify/handoff: full suite phải xanh

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|
| 15.9-01-T1 | 01 | 1 | Logging contract stabilization | unit + schema checks | `pytest tests/test_signal_contract_normalization.py -q` | ✅ | ⬜ pending |
| 15.9-01-T2 | 01 | 1 | Producer call-site alignment | integration-focused | `pytest tests/test_decision_trace_schema.py -q` | ✅ | ⬜ pending |
| 15.9-01-T3 | 01 | 1 | Consumer/snapshot safety | restore + compatibility | `pytest tests/test_state_snapshot.py -q` | ✅ | ⬜ pending |

## Wave 0 Requirements
- Existing test framework and fixtures available
- Không cần thêm dependency/framework mới

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Signal records giữ metadata nhưng không mất `tag/t` | Internal semantic observability | Cần đọc payload runtime thực tế | Chạy loop live/backtest ngắn, inspect payload ở logger/snapshot output |

## Validation Sign-Off
- [x] Có mapping verify cho mọi task của plan 01
- [x] Có quick/full command rõ ràng, không watch-mode
- [x] Wave 0 không thiếu dependency
- [x] `nyquist_compliant: true` đã set
- [ ] Approval: pending execution evidence
