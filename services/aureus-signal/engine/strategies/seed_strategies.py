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
                    "direction": "BUY",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
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
                    "direction": "SELL",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
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
                    "direction": "BUY",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
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
                    "direction": "SELL",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
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
                    "direction": "BUY",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
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
                    "direction": "SELL",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.5,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "CHOCH_CISD_BULL",
            "description": "ChoCH lên xác nhận đảo chiều bullish, sau đó CISD bullish xác nhận break và entry. Sequence: choch_up → cisd_bull.",
            "min_score": 8.0,
            "config": {
                "min_score_threshold": 8.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
                    {"tag": "cisd_bull", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "CHOCH_CISD_BEAR",
            "description": "ChoCH xuống xác nhận đảo chiều bearish, sau đó CISD bearish xác nhận break và entry. Sequence: choch_down → cisd_bear.",
            "min_score": 8.0,
            "config": {
                "min_score_threshold": 8.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_up"]},
                    {"tag": "cisd_bear", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "CISD_CONSENSUS_BULL",
            "description": "CISD M30 + M15 + M5 đồng thuận bullish, trigger entry khi CISD M1 bullish fire. Multi-frame consensus strategy.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [
                    {
                        "type": "cisd_consensus",
                        "required_direction": "bullish",
                        "required_tfs": ["m30", "m15", "m5"]
                    }
                ],
                "sequence": [
                    {"tag": "cisd_bull", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["cisd_bear", "choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "CISD_CONSENSUS_BEAR",
            "description": "CISD M30 + M15 + M5 đồng thuận bearish, trigger entry khi CISD M1 bearish fire. Multi-frame consensus strategy.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [
                    {
                        "type": "cisd_consensus",
                        "required_direction": "bearish",
                        "required_tfs": ["m30", "m15", "m5"]
                    }
                ],
                "sequence": [
                    {"tag": "cisd_bear", "weight": 4.0, "required": True, "max_wait": 20, "reset_signals": ["cisd_bull", "choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "LIMIT_PULLBACK_BULL",
            "description": "Vào lệnh BUY tại 50% retracement của candle trigger. Entry type LIMIT, entry_method PULLBACK_50.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "entry_type": "LIMIT",
                    "entry_method": "PULLBACK_50",
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "LIMIT_OB_EDGE_BULL",
            "description": "Vào lệnh BUY tại cạnh OB (bottom). Entry type LIMIT, entry_method OB_EDGE.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bull", "weight": 5.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "entry_type": "LIMIT",
                    "entry_method": "OB_EDGE",
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "LIMIT_EMA_TOUCH_BULL",
            "description": "Vào lệnh BUY khi giá chạm EMA 21. Entry type LIMIT, entry_method EMA_TOUCH period 21.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "entry_type": "LIMIT",
                    "entry_method": "EMA_TOUCH",
                    "entry_value": 21,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "LIMIT_FIXED_OFFSET_BULL",
            "description": "Vào lệnh BUY dưới giá hiện tại 15 pips. Entry type LIMIT, entry_method FIXED_OFFSET.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size": 0.01,
                    "entry_type": "LIMIT",
                    "entry_method": "FIXED_OFFSET",
                    "entry_value": 15,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "FIXED_BUDGET_BULL",
            "description": "Vào lệnh BUY với budget cố định $50. SL dựa trên pivot point, MT5 tự tính lot size.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "FIXED_BUDGET_BEAR",
            "description": "Vào lệnh SELL với budget cố định $50. SL dựa trên pivot point, MT5 tự tính lot size.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
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
