---
phase: 38
slug: fix-db-writer-order-payload-parsing-for-wrapped-data-to-unblock-trade-journal-fk
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | services/aureus-db-writer/ (existing) |
| **Quick run command** | `pytest services/aureus-db-writer/tests/ -x -q` |
| **Full suite command** | `pytest services/aureus-db-writer/tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** `pytest services/aureus-db-writer/tests/test_order_buffer.py -x`
- **After every plan wave:** `pytest services/aureus-db-writer/tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01 | TBA | 1 | D-01/D-02 | — | Wrapped payload unwrapped before processing | unit | `pytest tests/test_order_buffer.py::TestWrappedPayload -x` | ❌ W0 | ⬜ pending |
| 38-02 | TBA | 1 | D-04/D-05 | — | Status from order data, not envelope type | unit | `pytest tests/test_order_buffer.py::TestStatusFromData -x` | ❌ W0 | ⬜ pending |
| 38-03 | TBA | 1 | D-06/D-08 | — | Missing timestamp → reject with ACK | unit | `pytest tests/test_order_buffer.py::TestMissingTimestamp -x` | ❌ W0 | ⬜ pending |
| 38-04 | TBA | 1 | D-09/D-10 | — | Invalid event → ACK + skip, no retry | unit | `pytest tests/test_order_buffer.py::TestInvalidEventAck -x` | ❌ W0 | ⬜ pending |
| 38-05 | TBA | 1 | D-11 | — | payload JSONB stores canonical data only | unit | `pytest tests/test_order_buffer.py::TestCanonicalPayload -x` | ❌ W0 | ⬜ pending |
| 38-fix | TBA | 1 | — | — | `ack_skip_msg_ids` replaced with `rejected_msg_ids` | regression | Existing order buffer tests pass | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_order_buffer.py` — wrapped payload test class (D-01/D-02)
- [ ] New test class: `TestWrappedPayloadUnwrap` — verifies `data` field is unwrapped before field access
- [ ] New test class: `TestStatusFromData` — verifies status comes from inner data, not envelope type
- [ ] New test class: `TestMissingTimestamp` — verifies reject + ACK for missing timestamp
- [ ] New test class: `TestInvalidEventAck` — verifies invalid events are ACK'd and skipped (not retried)
- [ ] New test class: `TestCanonicalPayload` — verifies payload JSONB stores only normalized data

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FK trade journal records created correctly | D-01/D-02 | Requires full pipeline | Run producer + DB writer, verify trade journal FK resolves |
| No silent skip of valid order events | Bug fix | Requires production-like data | Send real order events through Redis, verify all written to DB |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
