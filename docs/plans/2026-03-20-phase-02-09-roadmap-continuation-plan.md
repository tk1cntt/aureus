# Phase 02-09 — Roadmap Continuation Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Tiếp tục triển khai `.planning/ROADMAP.md` từ Phase 02 đến Phase 09 sau khi Foundation Gate (Phase 00) đã hoàn tất.

**Architecture:** Giữ nguyên mô hình roadmap 1 signal / phase. Mỗi phase đi theo vòng lặp cố định: research → plan → implement → verify → document. Dependency cứng: không mở Phase 02 nếu `Phase 00` chưa đóng thành công.

**Tech Stack:** Python, pytest, coverage, roadmap artifacts trong `.planning/phases/*`.

---

## Dependency Gate (Bắt buộc trước khi bắt đầu)

### Task 0: Confirm Foundation Gate Completed

**Files:**
- Verify: `d:/Aureus/docs/plans/2026-03-20-phase-00-signals-foundation-gate-plan.md`
- Verify: `d:/Aureus/docs/plans/task.md`
- Verify: `d:/Aureus/.planning/ROADMAP.md`

**Step 1: Kiểm tra trạng thái Phase 00**
- Xác nhận `completed` và có evidence test pass.

**Step 2: Nếu chưa completed, dừng plan này**
- Không triển khai roadmap tiếp để tránh lock-in rủi ro contract/state.

---

## Phase Loop Template (áp dụng cho từng phase 02→09)

### Task A: Research Phase Scope
**Files:**
- Create: `d:/Aureus/.planning/phases/<NN-signal>/RESEARCH.md`
- Verify: `d:/Aureus/.planning/REQUIREMENTS.md`

**Steps:**
1. Ghi mục tiêu signal của phase.
2. Liệt kê file code + test cần chạm.
3. Nêu rủi ro kỹ thuật và cách kiểm soát.

### Task B: Plan Implementation
**Files:**
- Create: `d:/Aureus/.planning/phases/<NN-signal>/PLAN.md`

**Steps:**
1. Chia task nhỏ 2-5 phút theo TDD.
2. Chốt command verify + coverage scope.

### Task C: Implement with Tests
**Files:**
- Modify: signal module tương ứng trong `d:/Aureus/services/aureus-signal/engine/signals/`
- Test: file unit/integration tương ứng trong `d:/Aureus/services/aureus-signal/tests/`

**Steps:**
1. Viết/điều chỉnh test fail trước.
2. Viết code tối thiểu để pass.
3. Refactor nhỏ nếu cần, giữ behavior ổn định.

### Task D: Validate & Document
**Files:**
- Create: `d:/Aureus/.planning/phases/<NN-signal>/VALIDATION.md`
- Create: `d:/Aureus/.planning/phases/<NN-signal>/SUMMARY.md`
- Modify: `d:/Aureus/.planning/ROADMAP.md`

**Steps:**
1. Chạy test unit + integration.
2. Chạy coverage cho scope phase (>=80%).
3. Cập nhật evidence command + output.
4. Đánh dấu phase done trong roadmap.

---

## Phase-by-Phase Execution Queue

### Task 1: Phase 02 — `ema`
- Folder: `d:/Aureus/.planning/phases/02-signal-ema/`
- Gate: pass all + coverage >= 80% trước khi sang Phase 03.

### Task 2: Phase 03 — `fvg`
- Folder: `d:/Aureus/.planning/phases/03-signal-fvg/`
- Lưu ý: tôn trọng feature-flag behavior đã thiết lập ở Phase 00.

### Task 3: Phase 04 — `pivots`
- Folder: `d:/Aureus/.planning/phases/04-signal-pivots/`

### Task 4: Phase 05 — `session`
- Folder: `d:/Aureus/.planning/phases/05-signal-session/`

### Task 5: Phase 06 — `sweep`
- Folder: `d:/Aureus/.planning/phases/06-signal-sweep/`

### Task 6: Phase 07 — `trend`
- Folder: `d:/Aureus/.planning/phases/07-signal-trend/`

### Task 7: Phase 08 — `volume_sma`
- Folder: `d:/Aureus/.planning/phases/08-signal-volume-sma/`

### Task 8: Phase 09 — `structure`
- Folder: `d:/Aureus/.planning/phases/09-signal-structure/`

---

## Standard Verification Commands (per phase)

1. Unit/integration focused:
   - `python -m pytest d:/Aureus/services/aureus-signal/tests -k "<signal_name>" -q`
2. Broader regression for signal area:
   - `python -m pytest d:/Aureus/services/aureus-signal/tests -k "signal or live_engine" -q`
3. Coverage gate (scope phase):
   - `python -m pytest d:/Aureus/services/aureus-signal/tests --cov=d:/Aureus/services/aureus-signal/engine --cov-report=term-missing`

Expected: phase scope đạt coverage >= 80% và không phá regression của phase đã đóng.

---

## Execution Order Recommendation

1. Chạy `2026-03-20-phase-00-signals-foundation-gate-plan.md` trước.
2. Sau khi Phase 00 completed, chạy plan này cho Phase 02→09.
3. Nếu có incident ở bất kỳ phase nào, dừng queue và xử lý triệt để trước khi sang phase tiếp theo.
