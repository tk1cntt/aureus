# TREND_CONT_BULL XAUUSD Review — 2026-05-07

## Scope

User request: compare 5 `TREND_CONT_BULL` trades today, inspect entry conditions from journal/snapshot tables, evaluate stored signal data, and extract lessons.

Data source:
- `aureus_trade_journal`
- `aureus_trade_signal_snapshots`
- Filter: `symbol='XAUUSD'`, `strategy_name='TREND_CONT_BULL'`, current DB day.

Actual count found: 5 trades.

## Result Summary

| Metric | Value |
|---|---:|
| Trades | 5 |
| Wins | 3 |
| Losses | 2 |
| Win rate | 60% |
| Total PnL | +71.55 |
| Avg win | +54.20 |
| Avg loss | -45.53 |

## Per-Trade Snapshot Comparison

Signal conventions from stored snapshot:
- Candle color: `1` bullish, `-1` bearish.
- CISD: `1` bullish, `-1` bearish.
- `entry_above_ema*` = entry price minus EMA. Larger positive value means entry is more extended above that EMA.

| ID | Trace | Entry UTC | Result | PnL | Entry | ATR | Vol SMA20 | Above EMA21 | Above EMA55 | Above EMA200 | D1 | H1 | M30 | M15 | M5 | CISD M5 | CISD M15 | CISD M30 | CISD H1 |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12081 | 1778121900 | 02:46 | LOSS | -45.45 | 4699.31 | 1.33 | 132.00 | 5.28 | 4.77 | 5.13 | 1 | -1 | -1 | 1 | 1 | -1 | -1 | 1 | 1 |
| 12139 | 1778142660 | 08:32 | WIN | +22.89 | 4701.41 | 1.54 | 234.55 | 3.83 | 3.61 | 1.35 | 1 | -1 | -1 | -1 | 1 | -1 | -1 | -1 | 1 |
| 12141 | 1778144520 | 09:03 | WIN | +69.92 | 4706.55 | 1.93 | 312.85 | 2.69 | 4.36 | 5.34 | 1 | 1 | 1 | -1 | -1 | -1 | 1 | -1 | 1 |
| 12161 | 1778151540 | 11:00 | WIN | +69.79 | 4743.43 | 2.24 | 454.25 | 1.77 | 3.30 | 17.78 | 1 | 1 | 1 | 1 | 1 | -1 | 1 | 1 | 1 |
| 12177 | 1778157780 | 12:44 | LOSS | -45.60 | 4738.94 | 1.97 | 368.15 | 2.81 | 3.42 | 6.41 | 1 | -1 | 1 | 1 | -1 | 1 | -1 | 1 | 1 |

## Winner vs Loser Pattern

| Feature | Winners Avg / Rate | Losers Avg / Rate | Read |
|---|---:|---:|---|
| Avg PnL | +54.20 | -45.53 | Wins payoff slightly larger than losses. |
| ATR | 1.90 | 1.65 | Winners happened with higher volatility. |
| Vol SMA20 | 333.88 | 250.08 | Winners had stronger volume context. |
| Entry above EMA21 | 2.76 | 4.04 | Losses chased farther above short EMA. |
| Entry above EMA200 | 8.16 | 5.77 | EMA200 distance alone not enough; trend strength helps but not decisive. |
| H1 bullish candle rate | 67% | 0% | Big difference: losses had bearish H1 candle. |
| M30 bullish candle rate | 67% | 50% | Mild edge for wins. |
| CISD M15 bullish rate | 67% | 0% | Strong difference: losses had bearish M15 CISD. |
| CISD M30 bullish rate | 33% | 100% | M30 CISD bullish alone did not save losses. |

## Trade Notes

### 12081 — LOSS

- Entry was highly extended above EMA21: `+5.28`, worst of 5.
- H1 and M30 candles were bearish.
- CISD M5/M15 bearish while only M30/H1 bullish.
- Read: bullish D1 + local M5 candle was not enough. Entry likely chased after move while HTF candle context opposed.

### 12139 — WIN, small

- Entry above EMA200 only `+1.35`, near long-term mean.
- H1/M30/M15 candles bearish; CISD mostly bearish except H1.
- Win was small: `+22.89`.
- Read: not high-quality by snapshot conditions, but lower extension reduced downside and allowed modest profit.

### 12141 — WIN, strong

- H1/M30 candles bullish; D1 bullish.
- Entry extension moderate above EMA21: `+2.69`.
- CISD M15 bullish while H1 bullish.
- Read: better alignment than earlier trades. Good balance: not too extended, HTF candle support present.

### 12161 — WIN, strong

- Best alignment: D1/H1/M30/M15/M5 all bullish.
- CISD M15/M30/H1 bullish; only M5 CISD bearish.
- Highest ATR/volume: ATR `2.24`, Vol SMA20 `454.25`.
- Entry above EMA21 lowest: `+1.77`, not chasing short EMA.
- Read: cleanest continuation setup. Strong trend + high participation + low short-EMA extension.

### 12177 — LOSS

- H1 candle bearish; M5 candle bearish.
- CISD M15 bearish while M5/M30/H1 bullish.
- Volume/ATR ok, but alignment mixed.
- Read: MTF conflict. Despite decent trend distance, local/HTF candle conflict and M15 CISD bearish warned against long continuation.

## Practical Lessons

1. **Do not rely on D1 bullish alone.** All 5 had D1 bullish; still 2 losses.
2. **H1 candle matters a lot for TREND_CONT_BULL.** Losses had `H1=-1`; winners had H1 bullish 2/3.
3. **M15 CISD bearish is dangerous for long continuation.** Losses both had `cisd_m15=-1`; strong winners had `cisd_m15=1`.
4. **Avoid chasing when entry is too far above EMA21.** Loss avg above EMA21 `+4.04`, winners `+2.76`; worst loss had `+5.28`.
5. **Best setup today:** high ATR/volume, H1+M30 bullish, M15 CISD bullish, and entry not too stretched above EMA21.
6. **M30 CISD alone is not enough.** Both losses had M30 CISD bullish, so it should not override bearish H1/M15 warnings.

## Suggested Rule-of-Thumb Filter To Consider

For `TREND_CONT_BULL`, consider stricter scoring or rejection when:

- `candle_color_h1 = -1` AND `cisd_m15 = -1`.
- `entry_price - ema_21` is high relative to ATR, e.g. `> 2x ATR`.
- H1 or M15 context conflicts while trade is already extended above EMA21.

From today's data:

- 12081: `entry_above_ema21 / ATR = 3.98x`, loss.
- 12177: `entry_above_ema21 / ATR = 1.43x`, loss, but H1/M5 candle and M15 CISD conflict.
- 12161: `entry_above_ema21 / ATR = 0.79x`, best aligned win.

## Data Quality Notes

- `score` is `0.00` for all 5 trades, so current persisted score is not useful for post-trade quality analysis.
- `active_signals` statuses are mostly `MISSING`; useful signal evidence mainly comes from `aureus_trade_signal_snapshots` numeric/categorical columns.
- `session` is blank for these older rows, despite later fix adding session persistence.
- `d1_poc/d1_vah/d1_val` are blank for these rows because they were created before D1 TPO persistence fix.

## Conclusion

Today `TREND_CONT_BULL` was profitable overall: **3W / 2L, +71.55 PnL**.

Best quality trade: **12161** — full candle alignment, strong ATR/volume, CISD M15/M30/H1 bullish, low EMA21 extension.

Main avoid pattern: **H1 bearish + M15 CISD bearish + stretched above EMA21**. This describes the worst loser 12081 and partially explains 12177.
