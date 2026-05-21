import asyncio
import os
import json
import logging
from engine.logging_common import get_logger
import asyncpg
from dotenv import load_dotenv

logger = get_logger(__name__)
async def seed_system_strategies(pool=None, conn=None):
    """
    Seeds the database with system-default strategy templates.
    Ensures that specialized strategies are always available for assignment.
    """
    if conn is None and pool is None:
        raise ValueError("seed_system_strategies requires pool or conn")
    strategies = [
        {
            "name": "TREND_CONT_BULL",
            "is_active": True,
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [
                    {"type": "trend_cont_poc_cisd", "direction": "bullish"}
                ],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
            "description": "High-probability SMC Trend Continuation. Requires HTF alignment, structural break, and pull-back sweep.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [
                    {"type": "trend_cont_poc_cisd", "direction": "bearish"}
                ],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "name": "TREND_CONT_FVG_BULL",
            "is_active": True,
            "description": "Trend continuation BUY LIMIT at first bullish FVG after CHOCH LL pivot. No FVG means no order.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "LIMIT",
                    "entry_method": "ENTRY_FVG_FROM_CHOCH_PIVOT",
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
            "name": "TREND_CONT_FVG_BEAR",
            "is_active": True,
            "description": "Trend continuation SELL LIMIT at first bearish FVG after CHOCH HH pivot. No FVG means no order.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "LIMIT",
                    "entry_method": "ENTRY_FVG_FROM_CHOCH_PIVOT",
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
            "name": "TREND_CONT_LIMIT_BULL",
            "is_active": True,
            "description": "Trend continuation BUY LIMIT at newest CHOCH LL pivot. Entry method ENTRY_PIVOT_LIMIT.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "LIMIT",
                    "entry_method": "ENTRY_PIVOT_LIMIT",
                    "entry_value": "PIVOT",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1, "pivot_index": 2},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "TREND_CONT_LIMIT_BEAR",
            "is_active": True,
            "description": "Trend continuation SELL LIMIT at newest CHOCH HH pivot. Entry method ENTRY_PIVOT_LIMIT.",
            "min_score": 3.0,
            "config": {
                "min_score_threshold": 0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30 }
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "LIMIT",
                    "entry_method": "ENTRY_PIVOT_LIMIT",
                    "entry_value": "PIVOT",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "PIVOT_POINT", "offset_pips": 1, "pivot_index": 2},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "ORDER_FLOW_BULL",
            "is_active": True,
            "description": "BUY khi xuất hiện CHOCH bullish rồi xác nhận thêm sweep_bull (sequence: choch_up → sweep_bull).",
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
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
            "description": "SELL khi xuất hiện CHOCH bearish rồi xác nhận thêm sweep_bear (sequence: choch_down → sweep_bear).",
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
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
            "description": "BUY chỉ khi có sweep_bull theo session liquidity (sequence: sweep_bull, không dùng CHOCH).",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
            "description": "SELL chỉ khi có sweep_bear theo session liquidity (sequence: sweep_bear, không dùng CHOCH).",
            "min_score": 6.0,
            "config": {
                "min_score_threshold": 6.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "sweep_bear", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
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
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
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
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
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
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
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
                    "entry_type": "MARKET",
                    "entry_method": "CURRENT",
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
            "is_active": True,
            "description": "BUY LIMIT pullback 50% chỉ khi có CHOCH bullish. Entry method PULLBACK_50.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "LIMIT",
                    "entry_method": "PULLBACK_50",
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
            "name": "LIMIT_PULLBACK_BEAR",
            "is_active": True,
            "description": "SELL LIMIT pullback 50% chỉ khi có CHOCH bearish. Entry method PULLBACK_50.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_up"]},
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "LIMIT",
                    "entry_method": "PULLBACK_50",
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
            "name": "LIMIT_OB_EDGE_BULL",
            "is_active": True,
            "description": "Vào lệnh BUY tại cạnh OB (bottom). Entry type LIMIT, entry_method OB_EDGE.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_up", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "LIMIT",
                    "entry_method": "OB_EDGE",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_LOW", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_down"]
                }
            }
        },
        {
            "name": "LIMIT_OB_EDGE_BEAR",
            "is_active": True,
            "description": "Vào lệnh SELL tại cạnh OB (top). Entry type LIMIT, entry_method OB_EDGE.",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [],
                "sequence": [
                    {"tag": "choch_down", "weight": 4.0, "required": True, "max_wait": 30, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "LIMIT",
                    "entry_method": "OB_EDGE",
                    "size_mode": "RISK_FIXED_AMOUNT",
                    "size_value": 50.0,
                    "sl": {"type": "FIXED_PIPS"},
                    "tp": {"type": "RR_RATIO", "value": 1.5},
                    "trailing": {"type": "SWING_HIGH", "activation_pips": 300},
                    "capital_risk_pct": 1.0,
                    "early_exits": ["choch_up"]
                }
            }
        },
        {
            "name": "LIMIT_EMA_TOUCH_BULL",
            "is_active": True,
            "description": "BUY LIMIT khi có CHOCH bullish và EMA alignment bullish (ema_21_up + ema_55_up + EMA21>EMA55).",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [
                    {"type": "ema_alignment", "period": 21, "required_slope": "POSITIVE"},
                    {"type": "ema_alignment", "period": 55, "required_slope": "POSITIVE"},
                    {"type": "ema_relation", "fast_period": 21, "slow_period": 55, "operator": ">"}
                ],
                "sequence": [
                    {"tag": "choch_up", "weight": 2.0, "required": True, "max_wait": 30, "reset_signals": ["choch_down"]},
                    {"tag": "ema_21_up", "weight": 3.0, "required": True, "max_wait": 20, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {
                    "direction": "BUY",
                    "entry_type": "LIMIT",
                    "entry_method": "EMA_TOUCH",
                    "entry_value": 21,
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
            "name": "LIMIT_EMA_TOUCH_BEAR",
            "is_active": True,
            "description": "SELL LIMIT khi có CHOCH bearish và EMA alignment bearish (ema_21_down + ema_55_down + EMA21<EMA55).",
            "min_score": 4.0,
            "config": {
                "min_score_threshold": 4.0,
                "context_filters": [
                    {"type": "ema_alignment", "period": 21, "required_slope": "NEGATIVE"},
                    {"type": "ema_alignment", "period": 55, "required_slope": "NEGATIVE"},
                    {"type": "ema_relation", "fast_period": 21, "slow_period": 55, "operator": "<"}
                ],
                "sequence": [
                    {"tag": "choch_down", "weight": 2.0, "required": True, "max_wait": 30, "reset_signals": ["choch_up"]},
                    {"tag": "ema_21_down", "weight": 3.0, "required": True, "max_wait": 20, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {
                    "direction": "SELL",
                    "entry_type": "LIMIT",
                    "entry_method": "EMA_TOUCH",
                    "entry_value": 21,
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
            "name": "TPO_VA_REJECTION_BULL",
            "is_active": True,
            "description": "BUY khi TPO VA rejection bullish reclaim VAL được xác nhận.",
            "min_score": 0.75,
            "config": {
                "min_score_threshold": 0.75,
                "context_filters": [{"type": "tpo_context", "setup": "va_rejection", "required_direction": "bullish", "timeframes": ["D1", "H1", "M30"], "min_confidence_pct": 70, "bias": ["bullish", "neutral", "neutral-up"]}],
                "sequence": [
                    {"tag": "tpo_va_rejection_bull", "weight": 6.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_rejection_bear", "choch_down"]},
                    {"tag": "choch_up", "weight": 2.0, "required": False, "max_wait": 10, "reset_signals": ["choch_down"]}
                ],
                "trade_execution": {"direction": "BUY", "entry_type": "MARKET", "entry_method": "CURRENT", "size_mode": "RISK_FIXED_AMOUNT", "size_value": 50.0, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "tp": {"type": "RR_RATIO", "value": 1.5}, "trailing": {"type": "SWING_LOW", "activation_pips": 300}, "capital_risk_pct": 1.0, "early_exits": ["choch_down"]}
            }
        },
        {
            "name": "TPO_VA_REJECTION_BEAR",
            "is_active": True,
            "description": "SELL khi TPO VA rejection bearish reject VAH được xác nhận.",
            "min_score": 0.75,
            "config": {
                "min_score_threshold": 0.75,
                "context_filters": [{"type": "tpo_context", "setup": "va_rejection", "required_direction": "bearish", "timeframes": ["D1", "H1", "M30"], "min_confidence_pct": 70, "bias": ["bearish", "neutral", "neutral-down"]}],
                "sequence": [
                    {"tag": "tpo_va_rejection_bear", "weight": 6.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_rejection_bull", "choch_up"]},
                    {"tag": "choch_down", "weight": 2.0, "required": False, "max_wait": 10, "reset_signals": ["choch_up"]}
                ],
                "trade_execution": {"direction": "SELL", "entry_type": "MARKET", "entry_method": "CURRENT", "size_mode": "RISK_FIXED_AMOUNT", "size_value": 50.0, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "tp": {"type": "RR_RATIO", "value": 1.5}, "trailing": {"type": "SWING_HIGH", "activation_pips": 300}, "capital_risk_pct": 1.0, "early_exits": ["choch_up"]}
            }
        },
        {
            "name": "TPO_VA_BREAKOUT_BULL",
            "is_active": True,
            "description": "BUY khi TPO VA breakout acceptance bullish giữ trên VAH.",
            "min_score": 0.75,
            "config": {
                "min_score_threshold": 0.75,
                "context_filters": [{"type": "tpo_context", "setup": "va_breakout_acceptance", "required_direction": "bullish", "timeframes": ["D1", "H1", "M30"], "min_confidence_pct": 70, "bias": ["bullish", "neutral", "neutral-up"]}],
                "sequence": [{"tag": "tpo_va_breakout_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_breakout_bear", "choch_down"]}],
                "trade_execution": {"direction": "BUY", "entry_type": "MARKET", "entry_method": "CURRENT", "size_mode": "RISK_FIXED_AMOUNT", "size_value": 50.0, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "tp": {"type": "RR_RATIO", "value": 1.5}, "trailing": {"type": "SWING_LOW", "activation_pips": 300}, "capital_risk_pct": 1.0, "early_exits": ["choch_down"]}
            }
        },
        {
            "name": "TPO_VA_BREAKOUT_BEAR",
            "is_active": True,
            "description": "SELL khi TPO VA breakout acceptance bearish giữ dưới VAL.",
            "min_score": 0.75,
            "config": {
                "min_score_threshold": 0.75,
                "context_filters": [{"type": "tpo_context", "setup": "va_breakout_acceptance", "required_direction": "bearish", "timeframes": ["D1", "H1", "M30"], "min_confidence_pct": 70, "bias": ["bearish", "neutral", "neutral-down"]}],
                "sequence": [{"tag": "tpo_va_breakout_bear", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_va_breakout_bull", "choch_up"]}],
                "trade_execution": {"direction": "SELL", "entry_type": "MARKET", "entry_method": "CURRENT", "size_mode": "RISK_FIXED_AMOUNT", "size_value": 50.0, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "tp": {"type": "RR_RATIO", "value": 1.5}, "trailing": {"type": "SWING_HIGH", "activation_pips": 300}, "capital_risk_pct": 1.0, "early_exits": ["choch_up"]}
            }
        },
        {
            "name": "TPO_TREND_PULLBACK_BULL",
            "is_active": True,
            "description": "BUY khi TPO trend pullback bullish về value area rồi reclaim.",
            "min_score": 0.75,
            "config": {
                "min_score_threshold": 0.75,
                "context_filters": [{"type": "tpo_context", "setup": "trend_pullback", "required_direction": "bullish", "timeframes": ["D1", "H1", "M30"], "min_confidence_pct": 70, "bias": ["bullish", "neutral-up"]}],
                "sequence": [{"tag": "tpo_trend_pullback_bull", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_trend_pullback_bear", "choch_down"]}],
                "trade_execution": {"direction": "BUY", "entry_type": "MARKET", "entry_method": "CURRENT", "size_mode": "RISK_FIXED_AMOUNT", "size_value": 50.0, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "tp": {"type": "RR_RATIO", "value": 1.5}, "trailing": {"type": "SWING_LOW", "activation_pips": 300}, "capital_risk_pct": 1.0, "early_exits": ["choch_down"]}
            }
        },
        {
            "name": "TPO_TREND_PULLBACK_BEAR",
            "is_active": True,
            "description": "SELL khi TPO trend pullback bearish về value area rồi reject.",
            "min_score": 0.75,
            "config": {
                "min_score_threshold": 0.75,
                "context_filters": [{"type": "tpo_context", "setup": "trend_pullback", "required_direction": "bearish", "timeframes": ["D1", "H1", "M30"], "min_confidence_pct": 70, "bias": ["bearish", "neutral-down"]}],
                "sequence": [{"tag": "tpo_trend_pullback_bear", "weight": 7.0, "required": True, "max_wait": 20, "reset_signals": ["tpo_trend_pullback_bull", "choch_up"]}],
                "trade_execution": {"direction": "SELL", "entry_type": "MARKET", "entry_method": "CURRENT", "size_mode": "RISK_FIXED_AMOUNT", "size_value": 50.0, "sl": {"type": "PIVOT_POINT", "offset_pips": 1}, "tp": {"type": "RR_RATIO", "value": 1.5}, "trailing": {"type": "SWING_HIGH", "activation_pips": 300}, "capital_risk_pct": 1.0, "early_exits": ["choch_up"]}
            }
        },
    ]

    for strat in strategies:
        strat.setdefault("is_active", True)

    async def _seed_with_conn(conn):
        template_upserts = 0
        template_failures = []
        for strat in strategies:
            try:
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
                template_upserts += 1
            except Exception as e:
                template_failures.append(strat['name'])
                logger.error(f"[GLOBAL] [seed_system_strategies] Error: Failed to seed strategy {strat['name']}: {e}")

        if template_failures:
            raise RuntimeError(f"Failed to seed strategy templates: {', '.join(template_failures)}")

        symbols_env = os.getenv("SYMBOLS", "XAUUSD")
        symbols_list = [s.strip() for s in symbols_env.split(",") if s.strip()]
        if not symbols_list:
            symbols_list = ["XAUUSD"]

        strategy_names = [item["name"] for item in strategies]
        active_strategy_names = [item["name"] for item in strategies if item.get("is_active", True)]
        template_rows = await conn.fetch(
            "SELECT id, name FROM aureus_strategy_templates WHERE name = ANY($1::text[])",
            strategy_names,
        )
        name_to_id = {row["name"]: row["id"] for row in template_rows}

        desired_ids = {name_to_id[name] for name in active_strategy_names if name in name_to_id}

        activated = 0
        deactivated = 0
        unchanged = 0

        for symbol in symbols_list:
            active_rows = await conn.fetch(
                """
                SELECT ss.symbol, t.id as strategy_id, t.name as strategy_name
                FROM aureus_symbol_strategies ss
                JOIN aureus_strategy_templates t ON t.id = ss.strategy_id
                WHERE ss.symbol = ANY($1::text[]) AND ss.is_active = true
                """,
                [symbol],
            )
            active_ids_before = {row["strategy_id"] for row in active_rows}

            for strategy_name in active_strategy_names:
                strategy_id = name_to_id.get(strategy_name)
                if strategy_id is None:
                    continue

                await conn.execute(
                    """
                    INSERT INTO aureus_symbol_strategies (symbol, strategy_id, is_active)
                    VALUES ($1, $2, true)
                    ON CONFLICT (symbol, strategy_id) DO UPDATE
                    SET is_active = true
                    """,
                    symbol,
                    strategy_id,
                )

                if strategy_id in active_ids_before:
                    unchanged += 1
                else:
                    activated += 1

            result = await conn.execute(
                """
                UPDATE aureus_symbol_strategies
                SET is_active = false
                WHERE symbol = $1
                  AND is_active = true
                  AND NOT (strategy_id = ANY($2::int[]))
                """,
                symbol,
                list(desired_ids),
            )
            try:
                deactivated += int(str(result).split()[-1])
            except Exception:
                pass

        logger.info(
            "[GLOBAL] [seed_system_strategies] sync_summary "
            f"templates_upserted={template_upserts} symbols={len(symbols_list)} "
            f"activated={activated} deactivated={deactivated} unchanged={unchanged}"
        )

    if conn is not None:
        await _seed_with_conn(conn)
    else:
        async with pool.acquire() as conn:
            await _seed_with_conn(conn)

if __name__ == "__main__":
    # For manual testing
    load_dotenv()
    db_dsn = os.getenv("DATABASE_URL", "postgresql://aureus:aureus_password@localhost:5432/aureus")
    
    async def run():
        pool = await asyncpg.create_pool(db_dsn)
        await seed_system_strategies(pool)
        await pool.close()
        
    asyncio.run(run())
