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
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 6.5,
            "config": {
                "min_score_threshold": 6.5,
                "context_filters": [
                    {"type": "trend_alignment", "required_trend": "BULLISH"},
                    {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]},
                    {"type": "ema_alignment", "required_slope": "POSITIVE", "period": 21}
                ],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 15, "reset_signals": ["choch_down"]},
                    {"tag": "fvg_bull", "weight": 2.0, "required": False, "max_wait": 10}
                ],
                "trade_execution": {
                    "size": 2.0,
                    "sl": {"type": "FIXED_PIPS", "value": 15},
                    "tp": {"type": "RR_RATIO", "value": 3.0},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 20},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "SESSION_SWEEP",
            "description": "Specialized Trend Continuation focusing on Session Liquidity Sweeps with tighter stops.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [
                    {"type": "trend_alignment", "required_trend": "BULLISH"},
                    {"type": "session_active", "allowed": ["LONDON", "NEW_YORK"]}
                ],
                "sequence": [
                    {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "size": 1.5,
                    "sl": {"type": "FIXED_PIPS", "value": 10},
                    "tp": {"type": "RR_RATIO", "value": 2.5},
                    "trailing": {"type": "BREAKEVEN", "activation_pips": 15},
                    "capital_risk_pct": 0.5,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "ORDER_FLOW_DOM",
            "description": "Dominance-based strategy. Massive OB imbalance with trend alignment and sweep trigger.",
            "min_score": 7.0,
            "config": {
                "min_score_threshold": 7.0,
                "context_filters": [
                    {"type": "trend_alignment", "required_trend": "BULLISH"},
                    {"type": "ob_imbalance", "min_ratio": 3.0, "lookback": 10},
                    {"type": "session_active", "allowed": ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]}
                ],
                "sequence": [
                    {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "size": 3.0,
                    "sl": {"type": "FIXED_PIPS", "value": 12},
                    "tp": {"type": "RR_RATIO", "value": 4.0},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 15},
                    "capital_risk_pct": 1.5,
                    "early_exits": ["choch_down"]
                }
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
