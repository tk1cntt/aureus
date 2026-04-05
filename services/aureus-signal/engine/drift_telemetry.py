from engine.logging_common import get_logger

logger = get_logger("drift_telemetry")

async def log_ta_drift(symbol: str, redis_val: float, ta_val: float, lag_ms: int) -> None:
    """
    Log TradingAgents drift metrics to observability platform (e.g., TimescaleDB).
    Currently implemented as structured logging until asyncpg context is provided globally.
    """
    try:
        payload = {
            "symbol": symbol,
            "redis_val": float(redis_val),
            "ta_val": float(ta_val),
            "lag_ms": int(lag_ms),
            "drift_diff": float(abs(redis_val - ta_val))
        }
        logger.info(f"TA_DRIFT: {payload}")
    except Exception as e:
        logger.error(f"Failed to log drift telemetry for {symbol}: {e}")
