# Step 2: Signal Quality Calculator

> **Phase**: E — Backtest Engine v2  
> **Thời gian**: ~30 phút | **Risk**: Thấp  
> **Input**: Backtest results (trades + snapshots)  
> **Output**: Quality scorecard per signal type

---

## Mô tả

Tính quality metrics cho từng loại signal để đánh giá signal nào hiệu quả. Algorithm: correlate signal appearance → trade outcome trong lookahead window.

## Checklist

- [ ] Function `calculate_signal_quality(snapshots, trades, signal_tag, lookahead=30)`
- [ ] Function `calculate_all_signal_quality(snapshots, trades)` → list of scores
- [ ] Metrics per signal:
  - [ ] `count`: Tổng số lần xuất hiện
  - [ ] `win_rate`: % trades win khi signal xuất hiện
  - [ ] `avg_pips`: Average pips per appearance
  - [ ] `trade_rate`: % signal dẫn tới trade (vs no trade)
  - [ ] `grade`: Letter grade (A+ to D)
- [ ] Handle edge cases: 0 trades, 0 signals
- [ ] Sort by quality descending

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | Returns list of dicts với expected keys | [ ] |
| 2 | Win rate trong range 0-100% | [ ] |
| 3 | Grade mapping đúng (>80%=A+, >70%=A, ...) | [ ] |
| 4 | Empty trades → graceful (0% win rate, grade D) | [ ] |
| 5 | Multiple signal types đều có scores | [ ] |

## Test

```python
# Unit test with mock data
from engine.quality_calculator import calculate_all_signal_quality

mock_snapshots = [
    {"time": 100, "events": [{"tag": "choch_up"}]},
    {"time": 200, "events": [{"tag": "sweep_bull"}]},
    {"time": 300, "events": [{"tag": "choch_up"}]},
]

mock_trades = [
    {"entry_time": 105, "pnl": 0.005},  # Win after choch_up
    {"entry_time": 210, "pnl": 0.008},  # Win after sweep
    {"entry_time": 310, "pnl": -0.003}, # Loss after choch_up
]

quality = calculate_all_signal_quality(mock_snapshots, mock_trades)
for q in quality:
    print(f"{q['tag']}: win={q['win_rate']:.0f}%, avg={q['avg_pips']:.4f}, grade={q['grade']}")
# Expect:
#   sweep_bull: win=100%, grade=A+
#   choch_up: win=50%, grade=B
```
