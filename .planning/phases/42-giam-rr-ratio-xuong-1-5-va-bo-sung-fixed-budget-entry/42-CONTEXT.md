# Phase 42: Giảm RR ratio xuống 1.5 và bổ sung FIXED_BUDGET entry (50$) - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning
**Updated:** 2026-04-14 (discuss-phase — 3 decisions mới từ discussion)

<domain>
## Phase Boundary

Chuyển TP RR ratio mặc định của tất cả strategy từ 2.0 xuống 1.5. Bổ sung cơ chế FIXED_BUDGET ($50) tự tính lot size dựa trên SL distance và entry price thực tế khi gửi lệnh sang MT5.

**Lý do giảm RR:**
- RR 2.0 yêu cầu giá di chuyển xa hơn để chạm TP → giảm win rate
- RR 1.5 cho phép take profit sớm hơn, phù hợp với scalping/intraday
- Still profitable với win rate > 40% (break-even ở ~40% với RR 1.5)

**Lý do FIXED_BUDGET:**
- Thay vì fix lot size (0.01) → fix số tiền rủi ro ($50)
- MT5 tự tính lot = budget / (SL_distance × contract_size)
- Dùng giá Ask/Bid thực tế tại thời điểm vào lệnh (chứ không phải giá close candle dự đoán)
- Rủi ro đồng nhất giữa các lệnh, bất kể SL rộng hay hẹp
</domain>

<decisions>
## Implementation Decisions

### RR Ratio Reduction
- **D-01:** Tất cả seed strategy có `tp: { "type": "RR_RATIO", "value": 2.0 }` → chuyển xuống `1.5`
- **D-02:** SESSION_SWEEP_BEAR có RR 4.0 → cũng chuyển xuống 1.5 (không ngoại lệ)
- **D-03:** Chỉ thay đổi trong `seed_strategies.py` — logic tính TP trong `orders.py` và `simulated_orders.py` không đổi (vẫn đọc `value` từ config)
- **D-04:** Strategy cũ trong DB không bị ảnh hưởng — chỉ seed strategy mới có RR 1.5

### FIXED_BUDGET Entry Mode
- **D-05:** Đặt tên size mode là `RISK_FIXED_AMOUNT` (không phải `FIXED_BUDGET`) — nhất quán với ngữ nghĩa "risk amount" thay vì "budget"
- **D-06:** Giá trị `size_value` = số tiền rủi ro cố định (mặc định $50)
- **D-07:** Python KHÔNG tính lot — chỉ set `volume=0` làm placeholder, forward `size_mode` + `risk_amount` sang MT5
- **D-08:** MT5 tính lot từ giá Ask/Bid thực tế (không phải giá close candle) → chính xác hơn vì SL distance tính từ giá thực

### Lot Calculation trên MT5
- **D-09:** Công thức: `lot = riskAmount / (slDistance * contractSize)`
- **D-10:** Contract sizes hardcoded trong cả Python và MQL5:
  | Symbol | Contract Size |
  |--------|--------------|
  | Forex (XXX/YYY) | 100,000 units |
  | XAUUSD/GOLD | 100 oz |
  | XAGUSD/SILVER | 5,000 oz |
  | Indices (USTEC, US30, US500) | 1 unit |
  | Crypto (BTCUSD, ETHUSD) | 1 unit |
- **D-11:** MT5 normalize lot theo `SYMBOL_VOLUME_STEP`, clamp giữa MIN/MAX
- **D-12:** Nếu `riskAmount` null hoặc <= 0 → fallback $50

### Fallback khi SL/TP không tính được
- **D-13:** Khi `_calculate_sl_tp` trả về `None`, KHÔNG `continue` skip trigger → để `missing_keys` validation handle rejection
- **D-14:** Flow mới: xác định side → tính entry_price → tính SL/TP → validate → tạo order (thay vì validate trước rồi mới tính)

### Propagation qua các layer
- **D-15:** `signal_event_publisher.py`: thêm `risk_amount` vào strategy match event
- **D-16:** `order_builder.py` (aureus-trader): detect `RISK_FIXED_AMOUNT` → forward `size_mode` + `risk_amount` + set `volume=0`
- **D-17:** `registry.py`: thêm `risk_amount` vào trigger payload để có sẵn cho các bước sau

