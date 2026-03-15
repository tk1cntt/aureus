import asyncio
import asyncpg
import json
from datetime import datetime, timezone

async def clone():
    conn = await asyncpg.connect('postgresql://aureus:aureus_password@localhost:5432/aureus')
    
    symbol = 'XAUUSD'
    # Range: 2026-03-03 12:00 to 14:00 UTC
    start_time = datetime(2026, 3, 3, 12, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 3, 3, 14, 0, 0, tzinfo=timezone.utc)
    
    # Mock data for UI stats
    stats = {
        "total_trades": 1,
        "win_rate": 100.0,
        "total_pnl": 12.5,
        "best_trade": 12.5,
        "worst_trade": 12.5,
        "profit_factor": 0.0,
        "max_drawdown": 0.0
    }
    
    trades = [
        {
            "strategy_name": "SMC_Confirm_V1",
            "side": "BUY",
            "entry_price": 2870.50,
            "exit_price": 2883.00,
            "entry_time": int(start_time.timestamp()) + 300,
            "exit_time": int(start_time.timestamp()) + 1800,
            "exit_reason": "TP",
            "pnl": 12.5,
            "signal_context": {"session": "LONDON", "htf_trend": "BULLISH"}
        }
    ]
    
    equity_curve = [
        {"time": int(start_time.timestamp()), "value": 10000},
        {"time": int(start_time.timestamp()) + 1800, "value": 10012.5}
    ]
    
    signal_quality = [
        {"tag": "choch_up", "count": 2, "win_rate": 100.0, "avg_pips": 12.5, "trade_rate": 50.0, "grade": "A+"},
        {"tag": "sweep_bull", "count": 1, "win_rate": 100.0, "avg_pips": 12.5, "trade_rate": 100.0, "grade": "A+"}
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
    
    print(f"Created backtest run #{run_id} for {symbol} from {start_time} to {end_time}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(clone())
