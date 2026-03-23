# Step 6: Redesign Backtest Page Layout

> **Phase**: F — Backtest Chart UI  
> **Thời gian**: ~1.5 giờ | **Risk**: Thấp  
> **Input**: Tất cả components từ Steps 1-5 + API endpoints từ Phase E  
> **Output**: Trang backtest hoàn chỉnh tại `/backtest`

---

## Mô tả

Tích hợp tất cả components vào trang backtest. Redesign layout, thêm precompute controls, kết nối API.

## Layout

```
┌───────────────────────────────────────────────────────────────┐
│ Header: Strategy Backtester v2                                │
├───────────────────────────────────────────────────────────────┤
│ Controls Row:                                                 │
│ [Symbol ▼] [Start Date] [End Date] [Strategy ▼] [▶ Run]      │
│ Pre-compute: [▶ Compute] [████████░░ 78%] [Status: Ready]    │
├───────────────────────────────────┬───────────────────────────┤
│                                   │ Signal Quality Scorecard  │
│   BacktestChart (65%)            │ (sortable, clickable)     │
│   - Candlesticks + ZigZag       │                           │
│   - OBs + CHOCH lines           │ ─────────────────────     │
│   - Signal Event Markers ◆●▲    │ Stats Cards:              │
│   - Trade Entry/Exit ▶◀         │ Win Rate | Pips | Trades  │
│   - SL/TP Lines ─ ─ ─           │                           │
│   - Hover Tooltip               │ ─────────────────────     │
│                                   │ Equity Curve (area chart) │
├───────────────────────────────────┤                           │
│ Trade Log Table                   │                           │
│ - Click trade → scroll to chart  │                           │
└───────────────────────────────────┴───────────────────────────┘
```

## State Management

```typescript
const [precomputeStatus, setPrecomputeStatus] = useState<PrecomputeStatus | null>(null);
const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
const [chartData, setChartData] = useState<ChartData | null>(null);
const [selectedSignal, setSelectedSignal] = useState<string | null>(null);
const [isRunning, setIsRunning] = useState(false);
```

## Data Flow

```
1. User clicks "Compute" → POST /precompute → poll status → show progress
2. User clicks "Run Backtest" → POST /backtest/v2 → poll status → get run_id
3. On completion: GET /backtest/{run_id}/chart-data → setChartData
4. Chart renders candles + signals + trades
5. User hover → tooltip from chartData.signal_events
6. User click signal type → setSelectedSignal → filter markers
7. User click trade → scroll chart to trade entry time
```

## Checklist

- [ ] Pre-compute controls:
  - [ ] "Compute" button triggers POST /precompute
  - [ ] Progress bar polls GET /precompute/status
  - [ ] Status badge: "Ready" / "Computing..." / "Done"
- [ ] Backtest controls:
  - [ ] Symbol selector (from SymbolsContext)
  - [ ] Date range picker
  - [ ] Strategy selector (optional)
  - [ ] Run button with loading state
- [ ] Chart area:
  - [ ] BacktestChart component (Step 1)
  - [ ] Signal markers (Step 2)
  - [ ] Signal tooltip (Step 3)
  - [ ] Trade markers (Step 5)
- [ ] Right panel:
  - [ ] SignalQualityCard (Step 4)
  - [ ] Stats cards (win_rate, pips, trades, sharpe)
  - [ ] EquityCurve (Step 5)
- [ ] Trade log table:
  - [ ] Click trade → chart scrolls to entry time
  - [ ] Highlight selected trade row
  - [ ] Show signal context per trade
- [ ] Responsive layout (grid collapse on small screen)
- [ ] Loading / empty states
- [ ] Error handling + user-friendly messages

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Pre-compute flow: button → progress → done | [ ] |
| 2 | Backtest flow: params → run → chart + results | [ ] |
| 3 | Chart hiển thị tất cả overlays | [ ] |
| 4 | Signal markers hiển thị + hover tooltip | [ ] |
| 5 | Signal quality scorecard renders | [ ] |
| 6 | Click signal type → filter markers | [ ] |
| 7 | Trade log click → chart scrolls | [ ] |
| 8 | Equity curve renders | [ ] |
| 9 | Stats cards accurate | [ ] |
| 10 | Page responsive | [ ] |
| 11 | Error states handled gracefully | [ ] |

## Test E2E — Full Flow

```
1. Navigate to /backtest
2. Verify empty state (no results)
3. Click "Compute 1 month" → verify progress bar animates
4. Wait for completion → status shows "Ready"
5. Select XAUUSD, Feb 20-27
6. Click "Run Backtest" → loading state
7. Wait for completion → chart appears
8. Verify: candles + zigzag + OBs + signal markers visible
9. Hover a CHOCH marker → verify tooltip pops up with metadata
10. Click "CHOCH ↑" in quality panel → only CHOCH markers shown
11. Click "All" → all markers return
12. Click a trade in trade log → chart scrolls to entry
13. Verify equity curve renders with correct shape
14. Verify stats match trade outcomes
15. Resize browser → layout responsive
```
