---
quick_id: 260507-vmj
status: passed
verified_at: 2026-05-07
report_only: true
---

# Quick Task 260507-vmj Verification

## Verdict

PASS.

## Must-Haves

### Analyze ACK_LOST_DUPLICATE_RECOVERY incident from trader logs in detail

PASS.

Report reconstructs timeline for `ord-4fd96f27887e`:

```text
15:21:01.346 Published attempt=1
15:21:06.348 ACK timeout attempt=1
15:21:07.353 Published attempt=2
15:21:12.354 ACK timeout attempt=2
15:21:12.963 Unmatched ACK
15:21:14.118 Unmatched ORDER_OPENED
15:21:14.120 Unmatched NACK
15:21:14.355 Published attempt=3
15:21:14.462 Matched NACK
15:21:14.462 RECONCILE_NEEDED class=ACK_LOST_DUPLICATE_RECOVERY
```

### Identify likely execution sequence and root cause without changing code

PASS.

Root cause identified from `dispatcher.py` + `AureusProvider_v2.mq5`:

- Dispatcher stores one pending future per `cmd_id`.
- `_wait_for_response()` removes future on timeout.
- Late ACK/ORDER_OPENED cannot be matched after timeout cleanup.
- Retry sends same `cmd_id`.
- Provider sees recorded duplicate and returns `NACK DUPLICATE`.
- Dispatcher classifies duplicate-after-timeout as `ACK_LOST_DUPLICATE_RECOVERY` and emits `RECONCILE_NEEDED`.

No source files modified.

### State whether INVALID_STOPS retcode 10016 recurred in observed window

PASS.

Findings distinguish two behaviors:

1. Object-shaped `sl` guard worked:

```text
Error processing event: sl must be numeric before MT5 dispatch
```

2. A separate numeric/geometry `INVALID_STOPS` happened for another order:

```text
Order rejected: ord-9d53998fd420 (ORDER_FAILED: INVALID_STOPS)
```

No evidence ties that to `ord-4fd96f27887e` or `ACK_LOST_DUPLICATE_RECOVERY`.

## Evidence Commands

```text
npx gitnexus query "ACK_LOST_DUPLICATE_RECOVERY dispatcher retry ACK timeout order opened NACK" --repo Aureus
```

```text
wsl -d Aureus -e bash -lc "docker logs --since 30m aureus-trader-dev 2>&1 | sed -n '/ord-4fd96f27887e/,+90p'"
```

```text
wsl -d Aureus -e bash -lc "docker logs --since 30m aureus-trader-dev 2>&1 | sed -n '/Unmatched event type=ACK cmd_id=ord-4fd96f27887e/,+40p'"
```

```text
wsl -d Aureus -e bash -lc "docker logs --since 30m aureus-trader-dev 2>&1 | sed -n '/Published order ord-4fd96f27887e lane=BTCUSD:608000:SELL attempt=3/,+35p'"
```

```text
wsl -d Aureus -e bash -lc "docker logs --since 30m aureus-trader-dev 2>&1 | grep -E 'INVALID_STOPS|retcode=10016|retcode.:10016|10016' || true"
```

## Scope Check

Changed docs/artifacts only:

- `.planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-PLAN.md`
- `.planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-SUMMARY.md`
- `.planning/quick/260507-vmj-ack-lost-duplicate-analysis/260507-vmj-VERIFICATION.md`
- `.planning/STATE.md`

No production source changed.

## Final Status

Analysis complete. Recommended next task: fix dispatcher late-event recovery/state machine so late `ORDER_OPENED` can be processed as success instead of unmatched after ACK timeout.
