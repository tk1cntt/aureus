---
quick_id: 260507-udw
status: passed
verified_at: 2026-05-07
---

# Quick Task 260507-udw Verification

## Verdict

PASS.

## Must-Haves

### Non-numeric object SL/TP must not be sent to MT5 as OPEN_ORDER payload

PASS.

`build_order_command()` now validates selected `sl` and `tp` before command dict is returned:

```python
sl = _require_numeric_stop(data.get("sl_absolute") or data.get("sl"), "sl")
tp = _require_numeric_stop(data.get("tp_absolute") or data.get("tp"), "tp")
```

Malformed object payloads raise `ValueError` before dispatcher can send to MT5.

Regression tests:

```python
def test_reject_object_sl_before_mt5_dispatch(self):
    event = _make_match_event({"data": {"sl_absolute": None, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}}})

    with pytest.raises(ValueError, match="sl must be numeric"):
        build_order_command(event)

def test_reject_object_tp_before_mt5_dispatch(self):
    event = _make_match_event({"data": {"tp_absolute": None, "tp": {"type": "RR_RATIO", "value": 1.5}}})

    with pytest.raises(ValueError, match="tp must be numeric"):
        build_order_command(event)
```

### Numeric int/float SL/TP path must remain unchanged

PASS.

Regression test:

```python
def test_numeric_absolute_sl_tp_still_pass_through(self):
    event = _make_match_event({"data": {"sl_absolute": 80590.94, "tp_absolute": 79377.85}})

    cmd = build_order_command(event)

    assert cmd["sl"] == 80590.94
    assert cmd["tp"] == 79377.85
```

Full order builder suite passes:

```text
.................                                                        [100%]
17 passed in 0.38s
```

### Error must fail before socket dispatch path can produce INVALID_STOPS from object parsing

PASS.

Validation occurs inside `build_order_command()` before command exists for dispatcher send path. Dispatcher payload contract still passes for valid command payloads:

```text
.                                                                        [100%]
1 passed in 0.21s
```

## Commands

```text
npx gitnexus impact build_order_command --repo Aureus --direction upstream
```

Output summary:

```text
risk: CRITICAL
impactedCount: 2
direct caller: run_trader
affected module: Aureus-trader
```

```text
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && PYTHONWARNINGS=ignore ./.venv/bin/python -m pytest services/aureus-trader/tests/test_order_builder.py -q"
```

```text
wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && PYTHONWARNINGS=ignore ./.venv/bin/python -m pytest services/aureus-trader/tests/test_dispatcher.py::TestOrderDispatcherPayloadContract -q"
```

```text
git diff --check -- services/aureus-trader/order_builder.py services/aureus-trader/tests/test_order_builder.py
```

GitNexus detect changes attempted, unavailable:

```text
npx gitnexus detect-changes --repo Aureus
error: unknown command 'detect-changes'
```

## Scope Check

Changed source:

- `services/aureus-trader/order_builder.py`
- `services/aureus-trader/tests/test_order_builder.py`

Artifacts:

- `.planning/quick/260507-udw-invalid-stops-guard/260507-udw-PLAN.md`
- `.planning/quick/260507-udw-invalid-stops-guard/260507-udw-SUMMARY.md`
- `.planning/quick/260507-udw-invalid-stops-guard/260507-udw-VERIFICATION.md`
- `.planning/STATE.md`

Unrelated untracked files not touched:

- `mql5/AureusProvider_v2.ex5`
- `stable/`

## Final Status

Fix verified. Object SL/TP cannot cross trader order-builder boundary into MT5 dispatch.
