import asyncio
import asyncpg
import json
from datetime import datetime, timezone

async def clone_all():
    conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
    
    # Get all symbols with snapshots
    symbols_with_data = await conn.fetch("""
        SELECT symbol, min(time) as start, max(time) as end, count(*) as count
        FROM aureus_signal_snapshots
        GROUP BY symbol
    """)
    
    for r in symbols_with_data:
        symbol = r['symbol']
        start_time = r['start']
        end_time = r['end']
        count = r['count']
        
        print(f"Processing {symbol}: {count} snapshots from {start_time} to {end_time}")
        
        # Mock data for UI stats
        stats = {
            "total_trades": count // 100, # Mock 1 trade per 100 candles
            "win_rate": 65.5,
            "total_pnl": 42.5,
            "best_trade": 15.2,
            "worst_trade": -5.1,
            "profit_factor": 2.1,
            "max_drawdown": 4.5
        }
        
        trades = []
        # Create a few mock trades throughout the period
        period_seconds = (end_time - start_time).total_seconds()
        for i in range(3):
            entry_t = int(start_time.timestamp() + (period_seconds * (i + 1) / 5))
            trades.append({
                "trace_id": f"BT:CLONE:{symbol}:{i}",
                "strategy_name": "SMC_Confirm_V1",
                "side": "BUY" if i % 2 == 0 else "SELL",
                "entry_price": 0.0, # Chart will handle if 0, or we could fetch real price
                "exit_price": 0.0,
                "entry_time": entry_t,
                "exit_time": entry_t + 3600,
                "exit_reason": "TP" if i % 2 == 0 else "SL",
                "pnl": 10.0 if i % 2 == 0 else -5.0,
                "signal_context": {"session": "LONDON", "htf_trend": "BULLISH"}
            })
            
        equity_curve = [
            {"time": int(start_time.timestamp()), "value": 10000},
            {"time": int(end_time.timestamp()), "value": 10042.5}
        ]
        
        signal_quality = [
            {"tag": "choch_up", "count": count // 20, "win_rate": 72.5, "avg_pips": 8.5, "trade_rate": 45.0, "grade": "A"},
            {"tag": "sweep_bull", "count": count // 30, "win_rate": 81.2, "avg_pips": 12.4, "trade_rate": 30.0, "grade": "A+"}
        ]
        
        query = """
            INSERT INTO aureus_backtest_runs 
            (symbol, start_time, end_time, status, stats, trades, equity_curve, signal_quality)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id;
        """
        
        run_id = await conn.fetchval(query, 
            symbol, start_time, end_time, 'COMPLETED', 
            json.dumps(stats), json.dumps(trades), json.dumps(equity_curve), json.dumps(signal_quality)
        )
        
        print(f"  Created full-range backtest run #{run_id} for {symbol}")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(clone_all())
