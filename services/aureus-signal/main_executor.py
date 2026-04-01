"""
Aureus Strategy Executor — Entry point for decoupled strategy evaluation worker

Pipeline:  Signal Aggregator → Redis Stream (aureus:stream:{symbol}:signals) → [THIS] → Orders/AI Queue
"""

import asyncio
from engine.logging_common import configure_logging, get_logger

configure_logging("strategy_executor")
logger = get_logger(__name__)

from engine.strategy_executor import run_strategy_executor
if __name__ == "__main__":
    try:
        logger.info("[EXECUTOR] Starting Strategy Executor worker...")
        asyncio.run(run_strategy_executor())
    except KeyboardInterrupt:
        logger.info("[EXECUTOR] Strategy Executor stopped")
