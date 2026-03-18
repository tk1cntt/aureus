import asyncio
import os
import logging
import time
import json
import redis.asyncio as redis
import asyncpg
from datetime import datetime

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_file = os.getenv("LOG_FILE")

handlers = [logging.StreamHandler()]
if log_file:
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=handlers
)
logger = logging.getLogger("aureus-db-writer.main")

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "aureus-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "aureus-timescaledb")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "aureus")
POSTGRES_USER = os.getenv("POSTGRES_USER", "aureus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "aureus_secure_pass")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
BATCH_TIMEOUT_MS = int(os.getenv("BATCH_TIMEOUT_MS", 1000))

# Consumer Group Settings
CONSUMER_GROUP = "aureus-db-writers"
CONSUMER_NAME = f"writer-{os.getenv('HOSTNAME', 'local')}"

class DBWriter:
    def __init__(self):
        self.redis: redis.Redis = None
        self.pg_pool: asyncpg.Pool = None
        self.running = True
        self.known_streams = set()
        self.tick_buffer = []
        self.candle_buffer = []
        self.swing_point_buffer = []
        self.execution_buffer = []
        self.last_flush_time = time.time()

    async def connect_redis(self):
        while self.running:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                await self.redis.ping()
                logger.info(f"[GLOBAL] [connect_redis] 1... Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
                break
            except Exception as e:
                logger.error(f"[GLOBAL] [connect_redis] Error: Waiting for Redis... {e}")
                await asyncio.sleep(2)

    async def connect_postgres(self):
        while self.running:
            try:
                self.pg_pool = await asyncpg.create_pool(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    database=POSTGRES_DB
                )
                logger.info(f"[GLOBAL] [connect_postgres] 1... Connected to TimescaleDB at {POSTGRES_HOST}:{POSTGRES_PORT}")
                async with self.pg_pool.acquire() as conn:
                     with open("schema.sql", "r") as f:
                        schema_sql = f.read()
                        await conn.execute(schema_sql)
                logger.info("[GLOBAL] [connect_postgres] 2... Database schema verified.")
                break
            except Exception as e:
                logger.error(f"[GLOBAL] [connect_postgres] Error: Waiting for Postgres... {e}")
                await asyncio.sleep(2)

    async def ensure_consumer_group(self, stream_key):
        try:
            await self.redis.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
            logger.info(f"[GLOBAL] [ensure_consumer_group] 1... Created group {CONSUMER_GROUP} for {stream_key}")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"[GLOBAL] [ensure_consumer_group] Error: Group error for {stream_key}: {e}")

    async def discover_streams(self):
        patterns = [
            "aureus:stream:*:tick",
            "aureus:stream:*:candle",
            "aureus:stream:*:swing_point",
            "aureus:stream:*:execution",
        ]
        found_streams = set()
        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                found_streams.update(keys)
                if cursor == 0: break
        
        new_streams = found_streams - self.known_streams
        if new_streams:
            for stream in new_streams:
                await self.ensure_consumer_group(stream)
            self.known_streams.update(new_streams)

    async def process_batch(self):
        if not self.tick_buffer and not self.candle_buffer and not self.swing_point_buffer and not self.execution_buffer:
            return
        async with self.pg_pool.acquire() as conn:
            if self.tick_buffer:
                ticks_to_insert = self.tick_buffer[:]
                self.tick_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                for stream, msg_id, payload in ticks_to_insert:
                    try:
                        ts_val = payload.get('t') or payload.get('timestamp') or payload.get('time')
                        if not ts_val: ts_val = datetime.fromtimestamp(int(msg_id.split('-')[0]) / 1000.0)
                        elif isinstance(ts_val, str):
                            try:
                                f_ts = float(ts_val)
                                ts_val = datetime.fromtimestamp(f_ts / (1000.0 if f_ts > 1e11 else 1.0))
                            except Exception: ts_val = datetime.fromisoformat(ts_val)
                        elif isinstance(ts_val, (int, float)):
                            ts_val = datetime.fromtimestamp(ts_val / (1000.0 if ts_val > 1e11 else 1.0))
                        
                        row = (ts_val, payload.get('symbol', 'UNKNOWN'), float(payload.get('bid', 0.0)), float(payload.get('ask', 0.0)), float(payload.get('v', payload.get('vol', payload.get('volume', 0.0)))))
                        data_rows.append(row); msg_ids.append(msg_id); stream_keys.append(stream)
                    except Exception as e: logger.error(f"[GLOBAL] [process_batch] Error: Tick parse error: {e}")
                if data_rows:
                    await conn.copy_records_to_table('aureus_ticks', records=data_rows, columns=['time', 'symbol', 'bid', 'ask', 'volume'])
                    
                if data_rows:
                    await conn.copy_records_to_table('aureus_ticks', records=data_rows, columns=['time', 'symbol', 'bid', 'ask', 'volume'])
                    acks = {}
                    for s, m in zip(stream_keys, msg_ids):
                        if s not in acks: acks[s] = []
                        acks[s].append(m)
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items(): pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 1... Inserted {len(data_rows)} ticks")

            if self.candle_buffer:
                candles_to_insert = self.candle_buffer[:]
                self.candle_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                for stream, msg_id, payload in candles_to_insert:
                    try:
                        ts_val = payload.get('t') or payload.get('timestamp') or payload.get('time')
                        if isinstance(ts_val, str):
                            try:
                                f_ts = float(ts_val)
                                ts_val = datetime.fromtimestamp(f_ts / (1000.0 if f_ts > 1e11 else 1.0))
                            except Exception: ts_val = datetime.fromisoformat(ts_val)
                        elif isinstance(ts_val, (int, float)):
                            ts_val = datetime.fromtimestamp(ts_val / (1000.0 if ts_val > 1e11 else 1.0))
                        if not ts_val:
                            logger.warning(f"[GLOBAL] [process_batch] Error: Skipping candle with null timestamp: {payload}")
                            continue
                        
                        # Fix for Candle mapping: test script sends 'tf' but might send 'timeframe'
                        row = (ts_val, payload.get('symbol', 'UNKNOWN'), payload.get('tf', payload.get('timeframe', 'UNKNOWN')), float(payload.get('o', payload.get('open', 0.0))), float(payload.get('h', payload.get('high', 0.0))), float(payload.get('l', payload.get('low', 0.0))), float(payload.get('c', payload.get('close', 0.0))), float(payload.get('v', payload.get('volume', 0.0))))
                        data_rows.append(row); msg_ids.append(msg_id); stream_keys.append(stream)
                    except Exception as e: logger.error(f"[GLOBAL] [process_batch] Error: Candle parse error: {e}")
                if data_rows:
                    query = """
                        INSERT INTO aureus_candles (time, symbol, timeframe, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                            high = GREATEST(aureus_candles.high, EXCLUDED.high),
                            low = LEAST(aureus_candles.low, EXCLUDED.low),
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """
                    await conn.executemany(query, data_rows)
                    acks = {}
                    for s, m in zip(stream_keys, msg_ids):
                        if s not in acks: acks[s] = []
                        acks[s].append(m)
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items(): pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 2... Inserted/Updated {len(data_rows)} candles")

            if self.swing_point_buffer:
                sp_to_insert = self.swing_point_buffer[:]
                self.swing_point_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                for stream, msg_id, payload in sp_to_insert:
                    try:
                        ts_val = payload.get('t') or payload.get('time')
                        if isinstance(ts_val, str):
                            try:
                                f_ts = float(ts_val)
                                ts_val = datetime.fromtimestamp(f_ts / (1000.0 if f_ts > 1e11 else 1.0))
                            except Exception: ts_val = datetime.fromisoformat(ts_val)
                        elif isinstance(ts_val, (int, float)):
                            ts_val = datetime.fromtimestamp(ts_val / (1000.0 if ts_val > 1e11 else 1.0))

                        row = (ts_val, payload.get('symbol', 'UNKNOWN'), 'M1', float(payload.get('price', 0.0)), payload.get('is_high', 'false').lower() == 'true' if isinstance(payload.get('is_high'), str) else bool(payload.get('is_high', False)), payload.get('type', 'UNKNOWN'))
                        data_rows.append(row); msg_ids.append(msg_id); stream_keys.append(stream)
                    except Exception as e: logger.error(f"[GLOBAL] [process_batch] Error: SwingPoint parse error: {e}")
                if data_rows:
                    query = """
                        INSERT INTO aureus_swing_points (time, symbol, timeframe, price, is_high, type)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (time, symbol, timeframe, is_high) DO UPDATE SET
                            price = EXCLUDED.price,
                            type = EXCLUDED.type
                    """
                    await conn.executemany(query, data_rows)
                    acks = {}
                    for s, m in zip(stream_keys, msg_ids):
                        if s not in acks: acks[s] = []
                        acks[s].append(m)
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items(): pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 3... Inserted {len(data_rows)} swing points")

            if self.execution_buffer:
                execution_to_insert = self.execution_buffer[:]
                self.execution_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                for stream, msg_id, payload in execution_to_insert:
                    try:
                        raw_data = payload.get('data')
                        event_payload = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
                        if not isinstance(event_payload, dict):
                            raise ValueError("Execution payload data must be a JSON object")

                        event_time = event_payload.get('event_time') or payload.get('t') or payload.get('time')
                        if isinstance(event_time, str):
                            try:
                                f_ts = float(event_time)
                                event_time = datetime.fromtimestamp(f_ts / (1000.0 if f_ts > 1e11 else 1.0))
                            except Exception:
                                event_time = datetime.fromisoformat(event_time)
                        elif isinstance(event_time, (int, float)):
                            event_time = datetime.fromtimestamp(event_time / (1000.0 if event_time > 1e11 else 1.0))
                        elif event_time is None:
                            event_time = datetime.fromtimestamp(int(msg_id.split('-')[0]) / 1000.0)

                        trace_id = event_payload.get('trace_id')
                        symbol = event_payload.get('symbol', 'UNKNOWN')
                        status = event_payload.get('status', 'UNKNOWN')
                        if not trace_id or symbol == 'UNKNOWN':
                            raise ValueError(f"Execution event missing trace_id/symbol: {event_payload}")

                        row = (
                            event_time,
                            trace_id,
                            symbol,
                            status,
                            event_payload.get('side'),
                            event_payload.get('type'),
                            float(event_payload.get('quantity', 0.0)),
                            float(event_payload.get('fill_price', 0.0)),
                            event_payload.get('adapter_order_id'),
                            event_payload.get('rejection_reason'),
                            event_payload.get('execution_mode', 'simulated'),
                            event_payload.get('raw_status'),
                            json.dumps(event_payload),
                        )
                        data_rows.append(row); msg_ids.append(msg_id); stream_keys.append(stream)
                    except Exception as e:
                        logger.error(f"[GLOBAL] [process_batch] Error: Execution parse error: {e}")

                if data_rows:
                    query = """
                        INSERT INTO aureus_execution_events (
                            event_time, trace_id, symbol, status, side, order_type,
                            quantity, fill_price, adapter_order_id, rejection_reason,
                            execution_mode, raw_status, payload
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
                        ON CONFLICT (trace_id, status, event_time) DO NOTHING
                    """
                    await conn.executemany(query, data_rows)
                    acks = {}
                    for s, m in zip(stream_keys, msg_ids):
                        if s not in acks: acks[s] = []
                        acks[s].append(m)
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items():
                        pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 4... Inserted {len(data_rows)} execution events")

    async def run(self):
        await self.connect_redis()
        await self.connect_postgres()
        logger.info("[GLOBAL] [run] 1... Worker started...")
        while self.running:
            await self.discover_streams()
            if not self.known_streams:
                await asyncio.sleep(1); continue
            streams_dict = {stream: ">" for stream in self.known_streams}
            try:
                response = await self.redis.xreadgroup(groupname=CONSUMER_GROUP, consumername=CONSUMER_NAME, streams=streams_dict, count=BATCH_SIZE, block=1000)
                if response:
                    for stream_name, messages in response:
                        for msg_id, payload in messages:
                            if ":tick" in stream_name: self.tick_buffer.append((stream_name, msg_id, payload))
                            elif ":candle" in stream_name: self.candle_buffer.append((stream_name, msg_id, payload))
                            elif ":swing_point" in stream_name: self.swing_point_buffer.append((stream_name, msg_id, payload))
                            elif ":execution" in stream_name: self.execution_buffer.append((stream_name, msg_id, payload))
            except Exception as e:
                logger.error(f"[GLOBAL] [run] Error: Read error: {e}"); await asyncio.sleep(1)
            
            buffer_size = (
                len(self.tick_buffer)
                + len(self.candle_buffer)
                + len(self.swing_point_buffer)
                + len(self.execution_buffer)
            )
            if buffer_size >= BATCH_SIZE or (buffer_size > 0 and (time.time() - self.last_flush_time) * 1000 >= BATCH_TIMEOUT_MS):
                await self.process_batch(); self.last_flush_time = time.time()

if __name__ == "__main__":
    try: asyncio.run(DBWriter().run())
    except KeyboardInterrupt: pass
