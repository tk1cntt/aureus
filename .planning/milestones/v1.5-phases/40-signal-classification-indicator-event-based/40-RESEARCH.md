# Phase 40: Signal Classification — Indicator vs Event-based with Telegram Snapshot — Research

**Researched:** 2026-04-12
**Domain:** Signal classification, indicator snapshot collection, Telegram notification formatting
**Confidence:** HIGH

## Summary

Phase 40 introduces formal signal classification (INDICATOR vs EVENT) to the Aureus signal engine and enriches Telegram notifications with a compact indicator snapshot when event-based signals trigger. The core change touches three layers: (1) signal class hierarchy adds a `SignalType` enum and class-level `signal_type` attribute, (2) `live_engine.py` gains a hook point between `evaluate_ai_trigger_events()` and `publish_signal_event()` to build and attach an indicator snapshot to the pub/sub payload, and (3) `aureus-notifier/formatters.py` gains a new "📈 Indicator Snapshot" section in the Telegram message format.

The existing `build_snapshot()` function in `snapshot_utils.py` already collects all indicator values from state (EMA, ATR, Volume SMA, HTF Trend, Session). The indicator snapshot helper can reuse this data-collection pattern but should be lighter weight — omitting DB-heavy fields (OB lists, swing points, strategy progress, etc.) and grouping EMAs onto one line.

**Primary recommendation:** Create a new `indicator_snapshot.py` helper module in the signal engine, hook it into `live_engine.py` at the existing `publish_signal_event()` call site, and extend `format_signal_event()` in the notifier to render the new section.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Thêm `SignalType` enum (INDICATOR / EVENT) và thuộc tính class-level `signal_type` lên `BaseSignal`. Subclasses override bằng 1 dòng: `signal_type = SignalType.INDICATOR`
- **D-02:** Auto-detect fallback: nếu subclass không khai báo `signal_type`, mặc định là `INDICATOR` (safe default). Factory log warning nhưng KHÔNG crash — cho phép migration gradual
- **D-03:** Classification mapping:
  - **Indicators:** EMASignal (tất cả periods), ATRSignal, VolumeSMASignal, TrendSignal, SessionSignal, PivotSignal
  - **Events:** StructureSignal, CHOCHUpSignal, CHOCHDownSignal, SweepSignal, SweepBullSignal, SweepBearSignal, FVGSignal, FVGUpSignal, FVGDownSignal
- **D-04:** Backward compatible — `signal_type` là optional class attribute, không phá vỡ `calculate()` signature
- **D-05:** Tạo helper function `build_indicator_snapshot_for_telegram(state)` — lightweight, chỉ lấy các values cần cho display. KHÔNG reuse trực tiếp `build_snapshot()` (function đó dành cho DB, nặng và có nhiều fields không cần cho Telegram)
- **D-06:** Hook point: trong `live_engine.py`, SAU `evaluate_ai_trigger_events()` trả về non-empty, TRƯỚC KHI gọi `publish_signal_event()` — build snapshot và attach vào `data["indicator_snapshot"]`
- **D-07:** Snapshot đóng gói vào `data.indicator_snapshot` trong payload pub/sub — backward compatible, consumer cũ ignore key mới
- **D-08:** Thêm section "📈 Indicator Snapshot" riêng biệt vào message, đặt SAU "Active Signals" và TRƯỚC hashtag
- **D-09:** Format nhóm EMA thành 1 line: `• EMA(21/34/55/89/100/200): 2341.20/2343.50/2346.80/2351.00/2355.40/2370.10`. Các indicators khác mỗi cái 1 line: `• ATR(14): 12.34`
- **D-10:** Safety truncate: nếu message >4095 chars, truncate indicator section TRƯỚC — giữ nguyên Active Signals section (event info quan trọng hơn)
- **D-11:** Bao gồm các indicator values từ state: EMAs 21/34/55/89/100/200 (giá trị current), ATR(14), Volume SMA(20), HTF Trend. KHÔNG include Market Session (đã có ở header)
- **D-12:** Cross detection: nếu EMA có cross event trong candle hiện tại, thêm emoji marker 📈 (cross up) atau 📉 (cross down) vào cuối line EMA
- **D-13:** Giá trị `None` hoặc missing hiển thị là `—` (em dash) để user biết indicator chưa có data
- **D-14:** Bỏ `market_session` khỏi indicator snapshot — đã hiển thị ở header message rồi, không cần lặp lại

