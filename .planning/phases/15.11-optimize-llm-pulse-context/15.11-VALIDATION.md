---
phase: 15.11
slug: optimize-llm-pulse-context
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-28
updated: 2026-03-28
---

# Phase 15.11 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest + targeted async tests |
| Config file | existing `services/aureus-signal/tests` pytest config |
| Quick run command | `python -m pytest services/aureus-signal/tests/test_pulse_prompt_cli.py -q` |
| Full suite command | `python -m pytest services/aureus-signal/tests/test_pulse_prompt_cli.py services/aureus-signal/tests/test_signal_contract_normalization.py -q` |
| Estimated runtime | ~30-120s |

## Sampling Rate
- Sau mỗi task chỉnh payload/prompt: chạy quick command
- Sau khi hoàn tất plan 01: chạy full suite command
- Trước handoff execution: full suite phải xanh

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|
| 15.11-01-T1 | 01 | 1 | Deterministic context payload | unit + mock assertions for context builder | `python -m pytest services/aureus-signal/tests/test_pulse_prompt_cli.py -k "run_prompt_test_with_call_api_false" -q` | ✅ implemented | ✅ passed |
| 15.11-01-T2 | 01 | 1 | Stable prompt + flat pulse contract | async mock parsing + contract checks | `python -m pytest services/aureus-signal/tests/test_pulse_prompt_cli.py -k "run_prompt_test_with_call_api_true" -q` | ✅ implemented | ✅ passed |
| 15.11-01-T3 | 01 | 1 | End-to-end analyzer fallback safety | contract regression for normalized output shape | `python -m pytest services/aureus-signal/tests/test_signal_contract_normalization.py -q` | ✅ implemented | ✅ passed |
| 15.11-01-T4 | 01 | 1 | Standalone prompt/context test tool from JSON input | unit + async mock tests for CLI adapter | `python -m pytest services/aureus-signal/tests/test_pulse_prompt_cli.py -q` | ✅ implemented | ✅ passed |

## Wave 0 Requirements
- Reuse pytest stack hiện có, không thêm framework mới
- Dùng mock `AsyncOpenAI` response cho deterministic contract checks

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Narrative pulse không “đổi giọng” khi anchors tương đương | Deterministic high-frequency narrative | Cần đối chiếu cảm nhận output theo chuỗi iteration | Replay cùng 1 snapshot state nhiều lần, so sánh `sentiment`, `aci`, và 2-3 câu narrative |
| Trigger-specific emphasis xuất hiện đúng khi có event mới | Trigger relevance | Cần đánh giá chất lượng diễn giải ngữ nghĩa | Inject event mới vào normalized history, gọi pulse và kiểm tra narrative có nhắc đúng trigger |

## Validation Sign-Off
- [x] Có mapping verify cho mọi task của plan 01
- [x] Có quick/full command rõ ràng, không watch-mode
- [x] Wave 0 không thiếu dependency mới
- [x] `nyquist_compliant: true` đã set
- [x] Execution evidence captured: `16 passed` (`test_pulse_prompt_cli.py` + `test_signal_contract_normalization.py`)
- [x] `gitnexus_detect_changes(scope="all")` đã chạy để kiểm tra phạm vi ảnh hưởng
