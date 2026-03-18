import asyncio
import json
import logging
import argparse
import sys
import uuid
from typing import Dict, Any, Optional
import time

try:
    import redis.asyncio as redis
except ImportError:
    print("Error: Missing required package 'redis'. Please install it using 'pip install redis'")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("flow_test_v2")

async def test_flow(redis_host: str, redis_port: int, symbol: str, timeout: int):
    client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    try:
        await client.ping()
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return False

    trace_id = f"flowtest_v2_{uuid.uuid4().hex[:8]}"
    order_stream ="aureus:stream:{}:orders".format(symbol)
    execution_stream = "aureus:stream:{}:execution".format(symbol)
    position_stream = "aureus:stream:{}:positions".format(symbol)
    account_stream = "aureus:stream:{}:account".format(symbol)

    # 1. Publish synthetic order
    order_payload = {
        "event_time": int(time.time() * 1000),
        "type": "ORDER_OPEN",
        "symbol": symbol,
        "quantity": 2.5,
        "side": "BUY",
        "order_type": "MARKET",
        "entry_price": 2000.5,
        "sl": 1950.0,
        "tp": 2100.0,
        "trace_id": trace_id,
        "execution_mode": "nautilus"
    }
    
    logger.info(f"Publishing intent to {order_stream}: {trace_id}")
    await client.xadd(order_stream, {"type": "ORDER_OPEN", "data": json.dumps(order_payload)})

    # 2. Wait for execution report
    logger.info(f"Waiting up to {timeout}s for execution report with trace_id {trace_id}...")
    start_time = time.time()
    last_exec_id = "0-0"
    execution_found = False

    while time.time() - start_time < timeout:
        response = await client.xread({execution_stream: last_exec_id}, count=100, block=1000)
        if response:
            for stream, entries in response:
                for entry_id, fields in entries:
                    last_exec_id = entry_id
                    raw_data = fields.get("data")
                    if raw_data:
                        try:
                            data = json.loads(raw_data)
                            if data.get("trace_id") == trace_id:
                                logger.info(f"SUCCESS: Found matching execution event: status={data.get('status')} trace_id={trace_id}")
                                execution_found = True
                                break
                        except Exception:
                            pass
                if execution_found:
                    break
        if execution_found:
            break

    if not execution_found:
        logger.error(f"Timeout waiting for execution report for trace_id {trace_id}")
        return False
        
    # 3. Publish mock position & account to verify DB ingestion paths
    position_payload = {
        "event_time": int(time.time() * 1000),
        "symbol": symbol,
        "position_id": f"pos_{trace_id}",
        "side": "BUY",
        "qty": 2.5,
        "avg_entry_price": 2000.5,
        "mark_price": 2005.0,
        "unrealized_pnl": 11.25,
        "realized_pnl": 0.0
    }
    account_payload = {
        "event_time": int(time.time() * 1000),
        "account_id": "acc_main",
        "equity": 10011.25,
        "balance": 10000.0,
        "margin_used": 500.0,
        "margin_free": 9511.25,
        "unrealized_pnl": 11.25,
        "realized_pnl": 0.0
    }
    
    logger.info(f"Publishing position update to {position_stream}")
    await client.xadd(position_stream, {"data": json.dumps(position_payload)})
    
    logger.info(f"Publishing account update to {account_stream}")
    await client.xadd(account_stream, {"data": json.dumps(account_payload)})
    
    logger.info("v2 flow artifacts published successfully.")
    await client.aclose()
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-host", default="127.0.0.1")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    
    success = asyncio.run(test_flow(args.redis_host, args.redis_port, args.symbol, args.timeout))
    sys.exit(0 if success else 1)
