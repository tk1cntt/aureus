# Step 4: Signal Quality Scorecard Panel

> **Phase**: F — Backtest Chart UI  
> **Thời gian**: ~45 phút | **Risk**: Thấp  
> **Input**: `signal_quality[]` từ API  
> **Output**: `services/aureus-dashboard/web/src/components/SignalQualityCard.tsx`

---

## Mô tả

Panel bên phải chart hiển thị quality metrics cho từng signal type. Progress bar color-coded, letter grade, click to filter markers.

## Checklist

- [ ] Component `SignalQualityCard.tsx`
- [ ] Props: `quality: SignalQualityItem[], onSelectSignal?: (tag) => void`
- [ ] Per signal row:
  - [ ] Icon + color (từ SIGNAL_MARKER_CONFIG)
  - [ ] Signal name (choch_up → "CHOCH ↑")
  - [ ] Count badge
  - [ ] Win rate progress bar (green >70%, yellow 50-70%, red <50%)
  - [ ] Avg pips (+/- with color)
  - [ ] Letter grade badge (A+ → D)
- [ ] Sorted by quality (best first)
- [ ] Click row → `onSelectSignal(tag)` để filter chart markers
- [ ] Selected state highlight (border glow)
- [ ] "All" button to reset filter
- [ ] Responsive (collapse on small screen)

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Scorecard hiển thị tất cả signal types | [ ] |
| 2 | Progress bar width đúng theo win_rate | [ ] |
| 3 | Colors phân biệt rõ (green/yellow/red) | [ ] |
| 4 | Grade badge hiển thị đúng | [ ] |
| 5 | Sort by quality descending | [ ] |
| 6 | Click signal → callback fired | [ ] |
| 7 | Responsive layout | [ ] |

## Test

```typescript
<SignalQualityCard
    quality={[
        { tag: "sweep_bull", count: 12, win_rate: 83.3, avg_pips: 12.4, grade: "A+" },
        { tag: "choch_up", count: 23, win_rate: 73.9, avg_pips: 8.2, grade: "A" },
        { tag: "bos_up", count: 31, win_rate: 48.4, avg_pips: 2.3, grade: "C" },
    ]}
    onSelectSignal={(tag) => console.log("Selected:", tag)}
/>
```

- Verify: Sweep > CHOCH > BOS order
- Verify: Sweep bar green, BOS bar yellow/red
- Click Sweep → console logs "Selected: sweep_bull"
