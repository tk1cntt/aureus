# Phase 40: Signal Classification — Indicator vs Event-based with Telegram Snapshot

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Phân loại chính thức signal thành 2 loại: (1) indicator-based signals (EMA, ATR, Volume SMA, Trend, Session) có giá trị liên tục theo từng nến, (2) event-based signals cần trigger/event mới xảy ra (CHoCH, Sweep, FVG, OB). Khi có event trigger, bổ sung snapshot giá trị của tất cả indicator signals vào thông báo Telegram.

Hiện tại: event signals (CHoCH, Sweep, FVG) trigger pub/sub notification qua `evaluate_ai_trigger_events()` trong `event_policy.py`, indicator signals (EMA, ATR, v.v.) KHÔNG trigger notification vì không có trong `_AI_TAG_TO_TRIGGER` mapping.

Phase này KHÔNG thay đổi logic trigger notification — chỉ bổ sung indicator snapshot vào message khi event đã trigger.
</domain>

<decisions>
## Implementation Decisions

### Signal Classification
- **D-01:** Thêm `SignalType` enum (INDICATOR / EVENT) và thuộc tính class-level `signal_type` lên `BaseSignal`. Subclasses override bằng 1 dòng: `signal_type = SignalType.INDICATOR`
- **D-02:** Auto-detect fallback: nếu subclass không khai báo `signal_type`, mặc định là `INDICATOR` (safe default). Factory log warning nhưng KHÔNG crash — cho phép migration gradual
- **D-03:** Classification mapping:
  - **Indicators:** EMASignal (tất cả periods), ATRSignal, VolumeSMASignal, TrendSignal, SessionSignal, PivotSignal
  - **Events:** StructureSignal, CHOCHUpSignal, CHOCHDownSignal, SweepSignal, SweepBullSignal, SweepBearSignal, FVGSignal, FVGUpSignal, FVGDownSignal
- **D-04:** Backward compatible — `signal_type` là optional class attribute, không phá vỡ `calculate()` signature

### Indicator Snapshot Collection
- **D-05:** Tạo helper function `build_indicator_snapshot_for_telegram(state)` — lightweight, chỉ lấy các values cần cho display. KHÔNG reuse trực tiếp `build_snapshot()` (function đó dành cho DB, nặng và có nhiều fields không cần cho Telegram)
- **D-06:** Hook point: trong `live_engine.py`, SAU `evaluate_ai_trigger_events()` trả về non-empty, TRƯỚC KHI gọi `publish_signal_event()` — build snapshot và attach vào `data["indicator_snapshot"]`
- **D-07:** Snapshot đóng gói vào `data.indicator_snapshot` trong payload pub/sub — backward compatible, consumer cũ ignore key mới

### Telegram Message Format
- **D-08:** Thêm section "📈 Indicator Snapshot" riêng biệt vào message, đặt SAU "Active Signals" và TRƯỚC hashtag
- **D-09:** Format nhóm EMA thành 1 line: `• EMA(21/34/55/89/100/200): 2341.20/2343.50/2346.80/2351.00/2355.40/2370.10`. Các indicators khác mỗi cái 1 line: `• ATR(14): 12.34`
- **D-10:** Safety truncate: nếu message >4095 chars, truncate indicator section TRƯỚC — giữ nguyên Active Signals section (event info quan trọng hơn)
- **D-14:** Bỏ `market_session` khỏi indicator snapshot — đã hiển thị ở header message rồi, không cần lặp lại

### Indicator Selection for Snapshot
- **D-11:** Bao gồm các indicator values từ state:
  - EMAs: 21, 34, 55, 89, 100, 200 (giá trị current)
  - ATR(14)
  - Volume SMA(20)
  - HTF Trend
  - KHÔNG include Market Session (đã có ở header)
- **D-12:** Cross detection: nếu EMA có cross event trong candle hiện tại, thêm emoji marker 📈 (cross up) hoặc 📉 (cross down) vào cuối line EMA
- **D-13:** Giá trị `None` hoặc missing hiển thị là `—` (em dash) để user biết indicator chưa có data

### Claude's Discretion
- Helper function placement (new file vs existing `snapshot_utils.py`)
- Exact HTML formatting details (color, emoji choices)
- Whether to cache indicator snapshot or rebuild each time

### Folded Todos
- None
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Signal Engine
- `services/aureus-signal/engine/signals/base.py` — BaseSignal class, cần thêm signal_type attribute
- `services/aureus-signal/engine/signal_factory.py` — Factory tạo signal set, cần validate signal_type
- `services/aureus-signal/engine/event_policy.py` — AI trigger evaluation, KHÔNG sửa logic trigger
- `services/aureus-signal/engine/snapshot_utils.py` — build_snapshot() pattern để reuse cho indicator snapshot
- `services/aureus-signal/engine/live_engine.py` — Main pipeline, nơi thêm indicator snapshot trước khi publish

### Signal Event Publishing
- `services/aureus-signal/engine/signal_event_publisher.py` — publish_signal_event(), payload structure
- `services/aureus-signal/engine/event_filter.py` — STRUCTURAL_TAGS definition

### Notifier
- `services/aureus-notifier/formatters.py` — format_signal_event(), cần thêm indicator snapshot section
- `services/aureus-notifier/main.py` — Notifier entry point
- `services/aureus-notifier/config.py` — Filter config

### Indicator Signals (cập nhật signal_type)
- `services/aureus-signal/engine/signals/ema.py` — EMASignal (indicator)
- `services/aureus-signal/engine/signals/atr.py` — ATRSignal (indicator)
- `services/aureus-signal/engine/signals/volume_sma.py` — VolumeSMASignal (indicator)
- `services/aureus-signal/engine/signals/trend.py` — TrendSignal (indicator)
- `services/aureus-signal/engine/signals/session.py` — SessionSignal (indicator)
- `services/aureus-signal/engine/signals/pivots.py` — PivotSignal (indicator — chỉ emit khi có pivot mới)

### Event Signals (cập nhật signal_type)
- `services/aureus-signal/engine/signals/structure.py` — StructureSignal + CHoCH consumers (event)
- `services/aureus-signal/engine/signals/sweep.py` — SweepSignal + consumers (event)
- `services/aureus-signal/engine/signals/fvg.py` — FVGSignal (event)
- `services/aureus-signal/engine/signals/fvg_up.py` — FVGUpSignal (event)
- `services/aureus-signal/engine/signals/fvg_down.py` — FVGDownSignal (event)
- `services/aureus-signal/engine/signals/choch_up.py` — CHOCHUpSignal (event consumer)
- `services/aureus-signal/engine/signals/choch_down.py` — CHOCHDownSignal (event consumer)
- `services/aureus-signal/engine/signals/sweep_bull.py` — SweepBullSignal (event consumer)
- `services/aureus-signal/engine/signals/sweep_bear.py` — SweepBearSignal (event consumer)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `snapshot_utils.py` `build_snapshot()` — Đã có pattern thu thập tất cả indicator values từ state object. Có thể extract helper function từ đây.
- `formatters.py` `format_signal_value()` — Đã có logic format giá trị signals, có thể extend cho indicator snapshot
- `signal_event_publisher.py` — Payload structure đã có `data` dict, chỉ cần thêm `indicator_snapshot` key
- `event_policy.py` `evaluate_ai_trigger_events()` — Gate hiện tại để detect event trigger, KHÔNG cần sửa

### Established Patterns
- State object pattern: `state.emas`, `state.atr`, `state.vol_sma_20`, `state.htf_trend`, `state.current_session`
- Signal results stored in `state.transient_signals` dict — indicators và events đều ghi vào đây
- Pub/sub payload format: `{"type", "symbol", "t", "data"}` — data chứa `signals` dict
- Telegram HTML format với emoji prefix, bold labels, 4095 char limit

### Integration Points
- `live_engine.py` — Nơi signal calculation → transient_signals → evaluate_ai_trigger_events → publish_signal_event. Đây là nơi thêm indicator snapshot building
- `formatters.py` — Nơi format message cho Telegram. Cần thêm section indicator snapshot
- `signal_factory.py` — Nơi create signal set, cần validate signal_type attribute

### Key Insight: `build_snapshot()` trong `snapshot_utils.py`
Function này đã collect TẤT CẢ indicator values từ state — EMA, ATR, Volume SMA, HTF Trend, Session. Có thể reuse pattern này để build indicator snapshot cho Telegram notification mà không cần viết lại logic thu thập.
</code_context>

<specifics>
## Specific Ideas

- Indicator snapshot nên nhóm EMA values chung thành 1 line để tiết kiệm space: `EMA(21/34/55/89/100/200): 2340/2342/2345/2350/2355/2370`
- Cross events nên có visual marker: 📈 cho cross up, 📉 cho cross down
- Telegram message format hiện tại đã có "Active Signals" section — indicator snapshot thêm section mới "📈 Indicator Snapshot" để phân biệt rõ ràng
</specifics>

<deferred>
## Deferred Ideas

- Smart selection (chỉ indicators "đáng chú ý") — deferred, phase này dùng all-inclusive approach
- Configurable indicator subset qua config file — deferred, có thể thêm sau nếu cần
- Indicator-only notification mode (notification khi indicator cross mà không cần event) — future phase
- Indicator alert thresholds (alert khi ATR vượt ngưỡng, EMA cross đặc biệt) — future phase

### Reviewed Todos (not folded)
- None — analysis stayed within phase scope
</deferred>

---

*Phase: 40-signal-classification-indicator-event-based*
*Context gathered: 2026-04-12*
