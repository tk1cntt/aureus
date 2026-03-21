"""
Aureus Signal Engine — Stream consumer + Signal processor + DB writer

Pipeline:  Gateway → Redis Stream → [THIS] → TimescaleDB + Redis State → Dashboard API
"""

import asyncio
from engine.logging_common import configure_logging, get_logger

configure_logging("main")
logger = get_logger(__name__)

from engine.live_engine import run_signal_engine
if __name__ == "__main__":
    try:
        asyncio.run(run_signal_engine())
    except KeyboardInterrupt:
        logger.info("[GLOBAL] [main] 1... Signal engine stopped")
