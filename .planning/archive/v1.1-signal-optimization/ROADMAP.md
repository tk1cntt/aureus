# Roadmap: Aureus v1.1 Signal Optimization

## Overview

Roadmap này chuẩn hóa 9 phase tối ưu tín hiệu theo hướng accuracy-first cho `aureus-signal`, với mỗi phase tập trung 1 signal và phải đạt test gate (unit + integration + coverage >= 80%) trước khi đóng phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3...): Planned milestone work
- Decimal phases (2.1, 2.2...): Urgent insertions (INSERTED)

- [x] **Phase 1: Signal ATR Optimization** - Hoàn tất tối ưu `atr` và lưu đầy đủ evidence phase.
- [x] **Phase 2: Signal EMA Optimization** - Hoàn tất tối ưu `ema` và đóng toàn bộ gate verification phase.
- [x] **Phase 3: Signal FVG Optimization** - Tối ưu `fvg` với rollout-safe và snapshot contract ổn định. (completed 2026-03-20)
- [x] **Phase 4: Signal Pivots Optimization** - Tối ưu `pivots` bằng defensive guards giữ contract tương thích hoàn hảo. (completed 2026-03-21)
- [x] **Phase 5: Signal Session Optimization** - Tối ưu `session` với test/coverage gate chuẩn. (completed 2026-03-21)
- [x] **Phase 6: Signal Sweep Optimization** - Tối ưu `sweep` và kiểm soát side effects. (completed 2026-03-21)
- [x] **Phase 7: Signal Trend Optimization** - Tối ưu `trend` với tiêu chí ổn định tín hiệu. (completed 2026-03-21)
- [x] **Phase 8: Signal Volume SMA Optimization** - Tối ưu `volume_sma` theo quyết định từ CONTEXT. (completed 2026-03-21)
- [x] **Phase 9: Signal Structure Optimization** - Tối ưu `structure` và hoàn tất traceability v1.1. (completed 2026-03-21)
- [ ] **Phase 10: Phân tích và tối ưu sweep_targets trong structure.py** - Optimize sweep targets in structure.py.
- [x] **Phase 11: System GC - Daily Signal Recalculation** - Tự động dọn RAM 5AM GMT+7 mỗi ngày bằng 1500 nến. (completed 2026-03-22)
- [ ] **Phase 12: Handle Multi-OB Mitigation Events** - Chống mất dữ liệu khi nhiều OB bị mitigated trong cùng một candle và giữ backward compatibility event contract.
- [ ] **Phase 13: Sweep Event Improvement** - Chuẩn hóa state/event semantics cho sweep theo thế đánh và loại bỏ `OB_STATE_CHANGE`.

## Phase Details

