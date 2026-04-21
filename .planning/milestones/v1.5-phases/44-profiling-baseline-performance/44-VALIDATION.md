---
phase: 44
slug: profiling-baseline-performance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `services/aureus-gateway/tests/pytest.ini` (chưa thấy pytest.ini riêng cho aureus-signal) |
| **Quick run command** | `pytest services/aureus-signal/tests/test_ob_numpy.py -q -x` |
| **Full suite command** | `pytest services/aureus-signal/tests -q -x` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest services/aureus-signal/tests -k "structure or ob_numpy or multi_symbol" -q -x`
- **After every plan wave:** Run `pytest services/aureus-signal/tests -q -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | PH44-PARITY | T-44-01 | Đảm bảo old/new parity và fallback khi mismatch | replay/contract | `pytest services/aureus-signal/tests -k "structure and (parity or shadow)" -q -x` | ❌ W0 | ⬜ pending |
| 44-01-02 | 01 | 1 | PH44-MODE | T-44-02 | Validate mode `off|shadow|on` không phá hành vi hiện có | unit | `pytest services/aureus-signal/tests -k "structure_mode_flag" -q -x` | ❌ W0 | ⬜ pending |
| 44-02-01 | 02 | 2 | PH44-PERF | T-44-03 | Đảm bảo giảm latency >=40% trên replay chuẩn | regression/perf | `pytest services/aureus-signal/tests -k "structure_replay_regression" -q -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/aureus-signal/tests/test_structure_parity_shadow.py` — contract parity old/new + mismatch fallback
- [ ] `services/aureus-signal/tests/test_structure_mode_flag.py` — validate `off|shadow|on`
- [ ] `services/aureus-signal/tests/test_structure_replay_regression.py` — replay dataset chuẩn cho gate 40%

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Shadow rollout quan sát mismatch bằng telemetry production-like | PH44-PARITY | Cần môi trường chạy thực tế theo symbol/time-window thật | Bật `AUREUS_STRUCTURE_OPT_MODE=shadow`, theo dõi mismatch logs 24h, xác nhận mismatch=0 trước khi chuyển `on` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
