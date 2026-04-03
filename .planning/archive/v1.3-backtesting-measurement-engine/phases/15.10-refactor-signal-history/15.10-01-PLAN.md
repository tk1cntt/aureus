---
phase: "15.10"
plan: "01"
title: "Reconcile signal_history/log_signal Contract Drift Before Strong-Typed Refactor"
wave: 1
depends_on: [15.9-01]
files_modified:
  - .planning/phases/15.10-refactor-signal-history/15.10-CONTEXT.md
  - .planning/phases/15.10-refactor-signal-history/15.10-RESEARCH.md
  - .planning/phases/15.10-refactor-signal-history/15.10-VALIDATION.md
  - services/aureus-signal/engine/state.py
  - services/aureus-signal/engine/live_engine.py
  - services/aureus-signal/engine/backtest_engine.py
  - services/aureus-signal/signal_computer.py
  - services/aureus-signal/engine/state_snapshot.py
autonomous: true
requirements_addressed: [INTERNAL-CONTRACT-RECONCILIATION]
---

<objective>
Đồng bộ lại contract `log_signal` giữa `state.py` và mọi call-site runtime để loại bỏ drift hiện tại, tạo nền an toàn trước khi tiếp tục refactor Pydantic kiểu mạnh.
</objective>

<must_haves>
- Một signature thống nhất cho toàn bộ luồng ghi signal
- Backward compatibility cho record legacy (`tag`, `t`, `value`, `data`)
- Consumer/snapshot path không vỡ sau đồng bộ
- Verification rõ cho test + runtime smoke
</must_haves>

---

<task id="15.10-01-T1" title="Select and enforce canonical log_signal contract">
<read_first>
- services/aureus-signal/engine/state.py
- .planning/phases/15.10-refactor-signal-history/15.10-CONTEXT.md
</read_first>
<action>
1. Chốt signature canonical (metadata-aware hoặc adapter-layer tương đương).
2. Bảo toàn compatibility cho callers/records legacy.
3. Ghi rõ normalize rules cho mixed payloads.
</action>
<acceptance_criteria>
- Contract được mô tả rõ và áp dụng được tại state layer
- Không phát sinh lỗi do kwargs/signature mismatch
</acceptance_criteria>
</task>

<task id="15.10-01-T2" title="Reconcile all runtime call-sites to one contract">
<read_first>
- services/aureus-signal/engine/live_engine.py
- services/aureus-signal/engine/backtest_engine.py
- services/aureus-signal/signal_computer.py
</read_first>
<action>
1. Đồng bộ toàn bộ đường gọi `log_signal` về contract canonical.
2. Loại bỏ drift giữa metadata kwargs và legacy positional calls.
3. Đảm bảo payload shape nhất quán giữa live/backtest/precompute.
</action>
<acceptance_criteria>
- Không còn call-site lệch contract
- Runtime loop ghi `signal_history` ổn định
</acceptance_criteria>
</task>

<task id="15.10-01-T3" title="Validate consumers and snapshot restoration under reconciled contract">
<read_first>
- services/aureus-signal/engine/state_snapshot.py
- services/aureus-signal/engine/ai_validator.py
</read_first>
<action>
1. Kiểm tra normalize/restore path với legacy + new records.
2. Đảm bảo consumer narrative không lỗi khi field mở rộng có/không có.
3. Xác nhận không hồi quy ở tests contract normalization.
</action>
<acceptance_criteria>
- Tests contract/snapshot pass
- Không có regression rõ trong smoke runtime path
</acceptance_criteria>
</task>

---

<verification>
1. `Get-ChildItem ".planning/phases/15.10-refactor-signal-history/*"`
2. `node ".agent/get-shit-done/bin/gsd-tools.cjs" phase-plan-index "15.10"`
3. `pytest tests/test_decision_trace_schema.py tests/test_signal_contract_normalization.py tests/test_state_snapshot.py -q`
</verification>
