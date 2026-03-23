# Step 2: Signal Event Markers trên Chart

> **Phase**: F — Backtest Chart UI  
> **Thời gian**: ~1 giờ | **Risk**: Thấp  
> **Input**: `signalEvents[]` từ API  
> **Output**: Colored markers trên chart cho mỗi event

---

## Mô tả

Map từng signal event thành marker trên chart. Mỗi loại event có icon, color, position riêng. Markers merge với swing point markers (dedup by time).

## Marker Config

```typescript
const SIGNAL_MARKER_CONFIG: Record<string, MarkerConfig> = {
    choch_up:           { shape: 'arrowUp',   color: '#00E676', position: 'belowBar', text: 'CHOCH↑' },
    choch_down:         { shape: 'arrowDown', color: '#FF5252', position: 'aboveBar', text: 'CHOCH↓' },
    bos_up:             { shape: 'arrowUp',   color: '#29B6F6', position: 'belowBar', text: 'BOS↑' },
    bos_down:           { shape: 'arrowDown', color: '#FF7043', position: 'aboveBar', text: 'BOS↓' },
    sweep_bull:         { shape: 'circle',    color: '#FFD740', position: 'belowBar', text: 'SWEEP' },
    sweep_bear:         { shape: 'circle',    color: '#FF80AB', position: 'aboveBar', text: 'SWEEP' },
    ema_21_cross_up:    { shape: 'square',    color: '#69F0AE', position: 'belowBar', text: 'EMA↑' },
    ema_21_cross_down:  { shape: 'square',    color: '#FF8A80', position: 'aboveBar', text: 'EMA↓' },
};
```

## Checklist

- [ ] Marker config object với tất cả event types
- [ ] `buildSignalMarkers(signalEvents)` → marker array
- [ ] Merge với swing point markers (dedup cùng time)
- [ ] `createSeriesMarkers()` hiển thị markers
- [ ] Markers visible khi zoom in/out
- [ ] Toggle: show/hide signal markers

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | CHOCH markers hiển thị đúng vị trí (above/below) | [ ] |
| 2 | BOS markers hiển thị với màu khác CHOCH | [ ] |
| 3 | Sweep markers hiển thị circle shape | [ ] |
| 4 | Text labels readable khi zoom in | [ ] |
| 5 | No duplicate markers cùng time | [ ] |
| 6 | Toggle on/off hoạt động | [ ] |

## Test

- Load backtest có ≥ 5 events → verify 5 markers trên chart
- Toggle off "Signal Markers" → markers biến mất
- Zoom vào 1 marker → verify text + color đúng
