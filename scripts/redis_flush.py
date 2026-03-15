import redis
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("redis-flush")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))

def main():
    logger.info(f"🧨 Flushing Redis at {REDIS_HOST}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.flushall()
        logger.info("✅ Redis FLUSHALL complete.")
    except Exception as e:
        logger.error(f"❌ Redis flush failed: {e}")

if __name__ == "__main__":
    main()
