# Step 5: Trade Markers + Equity Curve

> **Phase**: F — Backtest Chart UI  
> **Thời gian**: ~1 giờ | **Risk**: Thấp  
> **Input**: `trades[]`, `equity_curve[]` từ API  
> **Output**: Trade markers trên BacktestChart + `EquityCurve.tsx` component

---

## Mô tả

Hai tính năng nhỏ nhóm chung:
1. **Trade markers**: Entry/exit points + SL/TP lines trên main chart
2. **Equity curve**: Thay SVG polyline bằng lightweight-charts area chart

## Part A: Trade Markers

### Checklist
- [ ] Entry markers: circle tại entry_time/entry_price
  - [ ] BUY = green, SELL = red
- [ ] Exit markers: circle tại exit_time/exit_price
  - [ ] Win = green, Loss = red  
  - [ ] Color intensity theo magnitude
- [ ] SL/TP horizontal dashed lines (entry → exit period)
  - [ ] SL = red dashed, TP = green dashed
  - [ ] Dùng LineSeries với lineStyle: 2 (dashed)
- [ ] Connection line giữa entry ↔ exit (optional, subtle)

### Test
- Backtest có 5 trades → 5 cặp entry/exit markers trên chart
- Zoom vào 1 trade → verify SL/TP lines ở đúng price level
- Win trade: green entry + green exit, Loss trade: green entry + red exit

## Part B: Equity Curve Component

### Checklist
- [ ] File `EquityCurve.tsx`
- [ ] Dùng lightweight-charts AreaSeries
- [ ] Data: `equity_curve: [{time, balance}]`
- [ ] Color: green area khi balance > 0, red khi < 0 (baseline series)
- [ ] Tooltip on hover: hiển thị balance value
- [ ] Auto-scale
- [ ] Compact sizing (h-48)

### Test
```typescript
<EquityCurve data={[
    { time: 1000, value: 0 },
    { time: 2000, value: 0.005 },
    { time: 3000, value: -0.002 },
    { time: 4000, value: 0.012 },
]} />
```
- Verify: area chart renders
- Verify: positive area green, negative area red
- Hover → tooltip shows balance

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Trade entry markers visible trên chart | [ ] |
| 2 | Trade exit markers visible | [ ] |
| 3 | SL/TP dashed lines render | [ ] |
| 4 | Color coding đúng (win/loss) | [ ] |
| 5 | Equity curve renders area chart | [ ] |
| 6 | Equity tooltip shows balance | [ ] |