### Claude's Discretion
- Helper function placement (new file vs existing `snapshot_utils.py`)
- Exact HTML formatting details (color, emoji choices)
- Whether to cache indicator snapshot or rebuild each time

### Deferred Ideas (OUT OF SCOPE)
- Smart selection (chỉ indicators "đáng chú ý") — deferred, phase này dùng all-inclusive approach
- Configurable indicator subset qua config file — deferred, có thể thêm sau nếu cần
- Indicator-only notification mode (notification khi indicator cross mà không cần event) — future phase
- Indicator alert thresholds (alert khi ATR vượt ngưỡng, EMA cross đặc biệt) — future phase

## Standard Stack

No new libraries required. This phase uses existing project infrastructure.

### Core
| Module | File | Purpose | Why Standard |
|--------|------|---------|--------------|
| `SignalType` enum | `services/aureus-signal/engine/signals/base.py` | Classify signals as INDICATOR/EVENT | Extends existing `BaseSignal` class |
| `build_indicator_snapshot_for_telegram()` | `services/aureus-signal/engine/indicator_snapshot.py` (NEW) | Build lightweight indicator dict from state | Follows existing `build_snapshot()` pattern |
| `format_indicator_section()` | `services/aureus-notifier/formatters.py` | Render indicator snapshot as HTML | Extends existing `format_signal_event()` |

No new dependencies to install. All changes are in existing modules.

## Architecture Patterns

### Recommended Project Structure

New file to create:
```
services/aureus-signal/engine/
├── indicator_snapshot.py          # NEW: build_indicator_snapshot_for_telegram(state)
└── signals/
    └── base.py                    # MODIFIED: add SignalType enum + signal_type attribute
```

Modified files (in order of dependency):
```
1. services/aureus-signal/engine/signals/base.py        # Add SignalType enum
2. services/aureus-signal/engine/signals/ema.py         # Add signal_type = SignalType.INDICATOR
3. services/aureus-signal/engine/signals/atr.py         # Add signal_type = SignalType.INDICATOR
4. services/aureus-signal/engine/signals/volume_sma.py  # Add signal_type = SignalType.INDICATOR
5. services/aureus-signal/engine/signals/trend.py       # Add signal_type = SignalType.INDICATOR
6. services/aureus-signal/engine/signals/session.py     # Add signal_type = SignalType.INDICATOR
7. services/aureus-signal/engine/signals/pivots.py      # Add signal_type = SignalType.INDICATOR
8. services/aureus-signal/engine/signals/structure.py   # Add signal_type = SignalType.EVENT
9. services/aureus-signal/engine/signals/sweep.py       # Add signal_type = SignalType.EVENT
10. services/aureus-signal/engine/signals/fvg_up.py     # Add signal_type = SignalType.EVENT
11. services/aureus-signal/engine/signals/fvg_down.py   # Add signal_type = SignalType.EVENT
12. services/aureus-signal/engine/signals/choch_up.py   # Add signal_type = SignalType.EVENT
13. services/aureus-signal/engine/signals/choch_down.py # Add signal_type = SignalType.EVENT
14. services/aureus-signal/engine/signals/sweep_bull.py # Add signal_type = SignalType.EVENT
15. services/aureus-signal/engine/signals/sweep_bear.py # Add signal_type = SignalType.EVENT
16. services/aureus-signal/engine/indicator_snapshot.py # NEW helper module
17. services/aureus-signal/engine/live_engine.py        # Hook point for indicator snapshot
18. services/aureus-signal/engine/signal_factory.py     # Optional: validation logging
19. services/aureus-notifier/formatters.py              # Add indicator snapshot section
```

### Pattern 1: Class-Level Signal Type Attribute

**What:** Each signal subclass gets a class-level `signal_type` attribute that classifies it as INDICATOR or EVENT.

