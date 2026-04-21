---
phase: 47
slug: verification-backfill-v1-5
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-20
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + markdown artifact validation |
| **Config file** | `services/*/tests/pytest.ini` (service-specific) |
| **Quick run command** | `pytest -q -x <targeted_test_file>` |
| **Full suite command** | `pytest tests/ -q -x` (service-scoped for impacted service) |
| **Estimated runtime** | ~30-180 seconds (targeted), ~5-12 minutes (full service suite) |

---

## Sampling Rate

- **After every task commit:** Run requirement-targeted command(s) cho REQ-ID vừa backfill evidence
- **After every plan wave:** Run service-level full suite cho các service bị ảnh hưởng bởi wave
- **Before `/gsd-verify-work`:** Tất cả command đã khai báo trong verification table phải green hoặc được đánh dấu `human_needed` có lý do
- **Max feedback latency:** 300 seconds cho quick checks

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | NOTIF-01 | T-47-01 | Verification chứng minh publish signal events qua Redis pub/sub bằng artifact+wiring+test | unit/integration | `pytest services/aureus-signal/tests/test_signal_event_publisher.py -q -x` | ✅ | ⬜ pending |
| 47-01-02 | 01 | 1 | STRAT-01..04 | T-47-02 | Verification chứng minh strategy contract entry_type/SLTP/size/magic theo requirement-level evidence | unit | `pytest services/aureus-signal/tests/test_strategy_contract_v2.py -q -x` | ✅ | ⬜ pending |
| 47-01-03 | 01 | 1 | ORDER-04..06 | T-47-03 | Verification chứng minh EA command execution + ACK/NACK + order events path | unit + manual gate | `pytest services/aureus-gateway/tests/test_order_events.py -q -x` | ✅ | ⬜ pending |
| 47-01-04 | 01 | 1 | ORDER-07 | T-47-04 | Verification chứng minh idempotency duplicate protection | unit | `pytest services/aureus-trader/tests/test_idempotency.py -q -x` | ✅ | ⬜ pending |
| 47-01-05 | 01 | 2 | TRADE-03..04 | T-47-05 | Verification chứng minh history push + poll reconciliation fallback | integration | `pytest services/aureus-db-writer/tests/test_reconciliation.py -q -x` | ✅ | ⬜ pending |
| 47-01-06 | 01 | 3 | Traceability sync | T-47-06 | REQUIREMENTS traceability updated, orphan IDs phase 47 có evidence refs | artifact | `python3 -m pytest services/aureus-signal/tests/test_signal_event_publisher.py -q` (smoke consistency) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Tạo `26-VERIFICATION.md` theo format verifier chuẩn
- [ ] Tạo `28-VERIFICATION.md` theo format verifier chuẩn
- [ ] Tạo `29-VERIFICATION.md` theo format verifier chuẩn
- [ ] Tạo `31-VERIFICATION.md` theo format verifier chuẩn
- [ ] Tạo `32-VERIFICATION.md` theo format verifier chuẩn
- [ ] Tạo `33-VERIFICATION.md` theo format verifier chuẩn
- [ ] Chuẩn hóa bảng requirement-level evidence cho toàn bộ REQ-ID của phase 47

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MT5 EA execute OrderSend end-to-end với terminal thật | ORDER-04 | Cần MT5 terminal + broker/session live; không thể auto-verify hoàn toàn trong môi trường docs-only | Chạy EA trên terminal test, publish command OPEN_ORDER qua Redis, đối chiếu log/ticket/ORDER_OPENED event |
| MT5 close/history push timing thực tế | TRADE-03 | Độ trễ và event timing phụ thuộc runtime MT5/Gateway live | Mở/đóng lệnh thử, xác nhận ORDER_CLOSED + TRADE_HISTORY path theo timestamps thực tế |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 300s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending