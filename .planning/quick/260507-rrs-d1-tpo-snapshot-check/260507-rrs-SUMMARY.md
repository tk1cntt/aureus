---
quick_id: 260507-rrs
status: completed
completed_at: 2026-05-07
mode: quick-full
---

# Quick Task 260507-rrs Summary

## Task

Kiểm tra vì sao dữ liệu `POC/VAL/VAH` của D1 chưa được lưu vào bảng snapshots. Xác nhận dữ liệu đầu vào đã có hay chưa.

## Kết luận ngắn

- Schema có cột `d1_poc`, `d1_vah`, `d1_val`.
- `journal.py` có thể persist D1 TPO nếu `signal_snapshot` có:
  - `d1_poc`, `d1_vah`, `d1_val`
  - hoặc `D1_POC`, `D1_VAH`, `D1_VAL`
  - hoặc `tpo_d1.POC`, `tpo_d1.VAH`, `tpo_d1.VAL`
- DB snapshot hiện tại: `4000/4000` rows đều null D1 TPO.
- Dữ liệu đầu vào thực tế đã có trong Redis signal stream tại `indicator_snapshot.tpo_d1`.
- Nhưng `signals_snapshot` không có `tpo_d1`, và `aureus_trade_journal.active_signals/context_filters` không có text `tpo_d1` hoặc `POC`.
- Root cause: upstream publisher không copy `indicator_snapshot.tpo_d1` vào `signal_snapshot`; trader chỉ persist từ `signal_snapshot/event`, nên snapshot DB nhận null.

## GitNexus Evidence

### Query

```text
npx gitnexus query "D1 POC VAL VAH snapshot persistence" --repo Aureus
```

Found relevant TPO/indicator files:

- `services/aureus-signal/engine/indicator_snapshot.py`
- `services/aureus-signal/engine/signals/tpo.py`
- `services/aureus-signal/engine/signals/tpo_context.py`
- `services/aureus-trader/journal.py`

### Impact: `_build_signal_snapshot_columns`

```text
risk: CRITICAL
impactedCount: 7
direct caller: on_order_opened
processes_affected: 9
modules_affected: 3
```

No code edits made.

## Code Path Evidence

### Trader persistence mapping

File: `services/aureus-trader/journal.py`

```python
"d1_poc": _to_float_or_none(_first_present(merged_snapshot, src_event, ("d1_poc", "D1_POC"))),
"d1_vah": _to_float_or_none(_first_present(merged_snapshot, src_event, ("d1_vah", "D1_VAH"))),
"d1_val": _to_float_or_none(_first_present(merged_snapshot, src_event, ("d1_val", "D1_VAL"))),
```

Fallback:

```python
tpo_d1 = merged_snapshot.get("tpo_d1")
if isinstance(tpo_d1, dict):
    columns["d1_poc"] = columns["d1_poc"] if columns["d1_poc"] is not None else _to_float_or_none(tpo_d1.get("POC", tpo_d1.get("poc")))
    columns["d1_vah"] = columns["d1_vah"] if columns["d1_vah"] is not None else _to_float_or_none(tpo_d1.get("VAH", tpo_d1.get("vah")))
    columns["d1_val"] = columns["d1_val"] if columns["d1_val"] is not None else _to_float_or_none(tpo_d1.get("VAL", tpo_d1.get("val")))
```

### Signal indicator source includes TPO

File: `services/aureus-signal/engine/indicator_snapshot.py`

```python
"tpo_d1": _get_tpo_block("tpo_d1"),
"tpo_h1": _get_tpo_block("tpo_h1"),
"tpo_m30": _get_tpo_block("tpo_m30"),
```

### Publisher drops TPO during derived signal snapshot build

File: `services/aureus-signal/engine/signal_event_publisher.py`

`_build_signal_snapshot_from_indicator_snapshot()` derives EMA/ATR/volume/session/BB/candle/CISD only. No `tpo_d1` mapping exists, so `publish_strategy_match()` sends `signal_snapshot` without D1 TPO.

## DB Evidence

### Snapshot table null rate

```text
 total | any_d1_tpo | full_d1_tpo | all_null_d1_tpo 
-------+------------+-------------+-----------------
  4000 |          0 |           0 |            4000
(1 row)
```

### Latest snapshots sample

Latest rows have null D1 TPO:

```text
id   | trace_id              | strategy_name        | symbol | d1_poc | d1_vah | d1_val
5435 | XAUUSD:641:1778169540 | CISD_CONSENSUS_BULL | XAUUSD |        |        |
5434 | BTCUSD:641:1778169480 | CISD_CONSENSUS_BULL | BTCUSD |        |        |
5433 | BTCUSD:607:1778168700 | CHOCH_CISD_BULL     | BTCUSD |        |        |
5431 | BTCUSD:1:1778168700   | TREND_CONT_BULL     | BTCUSD |        |        |
```

### Journal payload lacks TPO

```text
 journal_total | with_tpo_d1 | with_poc 
---------------+-------------+----------
         11931 |           0 |        0
(1 row)
```

## Runtime Input Evidence

Latest `aureus:stream:XAUUSD:signals` payload:

```text
indicator_tpo_d1= {"POC": 4696.92, "VAH": 4736.72, "VAL": 4685.42, "distr": 228.87209302, "distribution_regime": "UNKNOWN", "shape": "b", "shape_confidence_pct": 100.0, "shape_scores_pct": {"B": 0.0, "D": 0.0, "b": 100.0, "p": 0.0}}
indicator_has_tpo_d1= True
payload_t= 1778169960
```

But:

```text
signals_snapshot_has_tpo_d1= False
signals_snapshot_tpo_d1= null
```

## Root Cause

D1 TPO exists upstream in `indicator_snapshot.tpo_d1`, but not in `signal_snapshot`. Trader snapshot persistence reads `signal_snapshot`/event fields, not raw Redis signal stream `indicator_snapshot`. Therefore `d1_poc/d1_vah/d1_val` stay null for real strategy-match snapshots.

## Recommended Fix

Add minimal mapping in `services/aureus-signal/engine/signal_event_publisher.py::_build_signal_snapshot_from_indicator_snapshot()`:

- if `indicator_snapshot.tpo_d1` is dict, copy it into derived `signal_snapshot["tpo_d1"]`
- or flatten into `d1_poc/d1_vah/d1_val`

Preferred: copy `tpo_d1` dict, because trader already supports `tpo_d1.POC/VAH/VAL` and now OHLC fallback too.

Then add regression test in `services/aureus-signal/tests/test_signal_event_publisher.py` proving strategy match payload `data.signal_snapshot.tpo_d1` exists.
