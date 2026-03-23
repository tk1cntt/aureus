# Phase F: Backtest Chart UI + Signal Quality

> **Độ khó**: ⭐⭐⭐⭐⭐ | **Ảnh hưởng Live**: Zero | **Thời gian**: 5-8 giờ  
> **Phụ thuộc**: Phase E (API endpoints + backtest results tồn tại)  
> **Mô tả**: Redesign trang Backtest với chart đầy đủ (giống realtime), thêm signal event markers, hover tooltips, trade markers, signal quality scorecard.

---

## Checklist tính năng

- [ ] `BacktestChart.tsx` — Extend SMCChart với signal markers + trade markers
- [ ] Signal event markers trên chart (CHOCH/BOS/Sweep/EMA Cross)
- [ ] Hover tooltip popup hiển thị chi tiết event + context + outcome
- [ ] Trade entry/exit markers + SL/TP dashed lines
- [ ] `SignalQualityCard.tsx` — Scorecard panel đánh giá chất lượng mỗi signal
- [ ] `EquityCurve.tsx` — Equity curve dùng lightweight-charts (thay SVG hiện tại)
- [ ] `SignalTimeline.tsx` — Horizontal timeline hiển thị signal occurrences
- [ ] Redesign `backtest/page.tsx` layout mới (chart + panels)
- [ ] Pre-compute trigger + progress UI
- [ ] Responsive layout

---

## Steps

### Step 1: Tạo `BacktestChart.tsx` — Chart với Signal Markers
- **File mới**: `services/aureus-dashboard/web/src/components/BacktestChart.tsx`
- **Mô tả**: Extend SMCChart component, thêm layer signal event markers + trade markers
- **Tính năng**:
  - Nhận thêm props: `signalEvents[]`, `trades[]`
  - Render signal markers dùng `createSeriesMarkers()` (giống swing point markers)
  - Render trade entry/exit markers  
  - Marker config mapping:
    | Tag | Shape | Color | Position |
    |:---|:---|:---|:---|
    | choch_up | arrowUp | #00E676 | belowBar |
    | choch_down | arrowDown | #FF5252 | aboveBar |
    | bos_up | arrowUp | #29B6F6 | belowBar |
    | bos_down | arrowDown | #FF7043 | aboveBar |
    | sweep_bull | circle | #FFD740 | belowBar |
    | sweep_bear | circle | #FF80AB | aboveBar |
- **Điều kiện hoàn thành**: Chart hiển thị candles + zigzag + OBs + signal markers
- **Test**: Load backtest data → verify markers xuất hiện đúng nến có event

### Step 2: Implement Hover Tooltip — `SignalTooltip.tsx`
- **File mới**: `services/aureus-dashboard/web/src/components/SignalTooltip.tsx`
- **Mô tả**: Glassmorphism popup khi hover gần marker
- **Tính năng**:
  - Subscribe `chart.subscribeCrosshairMove()` 
  - Khi crosshair gần marker (within 2 bars) → hiển thị tooltip
  - Tooltip content:
    - Event type + icon + color
    - Timestamp
    - Event-specific metadata (pivot price, breakout, fidelity, etc.)
    - Context tại thời điểm đó (HTF trend, session, ATR, EMA)
    - Outcome: trade win/loss/no trade nếu có
  - Position: theo vị trí mouse, auto-flip khi gần edge
  - Glassmorphism styling: `backdrop-blur-md bg-gray-900/80 border border-gray-700`
- **Điều kiện hoàn thành**: Hover cạnh marker → popup xuất hiện với đầy đủ metadata
- **Test**: Hover vào CHOCH marker → verify pivot_price, breakout_price hiển thị đúng

### Step 3: Trade Markers + SL/TP Lines
- **File**: Thêm vào `BacktestChart.tsx`
- **Mô tả**: Vẽ entry/exit points + SL/TP horizontal lines
- **Tính năng**:
  - Entry marker: circle tại entry_time/entry_price, BUY=green, SELL=red
  - Exit marker: circle tại exit_time/exit_price, Win=green, Loss=red
  - SL line: red dashed horizontal từ entry_time đến exit_time
  - TP line: green dashed horizontal từ entry_time đến exit_time
  - Color intensity theo P/L magnitude
- **Điều kiện hoàn thành**: Trades hiển thị rõ trên chart
- **Test**: Backtest có 5 trades → verify 5 cặp entry/exit markers