### Phase 1: Signal ATR Optimization
**Goal**: Tối ưu tín hiệu `atr` và hoàn tất phase evidence.
**Depends on**: Nothing (first phase)
**Requirements**: [SIG-01, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. Tín hiệu `atr` giữ intent giao dịch và event semantics.
  2. Unit + integration tests cho scope phase pass.
  3. Evidence phase đầy đủ trong thư mục phase.
**Plans**: 1 plan

Plans:
- [x] 01-01: Hoàn tất tối ưu ATR và phase evidence (`RESEARCH`, `PLAN`, `VALIDATION`, `SUMMARY`, `UAT`).

### Phase 2: Signal EMA Optimization
**Goal**: Tối ưu tín hiệu `ema` theo artifacts đã lập kế hoạch.
**Depends on**: Phase 1
**Requirements**: [SIG-02, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. Tín hiệu `ema` hoạt động đúng contract runtime.
  2. Unit + integration tests scope EMA pass.
  3. Coverage phase >= 80% với evidence rõ ràng.
**Plans**: 1 plan

Plans:
- [x] 02-01: Execute EMA plan đã định nghĩa trong `02-01-PLAN.md`.

### Phase 3: Signal FVG Optimization
**Goal**: Tối ưu `fvg` với rollout-safe và snapshot contract ổn định.
**Depends on**: Phase 2
**Requirements**: [SIG-03, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `fvg` chạy ổn định theo contract mới.
  2. Không phát sinh contamination/import side effect.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [ ] 03-01: Plan sẽ được tạo sau `gsd-discuss-phase 3`.

### Phase 4: Signal Pivots Optimization
**Goal**: Tối ưu `pivots` và giữ tương thích hệ thống.
**Depends on**: Phase 3
**Requirements**: [SIG-04, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `pivots` cho kết quả ổn định theo yêu cầu.
  2. Unit + integration tests pass.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [ ] 04-01: Tối ưu và verify tín hiệu `pivots`.

### Phase 5: Signal Session Optimization
**Goal**: Tối ưu `session` với gate kiểm thử chuẩn.
**Depends on**: Phase 4
**Requirements**: [SIG-05, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `session` phản ánh logic thị trường đúng intent.
  2. Unit + integration tests pass.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [x] 05-01: Tối ưu và verify tín hiệu `session`.

### Phase 6: Signal Sweep Optimization
**Goal**: Tối ưu `sweep` với kiểm soát an toàn trạng thái.
**Depends on**: Phase 5
**Requirements**: [SIG-06, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `sweep` hoạt động ổn định trong flow chính.
  2. Unit + integration tests pass.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [x] 06-01: Tối ưu và verify tín hiệu `sweep`.

### Phase 7: Signal Trend Optimization
**Goal**: Tối ưu `trend` và đảm bảo tương thích contract.
**Depends on**: Phase 6
**Requirements**: [SIG-07, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `trend` duy trì hành vi mong đợi.
  2. Unit + integration tests pass.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [x] 07-01: Tối ưu và verify tín hiệu `trend`.

### Phase 8: Signal Volume SMA Optimization
**Goal**: Tối ưu `volume_sma` theo chuẩn phase execution.
**Depends on**: Phase 7
**Requirements**: [SIG-08, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `volume_sma` hoạt động đúng intent.
  2. Unit + integration tests pass.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [ ] 08-01: Tối ưu và verify tín hiệu `volume_sma`.

### Phase 9: Signal Structure Optimization
**Goal**: Tối ưu `structure` và chốt milestone v1.1.
**Depends on**: Phase 8
**Requirements**: [SIG-09, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `structure` ổn định trong pipeline signal.
  2. Unit + integration tests pass.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [x] 09-01: Tối ưu và verify tín hiệu `structure`.

### Phase 10: Phân tích và tối ưu sweep_targets trong structure.py
**Goal**: Phân tích logic vạch sweep_targets đa cực, tìm hướng tối ưu hiệu năng mà không làm rách contract O1.
**Depends on**: Phase 9
**Requirements**: [SIG-10, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `sweep_targets` hoạt động ổn định và chính xác theo logic MQL5.
  2. Đo đạc được Performance Baseline và tối ưu O(1) nếu có thể.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [ ] 10-01: Plan sẽ được tạo sau `gsd-discuss-phase 10` hoặc `gsd-plan-phase 10`.

### Phase 11: System GC - Daily Signal Recalculation
**Goal**: Xây dựng cơ chế dọn rác System RAM bằng cách tự động gọi `recalculate_all_signals` lúc 5h sáng (0:00 UTC).
**Depends on**: Phase 10
**Requirements**: [SIG-11, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. Engine tự động trigger loop check đúng 0:00 UTC mỗi ngày.
  2. Dữ liệu RAM được renew thay vì phình to vô hạn.
  3. Coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [x] 11-01: Tạo Background Task hẹn giờ Reset trong Live Engine.

### Phase 12: Handle Multi-OB Mitigation Events
**Goal**: Chuẩn hóa hành vi mitigation khi nhiều OB chạm cùng candle theo semantics deterministic `last-event-wins`, giữ nguyên legacy contract đang chạy production.
**Depends on**: Phase 11
**Requirements**: [SIG-12, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. Khi nhiều OB cùng bị mitigation trong một candle, `ob_bull_mitigated`/`ob_bear_mitigated` luôn chứa event cuối cùng một cách deterministic.
  2. Không thêm schema aggregate key mới; downstream hiện tại vẫn hoạt động bằng legacy event keys.
  3. Unit + integration tests liên quan `structure`/`event_filter` pass và coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [x] 12-01: Enforce deterministic last-event-wins semantics for OB mitigation events.

### Phase 13: Sweep Event Improvement
**Goal**: Chuẩn hóa lại state machine và event contract của `sweep` theo mô hình mỗi trạng thái là một thế đánh riêng, loại bỏ hoàn toàn `OB_STATE_CHANGE`.
**Depends on**: Phase 12
**Requirements**: [SIG-13, TST-01, TST-02, TST-03, TST-04, VAL-01, VAL-02]
**Success Criteria** (what must be TRUE):
  1. `sweep` sử dụng bộ trạng thái chuẩn (`PENDING`, `TOUCHED`, `SWEEP`, `BROKEN_PENDING`, `STOP_HUNT`, `DEAD`) với transition deterministic.
  2. Event phát ra theo format `{STATUS}_EVENT`, không còn `OB_STATE_CHANGE`.
  3. Unit + integration tests cho `sweep` pass và coverage phase >= 80%.
**Plans**: 1 plan

Plans:
- [ ] 13-01: Plan sẽ được tạo sau `gsd-discuss-phase 13` hoặc `gsd-plan-phase 13`.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Signal ATR Optimization | v1.1 | 1/1 | Complete | 2026-03-19 |
| 2. Signal EMA Optimization | v1.1 | 1/1 | Complete | 2026-03-20 |
| 3. Signal FVG Optimization | v1.1 | 1/1 | Complete | 2026-03-20 |
| 4. Signal Pivots Optimization | v1.1 | 2/2 | Complete | 2026-03-21 |
| 5. Signal Session Optimization | v1.1 | 0/1 | Complete | 2026-03-21 |
| 6. Signal Sweep Optimization | v1.1 | 0/1 | Complete | 2026-03-21 |
| 7. Signal Trend Optimization | v1.1 | 1/1 | Complete | 2026-03-21 |
| 8. Signal Volume SMA Optimization | v1.1 | 1/1 | Complete | 2026-03-21 |
| 9. Signal Structure Optimization | v1.1 | 1/1 | Complete | 2026-03-21 |
| 10. Phân tích và tối ưu sweep_targets trong structure.py | v1.1 | 0/1 | Not started | - |
| 11. System GC - Daily Signal Recalculation | v1.1 | 1/1 | Complete | 2026-03-22 |
| 12. Handle Multi-OB Mitigation Events | v1.1 | 0/1 | Not started | - |
| 13. Sweep Event Improvement | v1.1 | 0/1 | Not started | - |
