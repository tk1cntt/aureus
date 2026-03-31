---
phase: "15.14"
plan: "01"
title: "Reconcile suspicious sweep events and mitigation timing"
wave: 1
depends_on: []
files_modified:
  - .planning/phases/15.14-sweep-reconcile/15.14-CONTEXT.md
  - .planning/phases/15.14-sweep-reconcile/15.14-RESEARCH.md
  - services/aureus-signal/engine/signals/sweep.py
  - services/aureus-signal/engine/signals/structure.py
  - services/aureus-signal/tests/test_sweep_o1.py
autonomous: true
requirements_addressed: [SWEEP-EVENT-RECONCILIATION]
---

<objective>
Loại bỏ bất nhất sweep event bằng cách xác nhận điểm đáng ngờ trên dữ liệu thật, sau đó sửa logic emission/gating để `triggered_sweep` trả về đúng tín hiệu hợp lệ.
</objective>

<must_haves>
- Có checklist xác nhận rõ từng suspicious point trước khi sửa logic
- Không làm mất backward compatibility của payload `tag: sweep`, `value`, `data.price_swept`
- Mỗi transition hợp lệ phải phát tối đa 1 event/tick theo parity cũ
- Bổ sung test regression cho case mitigation timing + multi-OB dedupe
</must_haves>

---

<task id="15.14-01-T1" title="Instrument and validate suspicious runtime conditions">
<read_first>
- services/aureus-signal/engine/signals/sweep.py
- services/aureus-signal/engine/signals/structure.py
- .planning/phases/15.14-sweep-reconcile/15.14-RESEARCH.md
</read_first>
<action>
1. Thêm logging/trace tạm thời cho `_just_swept`, `status`, `mitigated`, `t_mitigation`, `mitigation_age`, `source_t`.
2. Reproduce 3 kịch bản nghi ngờ để chốt pass/fail của checklist.
3. Kết luận root-cause bằng bằng chứng runtime, không suy đoán.
</action>
<acceptance_criteria>
- Mỗi suspicious point có trạng thái confirmed/rejected kèm bằng chứng log
- Có mapping rõ from log -> branch code tương ứng
</acceptance_criteria>
</task>

<task id="15.14-01-T2" title="Refine sweep duplicate keying and preserve trap spam">
<read_first>
- services/aureus-signal/engine/signals/sweep.py
</read_first>
<action>
1. Gỡ bỏ dedupe dựa trên `rec_t != c_t`, giữ lại spam event Sweep trong vòng 300s of mitigation (thể hiện trap/giằng co).
2. Sửa điều kiện `already_swept` bắt buộc so sánh định danh OB (`source_t` và `ob_type`), để tránh ghi đè sweep nếu nhỡ có 2 OB cùng giá nhưng khác khung thời gian.
3. Vẫn giữ invariant: 1 tick phát tối đa 1 sự kiện sweep.
</action>
<acceptance_criteria>
- `already_swept` key sử dụng data.source_t và data.ob_type
- Các sweep trigger được tiếp tục nã liên thanh (spam) nếu giá nán lại mốc dưới/trên vùng OB trong 300s sau khi mitigated.
- Không làm thay đổi shape payload hiện có
</acceptance_criteria>
</task>

<task id="15.14-01-T3" title="Add regression tests for mitigation timing and trap spam">
<read_first>
- services/aureus-signal/tests/test_sweep_o1.py
</read_first>
<action>
1. Thêm case trap spam: tạo 5 nến liên tiếp dao động quanh edge của OB -> đảm bảo emit đủ 5 event Sweep liên tục (chặn dedupe bậy bạ).
2. Thêm case multi-OB cùng giá để kiểm tra dedupe theo OB identity.
3. Thêm case BROKEN_PENDING -> STOP_HUNT đảm bảo status_tag đúng.
</action>
<acceptance_criteria>
- Test trap spam phải pass, verify count đúng bằng số nến quét trong zone
- Không regression các test sweep hiện hữu
</acceptance_criteria>
</task>

---

<verification>
1. `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.14"`
2. `pytest services/aureus-signal/tests/test_sweep_o1.py -q`
3. `pytest services/aureus-signal/tests/test_sweep_integration_live_engine.py -q`
</verification>
