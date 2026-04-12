# Phase 40: Signal Classification — Indicator vs Event-based — Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-12
**Phase:** 40-signal-classification-indicator-event-based
**Mode:** assumptions
**Areas analyzed:** Signal Classification, Indicator Snapshot Collection, Telegram Message Format, Indicator Selection

## Assumptions Presented

### Signal Classification
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Thêm signal_type attribute lên BaseSignal | Confident | BaseSignal là abstract base class cho tất cả signals. Pattern tương tự đã có trong `event_policy.py` `_AI_TAG_TO_TRIGGER` phân biệt event tags vs indicator tags |
| Validation raise error nếu thiếu signal_type | Confident | Phase 36 đã có precedent: TemplateStrategy.__init__ validate direction, raise ValueError nếu thiếu |
| Classification: Indicators = EMA/ATR/VolSMA/Trend/Session, Events = CHoCH/Sweep/FVG | Confident | `_AI_TAG_TO_TRIGGER` trong `event_policy.py` chỉ map structural tags (events). Indicator tags không có trong mapping này |

### Indicator Snapshot Collection
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Snapshot từ state object tại thời điểm publish event | Confident | `snapshot_utils.py` `build_snapshot()` đã có pattern thu thập tất cả indicator values từ state |
| Đóng gói vào `data.indicator_snapshot` trong payload | Confident | Payload hiện tại có structure `{"type", "symbol", "t", "data"}` với `data.signals` — thêm key mới không phá backward compat |

### Telegram Message Format
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Section "📈 Indicator Snapshot" riêng biệt | Confident | `formatters.py` đã có pattern section-based formatting. Thêm section mới sau "Active Signals" không phá existing format |
| Format nhóm EMA thành 1 line để tiết kiệm space | Likely | Telegram limit 4096 chars, current format already uses ~200-400 chars. EMA group line saves ~300 chars vs 6 separate lines |

### Indicator Selection
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Include ALL indicators (EMA 21/34/55/89/100/200, ATR, VolSMA, Trend, Session) | Confident | `snapshot_utils.py` `build_snapshot()` already collects all these values. No additional computation needed. |
| EMA cross events có visual marker (📈/📉) | Likely | EMA signal data dict đã có `cross` key với `cross_up`/`cross_down` values |

## Corrections Made

No corrections — AskUserQuestion không hoạt động trong session này, decisions dựa trên recommended defaults từ codebase analysis.

## Auto-Resolved

All assumptions auto-resolved based on codebase evidence:
- Signal classification: Thêm signal_type attribute lên BaseSignal (type-safe, dễ maintain)
- Snapshot collection: Reuse `build_snapshot()` pattern từ `snapshot_utils.py`
- Telegram format: Section riêng "📈 Indicator Snapshot" sau "Active Signals"
- Indicator selection: ALL indicators, grouped format để tiết kiệm space

## External Research

No external research performed — all decisions based on codebase analysis.
