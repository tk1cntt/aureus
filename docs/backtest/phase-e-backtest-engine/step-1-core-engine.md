# Step 1: Implement BacktestRunnerV2 — Core Logic

> **Phase**: E — Backtest Engine v2  
> **Thời gian**: ~1.5 giờ | **Risk**: Thấp (code mới, không đụng live)  
> **Input**: Pre-computed data trong `aureus_signal_snapshots`  
> **Output**: `services/aureus-signal/engine/backtest_engine_v2.py`

---

## Mô tả

Class chính cho backtest mới: đọc snapshots + candles từ DB → rebuild state per-candle → evaluate strategies → quản lý orders (SL/TP).

## Checklist

- [ ] Class `BacktestRunnerV2(db_pool, strategy_registry)`
- [ ] Method `async run(symbol, start, end, strategy_ids=None) -> Dict`
- [ ] Verify snapshots tồn tại (count query)
- [ ] JOIN query: `aureus_candles` + `aureus_signal_snapshots`
- [ ] Per-candle loop:
  - [ ] Restore state từ snapshot (atr, emas, trend, regime, session)
  - [ ] Restore OBs từ `active_obs` JSONB
  - [ ] Inject events vào `signal_history` + `transient_signals`
  - [ ] `state.update_with_candle()` cho lifecycle
  - [ ] `strategy_registry.evaluate_all()` 
  - [ ] Order management: check SL/TP hits
  - [ ] Process new triggers → create orders
  - [ ] Clear `transient_signals`
- [ ] Result aggregation: trades list, equity_curve
- [ ] `_calculate_stats()`: total_trades, win_rate, total_pnl, avg_pips
- [ ] Isolated: dùng `SimulatedTradeManager` riêng, không Redis

## Điều kiện nghiệm thu

| # | Điều kiện | Pass? |
|:---|:---|:---|
| 1 | `run()` hoàn thành không error | [ ] |
| 2 | Returns dict có keys: trades, stats, equity_curve | [ ] |
| 3 | `trades` list không trống (strategies trigger) | [ ] |
| 4 | `stats.win_rate` trong range 0-100% | [ ] |
| 5 | Backtest 1 tuần < 5 giây | [ ] |
| 6 | Live system không bị ảnh hưởng | [ ] |

## Test

```python
# Direct test
import asyncio
from engine.backtest_engine_v2 import BacktestRunnerV2
from engine.strategies.registry import StrategyRegistry

async def test():
    db_pool = await asyncpg.create_pool(...)
    registry = StrategyRegistry(db_pool)
    await registry.load_from_db("XAUUSD")
    
    runner = BacktestRunnerV2(db_pool, registry)
    result = await runner.run("XAUUSD", "2026-02-20", "2026-02-27")
    
    print(f"Trades: {len(result['trades'])}")
    print(f"Win Rate: {result['stats']['win_rate']:.1f}%")
    print(f"Net PnL: {result['stats']['total_pnl']}")
    
    assert len(result['trades']) > 0, "Should have at least 1 trade"
    assert 'equity_curve' in result

asyncio.run(test())
```