**Why this pattern:** Class-level attributes are set once at import time, not per-instance. This is Python's standard pattern for static classification (similar to Django model Meta classes, SQLAlchemy declarative base, etc.).

**Example in base.py:**
```python
from enum import Enum

class SignalType(Enum):
    INDICATOR = "indicator"
    EVENT = "event"

class BaseSignal(ABC):
    """Base class for all Atomic Signals (FVG, Sweep, EMA, etc.)"""

    # Default: INDICATOR (safe default for gradual migration)
    signal_type = SignalType.INDICATOR

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def get_signal_type(cls) -> SignalType:
        """Returns the signal type, defaulting to INDICATOR if not overridden."""
        st = getattr(cls, "signal_type", None)
        if st is None:
            import logging
            from engine.logging_common import get_logger
            get_logger(__name__).warning(
                f"Signal class {cls.__name__} does not define signal_type, defaulting to INDICATOR"
            )
            return SignalType.INDICATOR
        return st
```

**Example in subclasses (ema.py):**
```python
class EMASignal(BaseSignal):
    signal_type = SignalType.INDICATOR  # 1 line addition
    ...
```

**Example in subclasses (structure.py):**
```python
class StructureSignal(BaseSignal):
    signal_type = SignalType.EVENT  # 1 line addition
    ...
```

### Pattern 2: Indicator Snapshot Builder

**What:** A new `build_indicator_snapshot_for_telegram(state)` function that extracts only the display-relevant indicator values from the state object.

**Pattern source:** Reuses the `_get_ema_val()` extraction pattern from existing `build_snapshot()` in `snapshot_utils.py` (lines 169-179).

**Design:**
```python
def build_indicator_snapshot_for_telegram(state) -> Dict[str, Any]:
    """Build a lightweight indicator snapshot for Telegram notification.

    Collects current indicator values from state. Designed for display,
    not DB storage — omits heavy fields (OB lists, swing points, etc.).
    """
    def _get_ema_val(period: int):
        v = state.emas.get(period)
        return v.get("current") if isinstance(v, dict) else v

    # Detect EMA crosses from transient_signals
    def _ema_cross_marker(period: int) -> str:
        tag_up = f"ema_{period}_cross_up"
        tag_dn = f"ema_{period}_cross_down"
        if tag_up in (state.transient_signals or {}):
            return " 📈"
        if tag_dn in (state.transient_signals or {}):
            return " 📉"
        return ""

    snapshot = {}

    # Grouped EMAs
    ema_periods = [21, 34, 55, 89, 100, 200]
    ema_values = [_get_ema_val(p) for p in ema_periods]
    snapshot["emas"] = {
        "periods": ema_periods,
        "values": ema_values,
        "cross_markers": [_ema_cross_marker(p) for p in ema_periods],
    }

    # ATR
    snapshot["atr_14"] = getattr(state, "atr", None)

    # Volume SMA
    snapshot["vol_sma_20"] = getattr(state, "vol_sma_20", None)

    # HTF Trend
    snapshot["htf_trend"] = getattr(state, "htf_trend", None)

    # NOTE: market_session intentionally excluded (D-14)

    return snapshot
```

### Pattern 3: Hook Point in Live Engine

**What:** Attach indicator snapshot to the pub/sub payload at the existing `publish_signal_event()` call site in `live_engine.py`.

**Current code (live_engine.py lines 739-747):**
```python
# Publish signal event to pub/sub for downstream consumers only if actionable AI triggers exist
if getattr(state, "transient_signals", None):
    from engine.event_policy import evaluate_ai_trigger_events
    if evaluate_ai_trigger_events(state.transient_signals):
        from engine.signal_event_publisher import publish_signal_event
        await publish_signal_event(
            r, symbol, "SIGNAL_EVENT", ts_unix,
            {"signals": state.transient_signals}
        )
```