### Step 4: `SignalQualityCard.tsx`
- **File mới**: `services/aureus-dashboard/web/src/components/SignalQualityCard.tsx`
- **Mô tả**: Panel bên phải hiển thị quality scorecard
- **Tính năng**:
  - Hiển thị từng signal type: tag, count, win_rate, avg_pips, grade
  - Progress bar cho win_rate (color-coded: green >70%, yellow 50-70%, red <50%)
  - Letter grade: A+ (>80%), A (>70%), B+ (>60%), B (>50%), C (>40%), D (<40%)
  - Sort by quality descending
  - Click signal → highlight markers của signal đó trên chart
- **Điều kiện hoàn thành**: Scorecard hiển thị đúng data từ API
- **Test**: Verify win_rate tính đúng so với trades

### Step 5: `EquityCurve.tsx` — Chart dùng Lightweight Charts
- **File mới**: `services/aureus-dashboard/web/src/components/EquityCurve.tsx`
- **Mô tả**: Thay SVG polyline hiện tại bằng lightweight-charts area chart
- **Tính năng**:
  - Area chart (xanh khi balance > 0, đỏ khi < 0)
  - Tooltip hiển thị balance tại từng point
  - Auto-scale
  - Max drawdown shading
- **Điều kiện hoàn thành**: Equity curve interactive và đẹp hơn SVG
- **Test**: Load equity data → verify render đúng

### Step 6: Redesign `backtest/page.tsx`
- **File**: `services/aureus-dashboard/web/src/app/backtest/page.tsx`
- **Mô tả**: Redesign layout tích hợp tất cả components
- **Layout**:
  ```
  ┌─────────────────────────────────────────────────────────────┐
  │ Controls: [Symbol] [Start] [End] [Strategy ▼] [▶ Run]      │
  │ Pre-compute: [▶ Compute 6 months] [Progress: ████░ 78%]    │
  ├───────────────────────────────────────┬─────────────────────┤
  │ BacktestChart (70% width)            │ Signal Quality (30%) │
  │                                      │ Stats Cards          │
  ├───────────────────────────────────────┤ Equity Curve         │
  │ Trade Log Table                      │                      │
  └───────────────────────────────────────┴─────────────────────┘
  ```
- **State management**: 
  - `backtestResult` → chart data, trades, signal_quality
  - `precomputeStatus` → progress
  - `selectedSignal` → filter markers by signal type
- **Điều kiện hoàn thành**: Full page renders với tất cả components
- **Test**: Run backtest → verify tất cả panels cập nhật

---

## Điều kiện nghiệm thu Phase F

| # | Điều kiện | Verified? |
|:---|:---|:---|
| F1 | Chart hiển thị candles + zigzag + OBs (giống realtime) | [ ] |
| F2 | Signal event markers hiển thị đúng vị trí | [ ] |
| F3 | Hover tooltip hiển thị đầy đủ metadata | [ ] |
| F4 | Trade markers (entry/exit/SL/TP) render đúng | [ ] |
| F5 | Signal Quality Scorecard hiển thị data chính xác | [ ] |
| F6 | Equity curve render dùng lightweight-charts | [ ] |
| F7 | Pre-compute trigger + progress bar hoạt động | [ ] |
| F8 | Page responsive trên các kích thước màn hình | [ ] |
| F9 | Click signal type → filter markers trên chart | [ ] |
| F10 | Full flow: Pre-compute → Run Backtest → View Results hoạt động liền mạch | [ ] |

---

## Test End-to-End Phase F

```bash
# === Prerequisite: Phase A-E hoàn thành ===

# 1. Mở trang backtest
# Navigate to http://localhost:17222/backtest

# 2. Trigger pre-compute (nếu chưa có data)
# Click "Compute 6 months" → verify progress bar
# Wait for completion

# 3. Run Backtest
# Select: XAUUSD, 2026-02-01 → 2026-02-28
# Click "Start Simulation"
# Wait for completion

# 4. Visual Verification
# Chart hiển thị:
#   ✓ Candlesticks
#   ✓ ZigZag lines  
#   ✓ Order Block zones
#   ✓ Signal markers (colored icons)
#   ✓ Trade entry/exit points
#   ✓ SL/TP dashed lines

# 5. Hover Verification
# Hover vào CHOCH marker → tooltip hiện:
#   ✓ Event type + color
#   ✓ Timestamp
#   ✓ Pivot price, breakout price
#   ✓ Context (trend, session, ATR)
#   ✓ Outcome (win/loss/no trade)

# 6. Signal Quality Verification
# Scorecard panel hiện:
#   ✓ Từng signal type với count, win_rate, grade
#   ✓ Color-coded progress bars
#   ✓ Sorted by quality

# 7. Click signal type → verify chart filters markers

# 8. Equity curve:
#   ✓ Area chart renders
#   ✓ Color changes at profit/loss boundary
#   ✓ Tooltip shows balance on hover
```
