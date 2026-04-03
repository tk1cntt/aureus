---
phase: 15.7
slug: sequence-enabled-but-no-entry-trigger-diagnosis
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-24
updated: 2026-03-24
---

# Phase 15.7 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest + runtime log trace review |
| Config file | existing service test configuration |
| Quick run command | `pytest services/aureus-signal/tests -q` |
| Full suite command | `pytest services/aureus-signal/tests services/aureus-signal/unittest -q` |
| Estimated runtime | ~60-180s |

## Sampling Rate
- Sau mỗi task diagnosis/instrumentation: chạy quick command liên quan
- Sau mỗi wave plan: chạy full suite command
- Trước `/gsd-verify-work`: full suite phải xanh

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|
| 15.7-01-T1 | 01 | 1 | Internal debug observability | static + log evidence | `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.7"` | ✅ | ⬜ pending |
| 15.7-01-T2 | 01 | 1 | Entry validation diagnosis | focused runtime tests | `pytest services/aureus-signal/tests -q` | ✅ | ⬜ pending |
| 15.7-01-T3 | 01 | 1 | Order-plan / guard diagnosis | integration + replay evidence | `pytest services/aureus-signal/unittest -q` | ✅ | ⬜ pending |

## Wave 0 Requirements
- Existing test infrastructure available
- Không cần cài framework mới ở phase này

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Correlate A/B/C/D checkpoints theo cùng candle | Internal debug observability | Cần đọc log chuỗi theo context runtime | Thu log pipeline prefix theo `bar_t`, `strategy_id`, `trace_id`; xác định điểm nghẽn đầu tiên |

## Validation Sign-Off
- [x] Có mapping verify cho mọi task của plan 01
- [x] Có quick/full command rõ ràng, không watch-mode
- [x] Wave 0 không thiếu dependency
- [x] `nyquist_compliant: true` đã set
- [ ] Approval: pending execution evidence
