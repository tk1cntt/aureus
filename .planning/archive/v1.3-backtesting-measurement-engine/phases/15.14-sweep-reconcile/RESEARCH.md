# Phase 15.14: Suspicious sweep event reconciliation — Research

## Objective
Đối ứng từng điểm đáng ngờ trong dữ liệu runtime với hành vi code thực tế, nhằm xác định chính xác chỗ cần sửa để `triggered_sweep` không bị thiếu/nuốt tín hiệu.

## Suspicious Points Checklist (Need Confirmation)
1. [ ] **Time paradox**: có bản ghi `mitigated=true` nhưng `t_mitigation > c_t` tại thời điểm sweep evaluate.
2. [ ] **Gate mismatch**: event bị skip vì `mitigation_age <= 0` dù `_just_swept=True` cùng tick.
3. [ ] **Conflicting flags**: trạng thái chuyển `TOUCHED/BROKEN_PENDING/SWEEP` nhưng emitted value không trùng kỳ vọng.
4. [ ] **Duplicate suppression false-positive**: `already_swept` chặn event hợp lệ giữa nhiều OB cùng giá.
5. [ ] **Execution-order coupling**: thứ tự chạy `StructureSignal` ↔ `SweepSignal` tạo khác biệt hành vi theo engine loop.

## Source Code Reconciliation

### A) `services/aureus-signal/engine/signals/sweep.py`
- `_update_ob_states` set `_just_swept=True` cho nhiều trạng thái (`TOUCHED`, `SWEEP`, `BROKEN_PENDING`, `STOP_HUNT`, `CLEAN_BREAKOUT`).
- `calculate` chỉ emit khi `ob.pop("_just_swept", False)` → event phụ thuộc hoàn toàn vào flag tạm.
- Khi `mitigated=True`, gate bắt buộc `0 < mitigation_age <= 300`; nếu không thoả sẽ `continue` và mất event.
- `already_swept` dedupe theo `(same tick, same status_tag, same target_price)`; chưa có identity theo OB (`t_start`/`source_t`).

### B) `services/aureus-signal/engine/signals/structure.py`
- `_verify_mitigations` scan lịch sử `df[df['t'] > t_breakout]` để set `ob['mitigated']=True` và `ob['t_mitigation']=c_t`.
- Mitigation có thể được set ở candle trước, nhưng sweep emit được evaluate ở candle hiện tại với age gate 300s.
- Export `ob_state` hiện đưa `status/mitigated/t_mitigation` vào `transient_signals`, hữu ích để đối soát runtime.

## Findings (Current Hypothesis)
1. **Không phải `_just_swept` tự nó gây mất signal**, nhưng đây là điểm choke duy nhất nên rất nhạy với thứ tự cập nhật.
2. **Nguyên nhân thiếu signal khả dĩ nhất** là gate `mitigated` trong `sweep.calculate` loại bỏ event hợp lệ khi timing không đồng bộ.
3. `already_swept` hiện **thiếu khóa theo OB**, có nguy cơ chặn nhầm trong setup nhiều OB có cùng mức giá.

## Pre-Fix Verification Matrix
- Thu log runtime gồm: `c_t`, `status`, `_just_swept` trước/ sau pop, `mitigated`, `t_mitigation`, `mitigation_age`, `source_t`.
- So sánh sequence event giữa `signal_history` và `transient_signals['ob_state']` theo từng tick.
- Xác minh ít nhất 3 case:
  - vừa mitigation xong và sweep cùng vùng trong 1-2 candle,
  - nhiều OB cùng side/cùng giá,
  - BROKEN_PENDING → STOP_HUNT reclaim.
