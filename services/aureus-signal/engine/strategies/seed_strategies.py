import asyncio
import os
import json
import logging
from engine.logging_common import get_logger
import asyncpg
from dotenv import load_dotenv

logger = get_logger(__name__)
async def seed_system_strategies(pool):
    """
    Seeds the database with system-default strategy templates.
    Ensures that specialized strategies are always available for assignment.
    """
    strategies = [
        {
            "name": "TREND_CONT",
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment and pull-back sweep.",
            "min_score": 6.5,
            "config": {
                "allowed_sessions": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"],
                "session_bonus": 1.5,
                "lookback_candles": 20,
                "ema_alignment_bonus": 0.5,
                "min_score_threshold": 60
            }
        },
        {
            "name": "SESSION_SWEEP",
            "description": "Specialized Trend Continuation focusing on Session Liquidity Sweeps.",
            "min_score": 6.0,
            "config": {
                "allowed_sessions": ["LONDON", "NEW_YORK"],
                "session_bonus": 2.0,
                "lookback_candles": 15,
                "ema_alignment_bonus": 0.3,
                "min_score_threshold": 55
            }
        },
        {
            "name": "ORDER_FLOW_DOM",
            "description": "Dominance-based strategy. Massive imbalance in Bullish/Bearish OBs with trend alignment.",
            "min_score": 7.0,
            "config": {
                "min_ob_ratio": 3.0,
                "lookback_obs": 10,
                "min_score_threshold": 65
            }
        }
    ]

    async with pool.acquire() as conn:
        for strat in strategies:
            try:
                # UPSERT based on Name
                query = """
                    INSERT INTO aureus_strategy_templates (name, description, config, min_score)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (name) DO UPDATE 
                    SET description = EXCLUDED.description,
                        config = EXCLUDED.config,
                        min_score = EXCLUDED.min_score
                """
                await conn.execute(
                    query, 
                    strat['name'], 
                    strat['description'], 
                    json.dumps(strat['config']), 
                    strat['min_score']
                )
                logger.info(f"[GLOBAL] [seed_system_strategies] 1... Seeded/Updated strategy: {strat['name']}")
            except Exception as e:
                logger.error(f"[GLOBAL] [seed_system_strategies] Error: Failed to seed strategy {strat['name']}: {e}")

if __name__ == "__main__":
    # For manual testing
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    
    async def run():
        pool = await asyncpg.create_pool(db_dsn)
        await seed_system_strategies(pool)
        await pool.close()
        
    asyncio.run(run())