**Modified (hook point per D-06):**
```python
if getattr(state, "transient_signals", None):
    from engine.event_policy import evaluate_ai_trigger_events
    triggers = evaluate_ai_trigger_events(state.transient_signals)
    if triggers:
        from engine.signal_event_publisher import publish_signal_event
        from engine.indicator_snapshot import build_indicator_snapshot_for_telegram
        data = {"signals": state.transient_signals}
        data["indicator_snapshot"] = build_indicator_snapshot_for_telegram(state)
        await publish_signal_event(r, symbol, "SIGNAL_EVENT", ts_unix, data)
```

### Pattern 4: Telegram Formatting with Truncation

**What:** Extend `format_signal_event()` to render the indicator snapshot section, with safety truncation.

**Source:** Current `format_signal_event()` in `services/aureus-notifier/formatters.py` (lines 11-80).

**Key design decisions:**
- Indicator snapshot section placed AFTER "Active Signals" and BEFORE hashtag line (D-08)
- EMA values grouped on one line: `• EMA(21/34/55/89/100/200): 2341.20/2343.50/...` (D-09)
- Other indicators each on their own line: `• ATR(14): 12.34` (D-09)
- Missing/None values show `—` (em dash, D-13)
- Truncate from the indicator section first if message >4095 chars (D-10)
- `market_session` excluded (D-14)

### Anti-Patterns to Avoid

- **Do NOT modify `evaluate_ai_trigger_events()`:** Decision D-06 explicitly says this function's logic stays unchanged. The hook is AFTER it returns, not inside it.
- **Do NOT reuse `build_snapshot()` directly:** Decision D-05 says it's too heavy (includes OB lists, swing points, strategy progress, etc. — fields for DB, not display). Build a new lightweight function instead.
- **Do NOT change the pub/sub payload structure incompatibly:** Decision D-07 says add `indicator_snapshot` as a new key in the existing `data` dict. Consumer `format_signal_event()` should use `data.get("indicator_snapshot")` which returns None for old payloads — backward compatible.
- **Do NOT add `signal_type` as instance attribute in `__init__`:** Decision D-01 says it's a class-level attribute. Subclasses override with one line at class scope, not in constructor.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signal classification | Custom type registry or config mapping | Class-level `signal_type` attribute + `SignalType` enum | Already embedded in class definition, zero runtime overhead, type-safe |
| Indicator value extraction | Re-scan candles to recalculate EMAs | Read from `state.emas`, `state.atr`, etc. | Values already computed and cached in state by the time snapshot runs |
| Telegram HTML escaping | Manual string replacement | `html.escape()` from Python stdlib | Already imported and used in `formatters.py` — handles all edge cases |
| Message truncation | Complex smart-truncate algorithm | Truncate the indicator section first, then hard-truncate at 4095 chars | Simple, deterministic, preserves critical event data |

**Key insight:** The indicator snapshot is pure data extraction from already-computed state. No recalculation needed. The `build_snapshot()` function in `snapshot_utils.py` proves all the values are already available on the state object.

## Common Pitfalls

### Pitfall 1: EMA Cross Detection False Positives
**What goes wrong:** EMA cross tags (`ema_21_cross_up`, etc.) appear in `transient_signals` from the EMA signal's `res["data"]["cross"]` field. But the cross tag is in the `data` sub-dict, NOT as a top-level key in `transient_signals`.
**Why it happens:** The EMA signal's `calculate()` method stores cross info as `res["data"]["cross"] = "ema_21_cross_up"`. This is written to `state.transient_signals` via `state.map_signal_to_candle_record()` with the tag being `ema_21_up` or `ema_21_down`, not the cross tag.
**How to avoid:** Cross detection should check the EMA signal's result data in `transient_signals`, OR detect crosses by comparing `state.emas[period]["current"]` vs `state.emas[period]["prev"]` against price. The `_ema_cross_marker()` helper needs to examine the actual transient_signals structure, which stores data under keys like `ema_21_up` → `{"value": 2341.2, "data": {"close": 2350, "cross": "ema_21_cross_up"}}`.
**Warning signs:** Cross emojis appear on wrong candles or never appear.

