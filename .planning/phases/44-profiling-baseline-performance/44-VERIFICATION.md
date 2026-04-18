---
phase: 44-profiling-baseline-performance
verified: 2026-04-18T03:48:21Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Shadow rollout quan sát mismatch trên môi trường production-like"
    expected: "AUREUS_STRUCTURE_OPT_MODE=shadow cho mismatch = 0 trong cửa sổ quan sát trước khi promote on"
    why_human: "Cần telemetry runtime thật theo symbol/time-window production, không thể xác nhận chỉ bằng static/code scan"
---

# Phase 44: Profiling Baseline Performance Verification Report

**Phase Goal:** Tối ưu `StructureSignal` để giảm latency/candle nhưng không thay đổi logic trading hiện tại (strict parity), rollout an toàn qua mode `off|shadow|on`.
**Verified:** 2026-04-18T03:48:21Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | User vận hành có thể bật/tắt tối ưu structure bằng mode `off|shadow|on` mà không đổi behavior mặc định. | ✓ VERIFIED | `structure.py` có `_get_structure_opt_mode()` parse `AUREUS_STRUCTURE_OPT_MODE` với whitelist + default `off` (lines 25-29). `test_structure_mode_flag.py` có test parametrize `off|shadow|on`, invalid->off, missing->off và `off` chỉ chạy old path. Spot-check: `PYTHONPATH="/d/Aureus/services/aureus-signal" pytest ...test_structure_mode_flag.py ...test_structure_parity_shadow.py -q -x` => `9 passed`. |
| 2 | Shadow mode luôn so sánh old/new output contract và tự fallback old path khi mismatch. | ✓ VERIFIED | `calculate()` mode `shadow` chạy cả `_calculate_old_path` + `_calculate_optimized_path`, snapshot + compare contract, restore state old và return `old_result` (lines 67-82). Test mismatch fallback có trong `test_structure_parity_shadow.py` (`test_shadow_mismatch_fallbacks_to_old`). |
| 3 | Parity checker bao phủ đầy đủ `transient_signals`, `obs`, `swing_points` để tránh mismatch ngầm. | ✓ VERIFIED | `_compare_shadow_contract()` so sánh các field `transient_signals`, `obs`, `swing_points`, `result` (lines 42-47). Test `test_shadow_compares_full_contract_fields` và replay parity full-contract assertion (`test_replay_parity_full_contract_identical`). |
| 4 | Structure processor giảm latency trung bình tối thiểu 40% trên replay dataset chuẩn (điều kiện tương đương). | ✓ VERIFIED | `test_structure_replay_regression.py` có gate cứng `new_avg_ms <= old_avg_ms * 0.60` (lines 104-108). Spot-check: `pytest /d/Aureus/services/aureus-signal/tests/test_structure_replay_regression.py -q -x` => `3 passed`. |
| 5 | Tối ưu A (array access) không làm lệch parity so với old path trên bộ replay contract. | ✓ VERIFIED | `_calculate_optimized_path` dùng `to_numpy` cho `t/o/h/l/c` (lines 173-177), replay parity test so full contract + diff fields (lines 84-95), `test_ob_numpy.py` khóa parity OB/swing/transient ob_state. Spot-check: `pytest /d/Aureus/services/aureus-signal/tests/test_ob_numpy.py -q -x` => `6 passed`. |
| 6 | Có evidence kiểm thử tự động để quyết định promote mode từ shadow sang on. | ✓ VERIFIED | Có đủ bộ test mode/parity/replay regression: `test_structure_mode_flag.py`, `test_structure_parity_shadow.py`, `test_structure_replay_regression.py`, `test_ob_numpy.py`; fail message có context `symbol`, `t`, `diff_fields` cho parity/perf gate. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `services/aureus-signal/engine/signals/structure.py` | Runtime mode + shadow comparator + fallback + A-first optimization | ✓ VERIFIED | `gsd-tools verify artifacts` plan 44-01/44-02 đều pass; có mode parser, old/new branch, comparator, mismatch log, array-centric path. |
| `services/aureus-signal/tests/test_structure_mode_flag.py` | Test mode `off|shadow|on` và default safety | ✓ VERIFIED | File tồn tại, substantive, test pass (9 tests cùng parity file). |
| `services/aureus-signal/tests/test_structure_parity_shadow.py` | Test parity contract + mismatch fallback behavior | ✓ VERIFIED | Có test compare full contract + shadow/on fallback old path khi mismatch. |
| `services/aureus-signal/tests/test_structure_replay_regression.py` | Replay regression parity + perf gate 40% | ✓ VERIFIED | Có deterministic replay dataset + assert `<= 0.60` + mismatch context assertion. |
| `services/aureus-signal/tests/test_ob_numpy.py` | Regression coverage OB/swing sau tối ưu | ✓ VERIFIED | Có `TestStructureArrayPathParity` assert old/new parity cho result, obs, swing_points, ob_state. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `structure.py` | `AUREUS_STRUCTURE_OPT_MODE` | env parsing and runtime branch selection | WIRED | `gsd-tools verify key-links` 44-01: verified=true. |
| `structure.py` | old/new structure execution paths | shadow compare then fallback on mismatch | WIRED | `gsd-tools verify key-links` 44-01: verified=true. |
| `test_structure_replay_regression.py` | `structure.py` | replay old vs new path with deterministic dataset | WIRED | `gsd-tools verify key-links` 44-02: verified=true (`_calculate_old_path/_calculate_optimized_path`). |
| optimization branch in `structure.py` | mode on/shadow from 44-01 | shared runtime branch execution | WIRED (manual) | `gsd-tools` báo `Source file not found` do chuỗi `from` trong plan là mô tả, không phải path thật; kiểm tra manual tại `calculate()` lines 83-96 xác nhận optimized path nằm trong nhánh mode `on`, còn `shadow` lines 67-82. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `structure.py::calculate` | `mode` | `os.getenv("AUREUS_STRUCTURE_OPT_MODE")` -> `_get_structure_opt_mode` | Yes | ✓ FLOWING |
| `structure.py::_calculate_optimized_path` | `t_values/h_values/l_values/o_values/c_values` | `df[cols].to_numpy(...)` | Yes (dữ liệu runtime từ DataFrame) | ✓ FLOWING |
| `test_structure_replay_regression.py` | `old_avg_ms/new_avg_ms` + `old_contract/new_contract` | `_run_and_measure` gọi trực tiếp old/new path trên replay dataset deterministic | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Mode + parity fallback hoạt động | `PYTHONPATH="/d/Aureus/services/aureus-signal" pytest /d/Aureus/services/aureus-signal/tests/test_structure_mode_flag.py /d/Aureus/services/aureus-signal/tests/test_structure_parity_shadow.py -q -x` | `9 passed in 0.49s` | ✓ PASS |
| Replay parity + perf gate 40% hoạt động | `pytest /d/Aureus/services/aureus-signal/tests/test_structure_replay_regression.py -q -x` | `3 passed in 0.96s` | ✓ PASS |
| OB/swing parity sau array optimization | `pytest /d/Aureus/services/aureus-signal/tests/test_ob_numpy.py -q -x` | `6 passed in 0.51s` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PH44-PARITY | 44-01, 44-02 | Giữ strict parity old/new contract + fallback an toàn khi mismatch | ✓ SATISFIED | Comparator full contract trong `structure.py`; test parity/shadow + replay parity pass; mismatch context có `symbol/t/diff_fields`. |
| PH44-MODE | 44-01 | Runtime mode `off|shadow|on`, invalid/missing về `off`, giữ behavior mặc định an toàn | ✓ SATISFIED | `_get_structure_opt_mode` whitelist/default off + test mode flag đầy đủ và pass. |
| PH44-PERF | 44-02 | Gate hiệu năng giảm latency >=40% trên replay chuẩn | ✓ SATISFIED | Assertion `optimized_avg_ms <= old_avg_ms * 0.60` trong replay regression test và command spot-check pass. |

