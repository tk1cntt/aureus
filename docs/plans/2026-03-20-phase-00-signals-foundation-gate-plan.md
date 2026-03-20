# Phase 00 — Signals Foundation Gate Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Hoàn thành gói foundation cho `signals contract cleanup` (Risk A-D) để giảm rủi ro runtime trước khi tiếp tục các phase tối ưu trong roadmap.

**Architecture:** Thực hiện một gate độc lập (Phase 00) tập trung vào contract consistency, FVG rollout an toàn bằng feature flag, hardening snapshot normalization, và guardrails cho state coupling. Không thay đổi logic trading cốt lõi; chỉ harden interface + wiring + test contract.

**Tech Stack:** Python, pytest, module `aureus-signal` (`engine/signals`, `engine/signal_factory.py`, `tests/*`).

## Current Status (2026-03-20 21:11 +07)
- [x] Task 2 — Contract Alignment (Risk A)
- [x] Task 3 — FVG Single Path + Feature-Flag Rollout (Risk B)
- [/] Task 1 — Baseline & Safety Snapshot (tracker/test done, commit step pending)
- [ ] Task 4 — Snapshot Contract Hardening (Risk C)
- [ ] Task 5 — State Coupling Guardrails (Risk D)
- [ ] Task 6 — Phase 00 Exit Gate & Handover

---

### Task 1: Baseline & Safety Snapshot

**Files:**
- Modify: `d:/Aureus/docs/plans/task.md`
- Verify: `d:/Aureus/.planning/ROADMAP.md`

**Step 1: Đánh dấu Phase 00 đang chạy trong tracker**
- Cập nhật `docs/plans/task.md` thêm row cho `Phase 00 / signals foundation gate`.

**Step 2: Chụp baseline test nhanh trước khi sửa**
- Run: `python -m pytest d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py -q`
- Expected: có baseline pass/fail rõ ràng để so sánh sau thay đổi.

**Step 3: Commit mốc baseline**
- Commit message gợi ý: `chore(signal): capture phase-00 baseline before contract cleanup`

---

### Task 2: Contract Alignment (Risk A)

**Files:**
- Modify: `d:/Aureus/services/aureus-signal/engine/signals/base.py`
- Modify: `d:/Aureus/services/aureus-signal/engine/signals/*.py`
- Test: `d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py`

**Step 1: Chuẩn hóa abstract contract ở `BaseSignal`**
- Đặt signature chuẩn runtime: `calculate(df, state_obj, **kwargs)`.
- Đồng bộ docstring contract với call-site thực tế.

**Step 2: Chuẩn hóa các signal có signature cứng**
- Thêm `**kwargs` hoặc đảm bảo không vỡ khi truyền `redis_client`, `symbol`, metadata runtime.

**Step 3: Chạy test contract sau chỉnh sửa**
- Run: `python -m pytest d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py -q`
- Expected: không có `TypeError` do mismatch signature.

**Step 4: Commit**
- Commit message: `refactor(signal): align BaseSignal runtime contract`

---

### Task 3: FVG Single Path + Feature-Flag Rollout (Risk B)

**Files:**
- Modify: `d:/Aureus/services/aureus-signal/engine/signal_factory.py`
- Modify: `d:/Aureus/services/aureus-signal/engine/signals/fvg.py`
- Keep: `d:/Aureus/services/aureus-signal/engine/signals/fvg_up.py`
- Keep: `d:/Aureus/services/aureus-signal/engine/signals/fvg_down.py`

**Step 1: Wiring FVG theo flag**
- Đăng ký key `fvg` chỉ khi `AUREUS_ENABLE_FVG_SIGNAL=1`.
- Mặc định OFF để rollout an toàn.

**Step 2: Harden guard trong `fvg.py`**
- Bổ sung kiểm tra state tối thiểu trước mutate/log.
- Không thay đổi business semantics detect/mitigation.

**Step 3: Test 2 mode (flag OFF/ON)**
- Run (OFF): `set AUREUS_ENABLE_FVG_SIGNAL=0 && python -m pytest d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py -q`
- Run (ON): `set AUREUS_ENABLE_FVG_SIGNAL=1 && python -m pytest d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py -q`
- Expected: OFF vẫn stable snapshot; ON có key `fvg` trong signal set.

**Step 4: Commit**
- Commit message: `feat(signal): add feature-flagged fvg registration`

---

### Task 4: Snapshot Contract Hardening (Risk C)

**Files:**
- Modify: `d:/Aureus/services/aureus-signal/engine/signal_factory.py`
- Modify: `d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py`

**Step 1: Chuẩn hóa fallback `fvg_state`**
- Ưu tiên `transient_signals["fvg_state"]` nếu có.
- Fallback `MISSING` + `source` metadata, không khóa vào reason legacy.

**Step 2: Cập nhật test contract**
- Assert theo contract ổn định (shape + semantic), không assert reason text cũ.

**Step 3: Chạy test liên quan normalization**
- Run: `python -m pytest d:/Aureus/services/aureus-signal/tests/test_signal_contract_normalization.py -q`
- Expected: pass cho cả đường fallback và transient.

**Step 4: Commit**
- Commit message: `test(signal): harden normalized snapshot contract`

---

### Task 5: State Coupling Guardrails (Risk D)

**Files:**
- Modify: `d:/Aureus/services/aureus-signal/engine/signals/structure.py`
- Modify: `d:/Aureus/services/aureus-signal/engine/signals/sweep.py`
- Modify: `d:/Aureus/services/aureus-signal/engine/signals/fvg.py`
- Test: `d:/Aureus/services/aureus-signal/tests/*signal*.py`

**Step 1: Thêm guard cho minimal/dummy state**
- `hasattr`/fallback default ở các điểm crash-prone.

**Step 2: Bổ sung edge-case tests cho minimal state shape**
- Confirm guardrails không phá luồng chính.

**Step 3: Chạy subset test theo scope**
- Run: `python -m pytest d:/Aureus/services/aureus-signal/tests -k "fvg or signal_contract or sweep or structure" -q`
- Expected: pass, không crash do thiếu field state.

**Step 4: Commit**
- Commit message: `fix(signal): add state guardrails for minimal runtime shape`

---

### Task 6: Phase 00 Exit Gate & Handover

**Files:**
- Modify: `d:/Aureus/docs/plans/task.md`
- Modify: `d:/Aureus/.planning/ROADMAP.md`
- Optional: `d:/Aureus/docs/plans/2026-03-20-phase-00-signals-foundation-gate-plan.md` (append results)

**Step 1: Chạy regression cần thiết**
- Run: `python -m pytest d:/Aureus/services/aureus-signal/tests/test_live_engine_gates.py d:/Aureus/services/aureus-signal/tests/test_decision_trace_schema.py -q`
- Expected: pass, không hồi quy gate/trace.

**Step 2: Ghi evidence + trạng thái hoàn thành**
- Cập nhật tracker là `completed` khi tất cả gate pass.

**Step 3: Quyết định tiến sang roadmap**
- Chỉ chuyển sang Phase 02 khi Phase 00 hoàn thành.

**Step 4: Commit cuối phase**
- Commit message: `chore(signal): close phase-00 foundation gate`

---

## Ready-to-Run Sequence
1. Chạy plan này trước (`Phase 00`).
2. Khi pass đầy đủ gate, chuyển sang plan roadmap continuation (`Phase 02-09`).
3. Nếu có incident, rollback nhanh bằng `AUREUS_ENABLE_FVG_SIGNAL=0`.