### Pitfall 2: `transient_signals` Structure Variability
**What goes wrong:** The `transient_signals` dict has different value shapes for different signal types — some are simple dicts `{"value": ..., "t": ...}`, others are complex (e.g., sweep signals with nested `data` dicts). The indicator snapshot builder must not assume uniform structure.
**Why it happens:** Indicator signals store their result dicts directly as values, while event signals store complex nested structures.
**How to avoid:** The `build_indicator_snapshot_for_telegram()` function reads from `state.emas`, `state.atr`, `state.vol_sma_20`, `state.htf_trend` — not from `transient_signals`. Cross detection is the only place that needs to inspect `transient_signals`.

### Pitfall 3: Consumer Signal Classes Missing `signal_type`
**What goes wrong:** Consumer signals (CHOCHUpSignal, SweepBullSignal, etc.) simply return `state.transient_signals.get(self.TAG)` — they don't have their own calculation. Adding `signal_type = SignalType.EVENT` is correct but easy to forget on all consumer classes.
**Why it happens:** There are 6 consumer signal classes across separate files (choch_up, choch_down, sweep_bull, sweep_bear, fvg_up, fvg_down) plus their processors (structure, sweep). It's easy to miss one.
**How to avoid:** Use the classification mapping from D-03 as a checklist. After adding all `signal_type` attributes, run a grep to verify none are missing.

### Pitfall 4: FVG Signal Feature Flag
**What goes wrong:** FVG signals (`FVGUpSignal`, `FVGDownSignal`) are conditionally created based on `AUREUS_ENABLE_FVG_SIGNAL` env var (in `signal_factory.py`). If FVG is disabled, those signal classes won't exist in the signal set, and the `signal_type` attribute on those classes won't be tested.
**Why it happens:** The `_is_fvg_enabled()` check at line 152 of `signal_factory.py`.
**How to avoid:** Add `signal_type = SignalType.EVENT` to FVG signal classes regardless. The env var controls runtime instantiation, not class definition. The classification is still correct when FVG is enabled.

### Pitfall 5: Telegram Message Character Limit
**What goes wrong:** Adding indicator snapshot could push message over 4096 chars (Telegram HTML parse mode limit is 4096, not 4095 as the current code uses — the current `[:4095]` is actually safe).
**Why it happens:** 6 EMA values with 7-digit prices = ~60 chars, plus ATR, Vol SMA, HTF Trend = ~100 chars total for indicator section. Combined with existing Active Signals section (variable length) + header, could exceed limit.
**How to avoid:** Build the message, check length, and if >4095 chars, truncate/rebuild without the indicator section. D-10 says truncate indicator section first.
**VERIFIED:** Telegram Bot API limit is 4096 characters for Bot API messages with HTML parse mode. The current code uses `[:4095]` which is safe.

### Pitfall 6: `default=str` in JSON Serialization
**What goes wrong:** The `publish_signal_event()` function uses `json.dumps(payload, default=str)`. If the indicator snapshot contains enum values or complex objects, they'll be serialized as strings (e.g., `SignalType.INDICATOR` → `"SignalType.INDICATOR"`).
**Why it happens:** The snapshot should only contain primitive types (int, float, str, None, list, dict). But if an enum value leaks in, it'll serialize as the enum repr.
**How to avoid:** Ensure `build_indicator_snapshot_for_telegram()` returns only primitive types. Convert `SignalType` enum to `.value` string if used in the snapshot.

## Code Examples

### SignalType Enum in base.py
```python
from abc import ABC, abstractmethod
from enum import Enum
import pandas as pd
from typing import Dict, Any, Optional


class SignalType(Enum):
    """Classifies signals as either continuous indicators or discrete events."""
    INDICATOR = "indicator"
    EVENT = "event"


class BaseSignal(ABC):
    """Base class for all Atomic Signals (FVG, Sweep, EMA, etc.)"""

    signal_type = SignalType.INDICATOR  # Default: safe for gradual migration

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def get_signal_type(cls) -> SignalType:
        st = getattr(cls, "signal_type", None)
        if st is None:
            import logging
            logging.getLogger(__name__).warning(
                f"Signal class {cls.__name__} missing signal_type, defaulting to INDICATOR"
            )
            return SignalType.INDICATOR
        return st

    @abstractmethod
    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        pass
```