### Lot Volume Guard & Budget Adjustment (Discuss-phase decisions)
- **D-18:** Uniform $50 fallback — KHÔNG symbol-specific. Khi lot tính ra < SYMBOL_VOLUME_MIN → tự động tăng budget lên cho đủ min lot (e.g. $50 → $100 → $150 cho đến khi lot >= 0.01)
- **D-19:** Khi lot tính ra > SYMBOL_VOLUME_MAX → tự động giảm budget cho đủ max volume. KHÔNG reject signal. Chấp nhận rủi ro nhỏ hơn hoặc bằng budget dự định
- **D-20:** RR 1.5 uniform cho tất cả strategy — KHÔNG per-strategy override. Đơn giản, dễ quản lý. Nếu strategy nào thực sự cần RR khác thì config sau

### Claude's Discretion
- Contract size file `symbol_contracts.json` (Python load được, MQL5 hardcoded)
- Log format cho lot calculation
- Fallback lot = 0.01 khi không tính được (Python) hoặc SYMBOL_VOLUME_MIN (MT5) — trước khi auto-adjust
</decisions>

<specifics>
## Specific Ideas

- "Tôi muốn rủi ro mỗi lệnh cố định $50 — không quan tâm SL rộng hay hẹp, tổng thiệt hại vẫn là $50"
- Lot calculation phải dùng giá thực tế tại thời điểm MT5 nhận lệnh, không phải giá dự đoán từ signal engine
- FIXED_PIPS vẫn là cơ chế SL hợp lệ — không bị thay thế bởi PIVOT_POINT
- RR 1.5 là để dễ hit TP hơn trong điều kiện market bình thường

</specifics>

<canonical_refs>
## Canonical References

### Signal Engine
- `services/aureus-signal/engine/orders.py` — SimulatedTradeManager, _calculate_sl_tp, lot calculation
- `services/aureus-signal/engine/simulated_orders.py` — Backtest version mirror
- `services/aureus-signal/engine/strategies/seed_strategies.py` — Seed strategy definitions với RR 1.5
- `services/aureus-signal/engine/strategies/registry.py` — Trigger payload với risk_amount
- `services/aureus-signal/engine/signal_event_publisher.py` — Strategy match event schema

### Order Execution
- `services/aureus-trader/order_builder.py` — OPEN_ORDER command builder với RISK_FIXED_AMOUNT forwarding
- `mql5/AureusProvider.mq5` — CalculateLotFromBudget(), ExecuteOpenOrder() với MT5-side lot calc

### Phase 41 (upstream)
- `.planning/phases/41-.../` — Entry price methods (CURRENT, PULLBACK_50, OB_EDGE, EMA_TOUCH, FIXED_OFFSET)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_calculate_entry_price()` từ phase 41 — được dùng trước khi tính SL/TP, đảm bảo entry_price chính xác cho entry method
- `VALID_SIZE_MODES` trong snapshot_utils — đã có `"FIXED_UNITS"` và `"RISK_PERCENT"`, thêm `"RISK_FIXED_AMOUNT"`

### Established Patterns
- Signal pipeline: strategy → registry → orders.py → signal_event_publisher → Redis → aureus-trader → MT5
- Mỗi layer cần forward đúng fields — RISK_FIXED_AMOUNT phải có mặt ở tất cả các bước
- Python fallback contract sizes, MQL5 hardcoded — có thể drift, cần sync thủ công

### Integration Points
- `orders.py` → `signal_event_publisher.py`: publish_strategy_match cần active_signals + risk_amount
- Redis pub/sub → aureus-trader: order_builder.py parse match event
- aureus-trader → MT5 TCP: OPEN_ORDER command với size_mode + risk_amount
- MT5 EA: parse JSON, detect RISK_FIXED_AMOUNT, calculate lot, execute OrderSend

</code_context>

<deferred>
## Deferred Ideas

- Dynamic budget theo account balance (hiện tại fix $50) — phase riêng
- Contract size auto-sync từ MT5 → backend (hiện tại hardcoded cả 2 bên) — Phase 999.1 trong backlog
- Risk-based RR adjustment (RR thay đổi theo điều kiện market) — ý tưởng tương lai
- Backtest lot calculation — simulated_orders.py chưa có logic tính lot từ budget (chỉ forward)

</deferred>

---

*Phase: 42-giam-rr-ratio-xuong-1-5-va-bo-sung-fixed-budget-entry*
*Context gathered: 2026-04-14*
