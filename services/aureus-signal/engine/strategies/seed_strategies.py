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
            "name": "TREND_CONT_BULL",
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS", "value": 500},
                    "tp": {"type": "RR_RATIO", "value": 3.0},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "TREND_CONT_BEAR",
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS", "value": 500},
                    "tp": {"type": "RR_RATIO", "value": 2.0},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "ORDER_FLOW_BULL",
            "description": "Specialized Trend Continuation focusing on Session Liquidity Sweeps with tighter stops.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]},
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS", "value": 500},
                    "tp": {"type": "RR_RATIO", "value": 2.5},
                    "trailing": {"type": "BREAKEVEN", "activation_pips": 300},
                    "capital_risk_pct": 0.5,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "ORDER_FLOW_BEAR",
            "description": "Specialized Trend Continuation focusing on Session Liquidity Sweeps with tighter stops.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 3.5, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]},
                    {"tag": "sweep_bear", "weight": 5.0, "required": True, "max_wait": 10, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS", "value": 500},
                    "tp": {"type": "RR_RATIO", "value": 2.5},
                    "trailing": {"type": "BREAKEVEN", "activation_pips": 300},
                    "capital_risk_pct": 0.5,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "SESSION_SWEEP_BULL",
            "description": "Dominance-based strategy. Massive OB imbalance with trend alignment and sweep trigger.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS", "value": 500},
                    "tp": {"type": "RR_RATIO", "value": 4.0},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.5,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "SESSION_SWEEP_BEAR",
            "description": "Dominance-based strategy. Massive OB imbalance with trend alignment and sweep trigger.",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bear", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "size": 0.01,
                    "sl": {"type": "FIXED_PIPS", "value": 500},
                    "tp": {"type": "RR_RATIO", "value": 4.0},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.5,
                    "early_exits": ["choch_up"]
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

        # --- Auto-assign strategies to symbols if no assignments exist ---
        try:
            existing_count = await conn.fetchval("SELECT COUNT(*) FROM aureus_symbol_strategies")
            if existing_count == 0:
                symbols_env = os.getenv("SYMBOLS", "XAUUSD")
                symbols_list = [s.strip() for s in symbols_env.split(",") if s.strip()]

                all_templates = await conn.fetch("SELECT id, name FROM aureus_strategy_templates")
                assigned = 0
                for tmpl in all_templates:
                    for symbol in symbols_list:
                        await conn.execute(
                            """
                            INSERT INTO aureus_symbol_strategies (symbol, strategy_id, is_active)
                            VALUES ($1, $2, true)
                            ON CONFLICT (symbol, strategy_id) DO NOTHING
                            """,
                            symbol, tmpl["id"]
                        )
                        assigned += 1
                logger.info(
                    f"[GLOBAL] [seed_system_strategies] Auto-assigned {assigned} strategy-symbol pairs "
                    f"({len(all_templates)} strategies × {len(symbols_list)} symbols)"
                )
            else:
                logger.info(
                    f"[GLOBAL] [seed_system_strategies] {existing_count} existing assignments found, skipping auto-assign"
                )
        except Exception as e:
            logger.error(f"[GLOBAL] [seed_system_strategies] Error during auto-assign: {e}")

if __name__ == "__main__":
    # For manual testing
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    
    async def run():
        pool = await asyncpg.create_pool(db_dsn)
        await seed_system_strategies(pool)
        await pool.close()
        
    asyncio.run(run())
