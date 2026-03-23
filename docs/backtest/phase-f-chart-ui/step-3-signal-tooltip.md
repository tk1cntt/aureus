# Step 3: Hover Tooltip — SignalTooltip Component

> **Phase**: F — Backtest Chart UI  
> **Thời gian**: ~1.5 giờ | **Risk**: Thấp  
> **Input**: Signal metadata từ snapshots, crosshair position  
> **Output**: `services/aureus-dashboard/web/src/components/SignalTooltip.tsx`

---

## Mô tả

Glassmorphism popup hiển thị khi crosshair hover gần signal marker. Hiển thị full event metadata, market context, và trade outcome (nếu có).

## Implementation Approach

1. Subscribe `chart.subscribeCrosshairMove(param)`
2. On move: check nếu `param.time` trùng với bất kỳ signal event time
3. Nếu match → hiển thị tooltip tại mouse position
4. Tooltip content lấy từ `signalEvents` array + `snapshots` data
5. Position: auto-flip khi gần edge (right/bottom)

## Checklist

- [ ] Component `SignalTooltip.tsx`
- [ ] Subscribe crosshair move
- [ ] Match time → signal event
- [ ] Tooltip layout:
  - [ ] Header: event type + icon + color indicator
  - [ ] Timestamp (formatted)
  - [ ] Event params: pivot_price, breakout_price, fidelity, etc.
  - [ ] Context: htf_trend, session, atr, ema_21
  - [ ] Outcome: win/loss/no-trade (nếu có trade data)
- [ ] Glassmorphism styling: `backdrop-blur-md bg-gray-900/80`
- [ ] Auto-position (flip at edges)
- [ ] Smooth appear/disappear animation
- [ ] Dismiss khi crosshair move away

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Hover gần CHOCH marker → tooltip xuất hiện | [ ] |
| 2 | Tooltip hiển thị event type đúng | [ ] |
| 3 | Tooltip hiển thị pivot_price (nếu có) | [ ] |
| 4 | Tooltip hiển thị context (trend, session) | [ ] |
| 5 | Tooltip hiển thị outcome (win/loss) | [ ] |
| 6 | Move away → tooltip disappear | [ ] |
| 7 | Tooltip không bị cut off ở edge | [ ] |

## Test

- Hover vào CHOCH marker → verify popup shows:
  - "◆ CHOCH UP" header
  - Timestamp
  - Pivot price: 2865.20
  - Context: BULLISH / LONDON
  - Result: ✅ Win (+8.5 pips)
- Hover vào Sweep marker → verify popup shows:
  - "● SWEEP BULL" header
  - Fidelity: 0.95
- Move cursor away → popup fades out
- Hover near right edge → popup flips to left side