### EMA signal with indicator_snapshot cross detection
```python
# In indicator_snapshot.py — detect cross from transient_signals data
def _ema_cross_marker(period: int, transient_signals: dict) -> str:
    """Check if EMA cross occurred in current candle."""
    tag_up = f"ema_{period}_up"
    tag_down = f"ema_{period}_down"
    
    # Cross info is in the "data.cross" field of the EMA signal result
    ema_data = transient_signals.get(tag_up) or transient_signals.get(tag_down)
    if isinstance(ema_data, dict):
        cross = ema_data.get("data", {}).get("cross")
        if cross:
            if "cross_up" in str(cross):
                return " 📈"
            if "cross_down" in str(cross):
                return " 📉"
    return ""
```

### Indicator snapshot formatting in formatters.py
```python
def _format_indicator_section(snapshot: dict) -> str:
    """Format indicator snapshot as HTML lines for Telegram."""
    lines = []
    
    # Grouped EMAs
    emas = snapshot.get("emas", {})
    ema_periods = emas.get("periods", [])
    ema_values = emas.get("values", [])
    ema_markers = emas.get("cross_markers", [])
    
    if ema_values:
        ema_parts = []
        for i, (period, val) in enumerate(zip(ema_periods, ema_values)):
            if val is not None:
                ema_parts.append(f"{val:.2f}{ema_markers[i] if i < len(ema_markers) else ''}")
            else:
                ema_parts.append("—")
        period_str = "/".join(str(p) for p in ema_periods)
        value_str = "/".join(ema_parts)
        lines.append(f"• <b>EMA({period_str})</b>: {html.escape(value_str)}")
    
    # ATR
    atr = snapshot.get("atr_14")
    atr_display = f"{atr:.2f}" if atr is not None else "—"
    lines.append(f"• <b>ATR(14)</b>: {html.escape(atr_display)}")
    
    # Volume SMA
    vol = snapshot.get("vol_sma_20")
    vol_display = f"{vol:.0f}" if vol is not None else "—"
    lines.append(f"• <b>Vol SMA(20)</b>: {html.escape(vol_display)}")
    
    # HTF Trend
    htf = snapshot.get("htf_trend")
    htf_display = html.escape(str(htf)) if htf else "—"
    emoji_map = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}
    htf_emoji = emoji_map.get(htf, "")
    lines.append(f"• <b>HTF Trend</b>: {htf_emoji} {htf_display}")
    
    return "\n".join(lines)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No signal classification | `SignalType` enum on `BaseSignal` | This phase | Enables type-aware filtering, logging, and future features |
| Telegram message: only event signals | Event signals + indicator snapshot | This phase | Richer context in notifications without extra messages |
| `build_snapshot()` used for both DB and display | Separate `build_indicator_snapshot_for_telegram()` for display | This phase | Lighter weight, display-optimized format |
| Manual cross detection in EMA display | Cross emoji from transient_signals data | This phase | Visual marker for price-EMA crosses |

**Deprecated/outdated:**
- None directly deprecated — this phase is additive, not replacing existing functionality.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | EMA cross data is stored in `transient_signals[key]["data"]["cross"]` | Pitfall 1, Code Examples | Cross detection would not work; need to verify actual transient_signals structure at runtime |
| A2 | `state.emas` dict always has the structure `{period: {"current": float, "prev": float, "slope": float}}` after EMA calculation | Indicator Snapshot Builder | EMA extraction would fail; verified from `ema.py` lines 66-70, this is correct |
| A3 | The `transient_signals` dict keys for EMA signals are `ema_{period}_up` or `ema_{period}_down` (not `ema_{period}`) | Cross Detection | Cross marker lookup would fail; verified from `ema.py` `tag_up`/`tag_down` attributes and `state.map_signal_to_candle_record()` in `state.py` |

## Open Questions

1. **Cross detection key in transient_signals:** The EMA signal sets `res["data"]["cross"]` in its result, but the exact key under which this data appears in `transient_signals` depends on `state.map_signal_to_candle_record()` which maps EMA signals to `record.ema[ema_key]` (see `state.py` lines 204-212), NOT to the transient_signals dict directly. The cross info may only be in the CandleRecord, not in transient_signals. The planner should verify this by checking what `state.transient_signals` actually contains after EMA calculation.

2. **`format_signal_event()` already handles empty signals by returning `""`:** The current function returns empty string if `signals` is empty. With indicator snapshot, even events with no signals might want to show indicators. However, D-06 says the hook fires AFTER `evaluate_ai_trigger_events()` returns non-empty, so there will always be signals. This is safe.

3. **Should the indicator snapshot be attached ONLY when event triggers fire?** Decision D-06 and D-07 say yes — snapshot is attached to the pub/sub payload when event triggers exist. This means indicator data is NOT published on every candle, only when events occur. This is the correct design to avoid spam.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | Pub/sub for signal events, notifier subscription | Verified via codebase | async redis-py | — |
| Python 3.12+ | Signal engine runtime | Verified (code uses `zoneinfo`, `dataclass` defaults) | 3.12 (from test pycache paths) | — |
| Docker | Service orchestration | Verified (docker-compose references) | — | — |
| Telegram Bot API | Notification delivery | Verified (bot tokens in config) | — | — |

No missing dependencies. All required infrastructure already exists.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None detected — tests use standard pytest discovery |
| Quick run command | `pytest tests/ -x -q` (from either `aureus-signal` or `aureus-notifier` service dir) |
| Full suite command | `pytest tests/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIG-01 | SignalType enum + signal_type on all signal classes | unit | `pytest services/aureus-signal/tests/test_signal_type.py -x` | ❌ Wave 0 |
| SIG-02 | build_indicator_snapshot_for_telegram collects correct values | unit | `pytest services/aureus-signal/tests/test_indicator_snapshot.py -x` | ❌ Wave 0 |
| SIG-03 | format_signal_event renders indicator snapshot section | unit | `pytest services/aureus-notifier/tests/test_formatters.py::test_format_signal_event_with_indicator_snapshot -x` | ❌ Wave 0 (extend existing) |
| SIG-04 | Backward compatible: old payloads without indicator_snapshot still format | unit | `pytest services/aureus-notifier/tests/test_formatters.py::test_format_signal_event_no_snapshot -x` | ❌ Wave 0 (extend existing) |