Ghi chú traceability: `.planning/REQUIREMENTS.md` hiện không chứa các ID `PH44-*`, nên mapping được xác nhận theo `requirements:` trong plan 44-01/44-02 và artifacts phase 44.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `services/aureus-signal/engine/signals/structure.py` | 113, 182 | `new_signals = []` | ℹ️ Info | Đây là biến làm việc trong logic xử lý, có populate/return thực tế; không phải stub. |

### Human Verification Required

### 1. Shadow rollout production telemetry

**Test:** Chạy service ở `AUREUS_STRUCTURE_OPT_MODE=shadow` trên cửa sổ production-like theo symbol/time-window thật (theo 44-VALIDATION Manual-Only Verifications) và theo dõi log mismatch.
**Expected:** Mismatch = 0 ổn định trong cửa sổ quan sát trước khi promote `on`.
**Why human:** Cần dữ liệu thị trường live, hành vi real-time pipeline và observability thực tế; không thể xác minh đầy đủ bằng static analysis hoặc unit/replay test.

### Gaps Summary

Không phát hiện blocker implementation cho must-haves của phase 44 trong code/tests hiện có. Tuy nhiên còn 1 hạng mục bắt buộc cần xác nhận thủ công ở môi trường production-like (shadow telemetry window), vì vậy phase chưa thể kết luận `passed` theo gate rule, chỉ đạt `human_needed`.

---

_Verified: 2026-04-18T03:48:21Z_
_Verifier: Claude (gsd-verifier)_
