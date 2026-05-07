---
quick_id: 260507-u2b
status: passed
verified_at: 2026-05-07
---

# Quick Task 260507-u2b Verification

## Verdict

PASS.

## Must-Haves

### Identify why BTCUSD MARKET SELL orders returned MT5 retcode 10016 INVALID_STOPS

PASS.

Immediate cause: MT5 provider received object-valued `sl`/`tp`, but parses them as doubles.

Input had:

```json
"sl": {"type": "PIVOT_POINT", "offset_pips": 1}
"tp": {"type": "RR_RATIO", "value": 1.5}
```

Provider code:

```mql5
double sl = ParseJSONDouble(raw, "sl");
double tp = ParseJSONDouble(raw, "tp");
```

`ParseJSONDouble()` returns `0.0` for object fields because object starts with `{`, not numeric literal.

For SELL MARKET, provider then uses:

```mql5
entry_price = bid;
sl = sl + total_adjustment;
tp = entry_price - (sl - entry_price) * tpRRRatio;
```

With `sl=0.0`, generated stops are invalid for SELL. `OrderCheck()` returns retcode `10016`.

### Determine whether bad SL/TP came from upstream command, provider recalculation, or broker stop constraints

PASS.

Classification:

- Upstream command: malformed for MT5 contract. `sl`/`tp` are config objects, not absolute numbers.
- Provider recalculation: deterministic amplifier. It assumes numeric SL and recalculates TP from bad `sl=0.0`.
- Broker stop constraints: final rejection mechanism, not root cause. Broker correctly rejects impossible SELL stop geometry.

Numeric evidence from log:

```text
entry_price=80115.66000 ask=80127.66000 bid=80115.66000
```

For SELL, valid SL must be above market and TP below market. Object parse -> zero makes provider produce invalid geometry.

### Determine whether fix is needed now or report-only is sufficient

PASS.

Recommendation: no MQL5 parser fix. Keep provider strict numeric.

Future fix if recurring:

1. Trader guard: reject non-numeric `sl`/`tp` in `build_order_command()`/validator before MT5 send.
2. Signal publisher guard: executable `STRATEGY_MATCH.data.sl/tp` must be absolute numeric.
3. Trace why those BTCUSD events missed `sl_absolute`/`tp_absolute` enrichment.

This task remains report-only: user asked for root-cause analysis, not full fix.

## Verification Commands

GitNexus query:

```text
npx gitnexus query "INVALID_STOPS OrderCheck stop loss take profit ExecuteOpenOrder BTCUSD" --repo Aureus
npx gitnexus query "build_order_command sl object OPEN_ORDER strategy match order_plan_snapshot" --repo Aureus
```

Focused tests:

```text
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && PYTHONWARNINGS=ignore ./.venv/bin/python -m pytest services/aureus-trader/tests/test_order_builder.py::TestBuildOrderCommand::test_forward_conditional_execution_fields_when_present services/aureus-signal/tests/test_pivot_sl.py -q"
........................                                                 [100%]
24 passed in 9.92s
```

## Scope Check

No source code modified for `260507-u2b`.

Created artifacts:

- `.planning/quick/260507-u2b-invalid-stops-analysis/260507-u2b-PLAN.md`
- `.planning/quick/260507-u2b-invalid-stops-analysis/260507-u2b-SUMMARY.md`
- `.planning/quick/260507-u2b-invalid-stops-analysis/260507-u2b-VERIFICATION.md`

STATE.md updated with quick row.

## Final Status

Root cause proven by log + code path. Invalid stops caused by object `sl`/`tp` reaching numeric MT5 parser, not by random broker behavior.