### Wave 0 Gaps
- [ ] `services/aureus-signal/tests/test_signal_type.py` — covers SIG-01 (SignalType enum + classification on all signals)
- [ ] `services/aureus-signal/tests/test_indicator_snapshot.py` — covers SIG-02 (snapshot builder with mock state)
- [ ] Extend `services/aureus-notifier/tests/test_formatters.py` — add tests for SIG-03 and SIG-04
- [ ] Framework install: `pip install pytest` — if not already in virtualenv

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (quick run)
- **Per wave merge:** `pytest tests/` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | Indicator snapshot values are read from trusted state object (internal), not user input |
| V6 Cryptography | No | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTML injection in Telegram message | Tampering | `html.escape()` already used in `formatters.py` — must apply to all indicator values |
| Message truncation leaking sensitive data | Information Disclosure | Indicator values are market data (public), not sensitive. Safe to truncate. |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: all 19 source files read and analyzed
- `ema.py` lines 66-70: `state_obj.emas[period]` structure verified
- `state.py` lines 172-216: `map_signal_to_candle_record()` EMA handling verified
- `snapshot_utils.py` lines 155-239: `build_snapshot()` pattern verified
- `formatters.py` lines 11-80: current `format_signal_event()` verified
- `live_engine.py` lines 739-747: current publish_signal_event hook point verified
- Telegram Bot API: 4096 character limit — verified via multiple sources

### Secondary (MEDIUM confidence)
- EMA cross detection path: based on code analysis of `ema.py` + `state.py`, cross data flows through `map_signal_to_candle_record()` into `record.ema`, not directly into `transient_signals`

### Tertiary (LOW confidence)
- None — all critical claims verified against source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all changes in existing modules verified
- Architecture: HIGH — all patterns derived from existing codebase structure
- Pitfalls: HIGH — each pitfall traced to specific code paths

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (30 days — stable domain, no fast-moving dependencies)
