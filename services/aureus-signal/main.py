"""
Aureus Signal Engine — Stream consumer + Signal processor + DB writer

Pipeline:  Gateway → Redis Stream → [THIS] → TimescaleDB + Redis State → Dashboard API
"""

import asyncio
import logging
import os
from engine.live_engine import run_signal_engine

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("aureus-signal.main")

if __name__ == "__main__":
    try:
        asyncio.run(run_signal_engine())
    except KeyboardInterrupt:
        logger.info("[GLOBAL] [main] 1... Signal engine stopped")
