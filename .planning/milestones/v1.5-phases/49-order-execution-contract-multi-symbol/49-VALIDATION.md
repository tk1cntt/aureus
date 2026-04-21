---
phase: 49
slug: order-execution-contract-multi-symbol
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-20
---

# Phase 49 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `services/aureus-gateway/tests/pytest.ini` (services khác dùng pytest defaults) |
| **Quick run command** | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py -q -x` |
| **Full suite command** | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests D:/Aureus/services/aureus-nautilus-bridge/tests -q` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py -q`
- **After every plan wave:** Run `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests D:/Aureus/services/aureus-nautilus-bridge/tests -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 49-01-01 | 01 | 1 | ORDER-01 | T-49-01 | Reject malformed/incomplete ORDER_OPEN with machine-readable reason code | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client.py -q -x` | ✅ | ⬜ pending |
| 49-01-02 | 01 | 1 | ORDER-02 | T-49-02 | Preserve qty semantics and contingent order generation path | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_risk_controls.py::test_valid_order_generates_entry_plus_sl_tp_contingents -q` | ✅ | ⬜ pending |
| 49-01-03 | 01 | 1 | ORDER-03 | T-49-03 | Keep mapping compatibility for quantity/qty and type/event_time | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-bridge/tests/test_mapper.py -q -x` | ✅ | ⬜ pending |
| 49-02-01 | 02 | 1 | PH45-05 | T-49-04 | Duplicate trace_id is ignored deterministically | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_risk_controls.py::test_duplicate_trace_id_is_ignored -q` | ✅ | ⬜ pending |
| 49-02-02 | 02 | 1 | PH45-06 | T-49-05 | Multi-symbol polling enforces stream/payload symbol consistency | unit/integration-lite | `python3 -m pytest D:/Aureus/services/aureus-nautilus-node/tests/test_execution_client_policy.py -q -x` | ✅ | ⬜ pending |
| 49-02-03 | 02 | 1 | PH45-07 | T-49-06 | Strategy lineage/idempotency retained through bridge lifecycle | unit | `python3 -m pytest D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_idempotency.py D:/Aureus/services/aureus-nautilus-bridge/tests/test_bridge_lineage.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `D:/Aureus/services/aureus-nautilus-node/tests/test_execution_multi_symbol_contract.py` — stubs cho qty/quantity compatibility + fallback XAUUSD removal
- [ ] `D:/Aureus/services/aureus-nautilus-bridge/tests/test_order_payload_qty_alias.py` — mapper compatibility test cho volume naming

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Runtime consume nhiều symbol thật qua Redis stream | PH45-06 | Môi trường unit test dùng mocked redis, không cover hạ tầng stream thật | Restart services theo RUN_SERVICES.md, publish ORDER_OPEN cho >=2 symbol, kiểm tra không còn hardcode/fallback XAUUSD và không reject sai |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 180s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
