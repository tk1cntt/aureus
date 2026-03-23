# Step 1: Tạo BacktestChart Component

> **Phase**: F — Backtest Chart UI  
> **Thời gian**: ~1.5 giờ | **Risk**: Thấp (new component, không đụng existing)  
> **Input**: `SMCChart.tsx` (reference), API endpoint `/backtest/{id}/chart-data`  
> **Output**: `services/aureus-dashboard/web/src/components/BacktestChart.tsx`

---

## Mô tả

Tạo chart component mới extend từ SMCChart. Giống SMCChart nhưng: data load từ API thay vì WebSocket, thêm signal event markers, thêm trade markers, không auto-follow (static period).

## Checklist

- [ ] File `BacktestChart.tsx` tồn tại
- [ ] Props: `candles, smcState, signalEvents, trades`
- [ ] Candlestick chart (giống SMCChart)
- [ ] ZigZag overlay (giống SMCChart)
- [ ] Order Block zones (giống SMCChart)
- [ ] CHOCH dotted lines (giống SMCChart)
- [ ] HH/LL/LH/HL markers (giống SMCChart)
- [ ] Signal event markers (MỚI — xem Step 2)
- [ ] Trade markers (MỚI — xem Step 3)
- [ ] No auto-follow (static data)
- [ ] Chart fills container (responsive)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Chart renders candles đúng | [ ] |
| 2 | ZigZag + OBs + CHOCH hiển thị | [ ] |
| 3 | Chart responsive (resize OK) | [ ] |
| 4 | Zoom/pan hoạt động | [ ] |

## Test

```typescript
// In backtest/page.tsx
<BacktestChart
    candles={chartData.candles}
    smcState={{ swing_points: chartData.swing_points, obs: chartData.obs }}
    signalEvents={chartData.signal_events}
    trades={chartData.trades}
/>
```

- Load page → chart renders với candles
- Scroll/zoom → smooth
- Resize browser → chart responsive
