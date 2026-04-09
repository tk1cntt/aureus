import asyncio
import os
import logging
import time
import json
import redis.asyncio as redis
import asyncpg
import uuid
from datetime import datetime
from state_machine import validate_transition

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_file = os.getenv("LOG_FILE")

handlers = [logging.StreamHandler()]
if log_file:
    log_file = log_file.strip()
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=handlers,
    force=True,
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
        self.position_buffer = []
        self.account_buffer = []
        self.order_buffer = []
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
            "aureus:stream:*:positions",
            "aureus:stream:*:account",
            "aureus:stream:*:orders",
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

    async def cleanup_stale_order_streams(self):
        """Delete stale order streams on startup before processing.
        
        Previous pending messages may be from an older producer format
        (missing 'open_time', missing 'data' wrapper). Clearing them
        prevents strict validation from rejecting every batch.
        """
        order_streams = ["aureus:stream:XAUUSD:orders", "aureus:stream:EURUSD:orders",
                         "aureus:stream:GBPUSD:orders", "aureus:stream:USDJPY:orders",
                         "aureus:stream:AUDUSD:orders", "aureus:stream:BTCUSD:orders",
                         "aureus:stream:ETHUSD:orders", "aureus:stream:USTEC:orders"]
        deleted_count = 0
        for stream in order_streams:
            try:
                length = await self.redis.xlen(stream)
                if length > 0:
                    await self.redis.delete(stream)
                    deleted_count += 1
                    logger.info(f"[GLOBAL] [cleanup] Deleted stale order stream {stream} ({length} pending messages)")
            except Exception as e:
                logger.warning(f"[GLOBAL] [cleanup] Could not clean {stream}: {e}")
        if deleted_count > 0:
            logger.info(f"[GLOBAL] [cleanup] Cleared {deleted_count} stale order streams. Consumer groups will be recreated on next discover_streams().")
        else:
            logger.info("[GLOBAL] [cleanup] No stale order streams to clean.")

    def _normalize_order_payload(self, payload):
        """Normalize wrapped order payload from Redis stream.
        
        Producer emits: {"type": "ORDER_OPEN", "data": json.dumps(order_dict)}
        Returns: (event_type, order_data) where order_data is the unwrapped dict.
        """
        event_type = payload.get('type', '')
        raw_data = payload.get('data')
        
        if raw_data is not None:
            if isinstance(raw_data, str):
                try:
                    order_data = json.loads(raw_data)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(f"Failed to parse order data JSON: {e}")
            else:
                order_data = raw_data
            if not isinstance(order_data, dict):
                raise ValueError("Order payload data must be a JSON object")
        else:
            # No data field - treat entire payload as order_data (backward compat for tests)
            order_data = dict(payload)
            order_data.pop('type', None)
        
        return event_type, order_data

    async def process_batch(self):
        if not self.candle_buffer and not self.swing_point_buffer and not self.execution_buffer and not self.position_buffer and not self.account_buffer and not self.order_buffer and not self.tick_buffer:
            return
        async with self.pg_pool.acquire() as conn:
            # --- TICK BUFFER: Process in real-time, DO NOT persist to DB ---
            if self.tick_buffer:
                ticks_to_ack = self.tick_buffer[:]
                self.tick_buffer.clear()

                # Process ticks in real-time (e.g., trigger calculations, emit events)
                # No DB write — ticks are ephemeral
                processed_count = 0
                for stream, msg_id, payload in ticks_to_ack:
                    try:
                        # Real-time processing happens here
                        # Example: trigger signal calculations, update in-memory state, etc.
                        processed_count += 1
                    except Exception as e:
                        logger.error(f"[GLOBAL] [process_batch] Error: Tick process error: {e}")

                # ACK all tick messages so they don't pile up in the stream
                acks = {}
                for s, m, _ in ticks_to_ack:
                    if s not in acks:
                        acks[s] = []
                    acks[s].append(m)

                if acks:
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items():
                        pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()

                logger.debug(
                    f"[GLOBAL] [process_batch] 1... Processed {processed_count} ticks (real-time, not persisted)"
                )

            # --- CANDLE BUFFER: Persist to DB ---
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
                            except Exception:
                                ts_val = datetime.fromisoformat(ts_val)
                        elif isinstance(ts_val, (int, float)):
                            ts_val = datetime.fromtimestamp(ts_val / (1000.0 if ts_val > 1e11 else 1.0))
                        if not ts_val:
                            logger.warning(f"[GLOBAL] [process_batch] Error: Skipping candle with null timestamp: {payload}")
                            continue

                        row = (
                            ts_val,
                            payload.get('symbol', 'UNKNOWN'),
                            payload.get('tf', payload.get('timeframe', 'UNKNOWN')),
                            float(payload.get('o', payload.get('open', 0.0))),
                            float(payload.get('h', payload.get('high', 0.0))),
                            float(payload.get('l', payload.get('low', 0.0))),
                            float(payload.get('c', payload.get('close', 0.0))),
                            float(payload.get('v', payload.get('volume', 0.0))),
                        )
                        data_rows.append(row)
                        msg_ids.append(msg_id)
                        stream_keys.append(stream)
                    except Exception as e:
                        logger.error(f"[GLOBAL] [process_batch] Error: Candle parse error: {e}")

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

            if self.position_buffer:
                positions_to_insert = self.position_buffer[:]
                self.position_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                for stream, msg_id, payload in positions_to_insert:
                    try:
                        raw_data = payload.get('data')
                        event_payload = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
                        if not isinstance(event_payload, dict):
                            raise ValueError("Position payload data must be JSON")

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

                        symbol = event_payload.get('symbol', 'UNKNOWN')
                        position_id = event_payload.get('position_id', 'UNKNOWN')
                        if position_id == 'UNKNOWN':
                            continue

                        row = (
                            event_time,
                            symbol,
                            position_id,
                            event_payload.get('side', 'UNKNOWN'),
                            float(event_payload.get('qty', 0.0)),
                            float(event_payload.get('avg_entry_price', 0.0)),
                            float(event_payload.get('mark_price', 0.0)),
                            float(event_payload.get('unrealized_pnl', 0.0)),
                            float(event_payload.get('realized_pnl', 0.0)),
                            json.dumps(event_payload)
                        )
                        data_rows.append(row); msg_ids.append(msg_id); stream_keys.append(stream)
                    except Exception as e:
                        logger.error(f"[GLOBAL] [process_batch] Error: Position parse error: {e}")

                if data_rows:
                    query = """
                        INSERT INTO aureus_position_snapshots (
                            event_time, symbol, position_id, side, qty,
                            avg_entry_price, mark_price, unrealized_pnl, realized_pnl, payload
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                        ON CONFLICT (position_id, event_time) DO NOTHING
                    """
                    await conn.executemany(query, data_rows)
                    acks = {}
                    for s, m in zip(stream_keys, msg_ids):
                        if s not in acks: acks[s] = []
                        acks[s].append(m)
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items(): pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 5... Inserted {len(data_rows)} position snapshots")

            if self.account_buffer:
                accounts_to_insert = self.account_buffer[:]
                self.account_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                for stream, msg_id, payload in accounts_to_insert:
                    try:
                        raw_data = payload.get('data')
                        event_payload = json.loads(raw_data) if isinstance(raw_data, str) else (raw_data or {})
                        if not isinstance(event_payload, dict):
                            raise ValueError("Account payload data must be JSON")

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

                        account_id = event_payload.get('account_id', 'UNKNOWN')
                        if account_id == 'UNKNOWN':
                            continue

                        row = (
                            event_time,
                            account_id,
                            float(event_payload.get('equity', 0.0)),
                            float(event_payload.get('balance', 0.0)),
                            float(event_payload.get('margin_used', 0.0)),
                            float(event_payload.get('margin_free', 0.0)),
                            float(event_payload.get('unrealized_pnl', 0.0)),
                            float(event_payload.get('realized_pnl', 0.0)),
                            json.dumps(event_payload)
                        )
                        data_rows.append(row); msg_ids.append(msg_id); stream_keys.append(stream)
                    except Exception as e:
                        logger.error(f"[GLOBAL] [process_batch] Error: Account parse error: {e}")

                if data_rows:
                    query = """
                        INSERT INTO aureus_account_snapshots (
                            event_time, account_id, equity, balance, margin_used, margin_free,
                            unrealized_pnl, realized_pnl, payload
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                        ON CONFLICT (account_id, event_time) DO NOTHING
                    """
                    await conn.executemany(query, data_rows)
                    acks = {}
                    for s, m in zip(stream_keys, msg_ids):
                        if s not in acks: acks[s] = []
                        acks[s].append(m)
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items(): pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 6... Inserted {len(data_rows)} account snapshots")

            if self.order_buffer:
                orders_to_process = self.order_buffer[:]
                self.order_buffer.clear()
                data_rows, msg_ids, stream_keys = [], [], []
                rejected_msg_ids = []  # Track ORDER_REJECTED events to ACK separately

                for stream, msg_id, payload in orders_to_process:
                    try:
                        # Normalize wrapped payload: extract data field, parse JSON
                        try:
                            event_type, order_data = self._normalize_order_payload(payload)
                        except ValueError as e:
                            logger.warning("[GLOBAL] [process_batch] Invalid order payload on %s msg %s: %s", stream, msg_id, e)
                            rejected_msg_ids.append((stream, msg_id))
                            continue

                        # Skip ORDER_REJECTED events — they're not real orders, just signal rejections
                        if event_type == 'ORDER_REJECTED':
                            logger.debug(f"[GLOBAL] [process_batch] Skipping ORDER_REJECTED (not a trade): {order_data.get('strategy', 'unknown')} on {order_data.get('symbol', '?')}")
                            rejected_msg_ids.append((stream, msg_id))
                            continue

                        trace_id = order_data.get('trace_id')
                        if not trace_id:
                            logger.debug(f"[GLOBAL] [process_batch] Skipping order event without trace_id: {event_type or 'unknown'} on {order_data.get('symbol', '?')}")
                            rejected_msg_ids.append((stream, msg_id))
                            continue

                        # Read business fields from order_data (not envelope payload)
                        direction = order_data.get('side', order_data.get('direction', ''))
                        entry_type = order_data.get('entry_type', order_data.get('type', ''))
                        status = order_data.get('status', 'PENDING')

                        # Normalize producer status values to state machine compatible values
                        if status in ('PENDING_AI', 'ACTIVE'):
                            status = 'PENDING'

                        # Skip events that are not real order states
                        if direction not in ('BUY', 'SELL'):
                            logger.debug(f"[GLOBAL] [process_batch] Skipping order with invalid direction '{direction}': trace_id={trace_id}")
                            rejected_msg_ids.append((stream, msg_id))
                            continue

                        if entry_type not in ('MARKET', 'LIMIT', 'STOP'):
                            logger.debug(f"[GLOBAL] [process_batch] Skipping order with invalid entry_type '{entry_type}': trace_id={trace_id}")
                            rejected_msg_ids.append((stream, msg_id))
                            continue

                        symbol = order_data.get('symbol', 'UNKNOWN')
                        new_status = status

                        # Validate direction and entry_type
                        if direction not in ('BUY', 'SELL'):
                            logger.warning(f"[GLOBAL] [process_batch] Warning: Invalid direction '{direction}' for trace_id={trace_id}, defaulting to UNKNOWN")
                            direction = 'UNKNOWN'
                        if entry_type not in ('MARKET', 'LIMIT', 'STOP'):
                            logger.warning(f"[GLOBAL] [process_batch] Warning: Invalid entry_type '{entry_type}' for trace_id={trace_id}, defaulting to UNKNOWN")
                            entry_type = 'UNKNOWN'

                        # Validate state transition
                        existing_status = None
                        try:
                            existing_row = await conn.fetchval(
                                "SELECT status FROM aureus_trades WHERE trace_id = $1", trace_id
                            )
                            if existing_row:
                                existing_status = existing_row
                        except Exception as e:
                            logger.warning(f"[GLOBAL] [process_batch] Warning: Could not check existing status for {trace_id}: {e}")

                        if existing_status:
                            # Existing record: validate transition from current status
                            if not validate_transition(existing_status, new_status):
                                logger.warning(
                                    f"[GLOBAL] [process_batch] Warning: Invalid state transition "
                                    f"{existing_status}\u2192{new_status} for trace_id={trace_id}. Skipping."
                                )
                                rejected_msg_ids.append((stream, msg_id))
                                continue
                        else:
                            # New record: first status must be PENDING
                            if new_status != 'PENDING':
                                logger.warning(
                                    f"[GLOBAL] [process_batch] Warning: New trade must start as PENDING, "
                                    f"got '{new_status}' for trace_id={trace_id}. Skipping."
                                )
                                rejected_msg_ids.append((stream, msg_id))
                                continue

                        # Strict timestamp validation (D-06, D-07, D-08)
                        open_time = order_data.get('open_time')
                        if open_time is None or open_time == '':
                            logger.warning(
                                f"[GLOBAL] [process_batch] Rejecting order event -- missing required timestamp: trace_id={trace_id} event_type={event_type} msg_id={msg_id}"
                            )
                            rejected_msg_ids.append((stream, msg_id))
                            continue

                        # Parse timestamp fields
                        def parse_ts(val):
                            if val is None:
                                return None
                            if isinstance(val, str):
                                try:
                                    f_ts = float(val)
                                    return datetime.fromtimestamp(f_ts / (1000.0 if f_ts > 1e11 else 1.0))
                                except Exception:
                                    return datetime.fromisoformat(val)
                            if isinstance(val, (int, float)):
                                return datetime.fromtimestamp(val / (1000.0 if val > 1e11 else 1.0))
                            return None

                        filled_at = parse_ts(order_data.get('filled_at'))
                        closed_at = parse_ts(order_data.get('closed_at'))

                        # Build canonical payload JSONB (store order_data, not raw envelope)
                        order_payload = json.dumps(order_data)

                        row = (
                            trace_id,
                            order_data.get('ticket'),
                            symbol,
                            order_data.get('magic_number'),
                            order_data.get('strategy_id'),
                            order_data.get('strategy_name'),
                            direction,
                            entry_type,
                            new_status,
                            float(order_data['entry_price']) if order_data.get('entry_price') is not None else None,
                            float(order_data['exit_price']) if order_data.get('exit_price') is not None else None,
                            float(order_data['sl']) if order_data.get('sl') is not None else None,
                            float(order_data['tp']) if order_data.get('tp') is not None else None,
                            float(order_data['volume']) if order_data.get('volume') is not None else None,
                            float(order_data.get('commission', 0)),
                            float(order_data.get('swap', 0)),
                            float(order_data.get('profit', 0)),
                            filled_at,
                            closed_at,
                            order_payload,
                        )
                        data_rows.append(row)
                        msg_ids.append(msg_id)
                        stream_keys.append(stream)
                    except Exception as e:
                        logger.error(f"[GLOBAL] [process_batch] Error: Order parse error: {e}")

                if data_rows:
                    query = """
                        INSERT INTO aureus_trades (
                            trace_id, ticket, symbol, magic_number, strategy_id, strategy_name,
                            direction, entry_type, status, entry_price, exit_price,
                            sl, tp, volume, commission, swap, profit,
                            filled_at, closed_at, payload
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                        ON CONFLICT (trace_id) DO UPDATE SET
                            ticket = COALESCE(EXCLUDED.ticket, aureus_trades.ticket),
                            status = EXCLUDED.status,
                            exit_price = COALESCE(EXCLUDED.exit_price, aureus_trades.exit_price),
                            profit = COALESCE(EXCLUDED.profit, aureus_trades.profit),
                            closed_at = COALESCE(EXCLUDED.closed_at, aureus_trades.closed_at),
                            updated_at = NOW(),
                            payload = aureus_trades.payload || EXCLUDED.payload
                    """
                    await conn.executemany(query, data_rows)

                # ACK all processed messages (successful inserts + rejected events)
                acks = {}
                for s, m in zip(stream_keys, msg_ids):
                    if s not in acks:
                        acks[s] = []
                    acks[s].append(m)

                # Also ACK rejected messages
                for s, m in rejected_msg_ids:
                    if s not in acks:
                        acks[s] = []
                    acks[s].append(m)

                if acks:
                    pipe = self.redis.pipeline()
                    for s, ids in acks.items():
                        pipe.xack(s, CONSUMER_GROUP, *ids)
                    await pipe.execute()
                    logger.info(f"[GLOBAL] [process_batch] 7... Inserted/Updated {len(data_rows)} orders, {len(rejected_msg_ids)} rejected skipped")


    async def check_xpending(self):
        """Check for unacknowledged messages from previous runs and reprocess them."""
        logger.info("[RECONCILIATION] Checking XPENDING for unacked messages...")
        order_stream_pattern = "aureus:stream:*:orders"

        # Find all order streams
        cursor = 0
        order_streams = []
        while True:
            cursor, keys = await self.redis.scan(cursor, match=order_stream_pattern, count=100)
            order_streams.extend(keys)
            if cursor == 0:
                break

        if not order_streams:
            logger.info("[RECONCILIATION] No order streams found for XPENDING check")
            return

        total_recovered = 0
        for stream in order_streams:
            try:
                # Check if consumer group exists
                try:
                    await self.redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
                except redis.ResponseError as e:
                    if "BUSYGROUP" not in str(e):
                        raise

                # Get pending messages (from beginning to now, max 100)
                pending = await self.redis.xpending_range(
                    stream, CONSUMER_GROUP, '-', '+', 100
                )

                for msg_info in pending:
                    msg_id = msg_info['message_id']
                    try:
                        # Fetch message content
                        messages = await self.redis.xrange(stream, msg_id, msg_id, 1)
                        if messages:
                            _, payload = messages[0]
                            
                            # Skip ORDER_REJECTED — not real trades, just signal rejections
                            event_type = payload.get('type', '')
                            if event_type == 'ORDER_REJECTED':
                                logger.debug(f"[RECONCILIATION] Skipping ORDER_REJECTED during XPENDING recovery: {msg_id}")
                                await self.redis.xack(stream, CONSUMER_GROUP, msg_id)
                                continue
                            
                            # Only recover real trade events (PENDING, OPEN, CLOSE)
                            if event_type in ('ORDER_PENDING', 'ORDER_OPEN', 'ORDER_CLOSE'):
                                # Unwrap data field before adding to buffer (same as process_batch)
                                raw_data = payload.get('data')
                                if raw_data is not None:
                                    try:
                                        if isinstance(raw_data, str):
                                            unwrapped = json.loads(raw_data)
                                        else:
                                            unwrapped = raw_data
                                        if isinstance(unwrapped, dict):
                                            self.order_buffer.append((stream, msg_id, payload))
                                            total_recovered += 1
                                            logger.info(f"[RECONCILIATION] Recovered unacked message: {msg_id} from {stream}")
                                        else:
                                            logger.warning("[RECONCILIATION] XPENDING order recovery - non-dict data on %s msg %s, skipping", stream, msg_id)
                                    except (json.JSONDecodeError, TypeError) as e:
                                        logger.warning("[RECONCILIATION] XPENDING order recovery - unparseable data on %s msg %s: %s", stream, msg_id, e)
                                else:
                                    # No data field - backward compat
                                    self.order_buffer.append((stream, msg_id, payload))
                                    total_recovered += 1
                            else:
                                logger.debug(f"[RECONCILIATION] Skipping unknown event type '{event_type}' during XPENDING recovery: {msg_id}")
                            
                            # ACK after adding to buffer (will be processed in next process_batch)
                            await self.redis.xack(stream, CONSUMER_GROUP, msg_id)
                    except Exception as e:
                        logger.error(f"[RECONCILIATION] Error recovering message {msg_id}: {e}")

            except Exception as e:
                logger.error(f"[RECONCILIATION] Error checking XPENDING for {stream}: {e}")

        if total_recovered > 0:
            logger.info(f"[RECONCILIATION] Recovered {total_recovered} unacked messages")
            # Process recovered immediately
            await self.process_batch()
        else:
            logger.info("[RECONCILIATION] No unacked messages found")

    async def reconciliation_loop(self):
        """Periodic reconciliation loop — polls MT5 history and fills gaps."""
        # Configurable interval with validation (10-300s range)
        try:
            interval = int(os.environ.get('HISTORY_SYNC_INTERVAL_SEC', '30'))
            interval = max(10, min(300, interval))
        except (ValueError, TypeError):
            interval = 30
            logger.warning("[RECONCILIATION] Invalid HISTORY_SYNC_INTERVAL_SEC, using default 30s")

        logger.info(f"[RECONCILIATION] Reconciliation loop started (interval={interval}s)")

        while self.running:
            try:
                await self.run_reconciliation()
            except Exception as e:
                logger.error(f"[RECONCILIATION] Error in reconciliation: {e}")
            await asyncio.sleep(interval)

    async def run_reconciliation(self):
        """
        Run one reconciliation cycle:
        1. Query DB for recent closed trades (last 5 minutes)
        2. Request trade history from EA via Redis command
        3. Wait for EA response on command channel
        4. Compare DB tickets vs MT5 tickets
        5. Insert missing trades with RECONCILED status
        6. Log discrepancies
        """
        logger.debug("[RECONCILIATION] Starting reconciliation cycle...")

        # 1. Get recent trades from DB (last 5 minutes)
        lookback_minutes = 5
        db_trades = await self.get_recent_trades_from_db(lookback_minutes)
        db_tickets = {t['ticket'] for t in db_trades if t.get('ticket')}
        logger.debug(f"[RECONCILIATION] Found {len(db_tickets)} trades in DB (last {lookback_minutes} min)")

        if not db_tickets:
            logger.debug("[RECONCILIATION] No recent trades in DB, skipping MT5 poll")
            return

        # 2. Request trade history from EA
        now_ms = int(time.time() * 1000)
        from_ms = int((time.time() - lookback_minutes * 60) * 1000)

        history_request = {
            "type": "REQUEST_TRADE_HISTORY",
            "from_time": from_ms,
            "to_time": now_ms,
            "magic_number": None,
            "symbol": None
        }

        # Publish command to Redis — EA picks it up via ProcessIncomingCommands
        cmd_channel = "aureus:mt5:commands"
        await self.redis.publish(cmd_channel, json.dumps(history_request))
        logger.debug(f"[RECONCILIATION] Sent REQUEST_TRADE_HISTORY to {cmd_channel}")

        # 3. Wait for EA response (subscribe to response channel briefly)
        mt5_trades = await self.wait_for_trade_history_response(timeout_sec=10)

        if mt5_trades is None:
            logger.warning("[RECONCILIATION] No response from EA within timeout")
            return

        logger.debug(f"[RECONCILIATION] Received {len(mt5_trades)} trades from MT5")

        # 4. Compare and find missing
        mt5_tickets = {t.get('ticket') for t in mt5_trades if t.get('ticket')}
        missing_tickets = mt5_tickets - db_tickets

        if not missing_tickets:
            logger.debug("[RECONCILIATION] No discrepancies detected")
            return

        logger.info(f"[RECONCILIATION] Found {len(missing_tickets)} missing trades")

        # 5. Insert missing trades
        async with self.pg_pool.acquire() as conn:
            for trade in mt5_trades:
                ticket = trade.get('ticket')
                if ticket not in missing_tickets:
                    continue

                await self.insert_reconciled_trade(conn, trade)

    async def get_recent_trades_from_db(self, minutes=5):
        """Query DB for trades closed in the last N minutes."""
        query = """
            SELECT ticket, symbol, magic_number, status, direction, entry_type,
                   entry_price, exit_price, sl, tp, volume, commission, swap, profit,
                   filled_at, closed_at, trace_id
            FROM aureus_trades
            WHERE closed_at >= NOW() - INTERVAL '{minutes} minutes'
            ORDER BY closed_at DESC
        """.format(minutes=minutes)

        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query)

        trades = []
        for row in rows:
            trades.append({
                'ticket': row['ticket'],
                'symbol': row['symbol'],
                'magic_number': row['magic_number'],
                'status': row['status'],
                'direction': row['direction'],
                'entry_type': row['entry_type'],
                'entry_price': row['entry_price'],
                'exit_price': row['exit_price'],
                'sl': row['sl'],
                'tp': row['tp'],
                'volume': row['volume'],
                'commission': row['commission'],
                'swap': row['swap'],
                'profit': row['profit'],
                'filled_at': row['filled_at'],
                'closed_at': row['closed_at'],
                'trace_id': row['trace_id'],
            })
        return trades

    async def wait_for_trade_history_response(self, timeout_sec=10):
        """
        Subscribe to command response channel and wait for TRADE_HISTORY response.
        Returns list of trade dicts, or None on timeout.
        """
        response_channel = "aureus:mt5:responses:db-writer"

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(response_channel)

            start_time = time.time()
            while time.time() - start_time < timeout_sec:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        if data.get('type') == 'TRADE_HISTORY':
                            await pubsub.unsubscribe(response_channel)
                            await pubsub.close()
                            return data.get('trades', [])
                    except json.JSONDecodeError:
                        continue

            await pubsub.unsubscribe(response_channel)
            await pubsub.close()
            return None

        except Exception as e:
            logger.error(f"[RECONCILIATION] Error waiting for trade history response: {e}")
            return None

    async def insert_reconciled_trade(self, conn, trade):
        """Insert a missing trade record with RECONCILED status and log discrepancy."""
        ticket = trade.get('ticket')
        symbol = trade.get('symbol', 'UNKNOWN')
        magic_number = trade.get('magic_number')
        direction = trade.get('direction', 'UNKNOWN')
        entry_price = trade.get('entry_price')
        exit_price = trade.get('exit_price')
        sl = trade.get('sl')
        tp = trade.get('tp')
        volume = trade.get('volume')
        commission = trade.get('commission', 0)
        swap = trade.get('swap', 0)
        profit = trade.get('profit', 0)

        # Generate trace_id for reconciled trade
        trace_id = f"reconciled-{ticket}-{uuid.uuid4().hex[:8]}"

        # Convert millisecond timestamps to datetime
        def ms_to_datetime(ms_val):
            if ms_val is None:
                return None
            if isinstance(ms_val, (int, float)):
                return datetime.fromtimestamp(ms_val / 1000.0)
            return ms_val

        filled_at = ms_to_datetime(trade.get('open_time'))
        closed_at = ms_to_datetime(trade.get('close_time'))

        # Insert trade with RECONCILED status
        insert_query = """
            INSERT INTO aureus_trades (
                trace_id, ticket, symbol, magic_number, direction, entry_type,
                status, entry_price, exit_price, sl, tp, volume,
                commission, swap, profit, filled_at, closed_at, payload
            ) VALUES ($1, $2, $3, $4, $5, $6, 'RECONCILED', $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            ON CONFLICT (trace_id) DO NOTHING
        """

        payload = json.dumps({
            'source': 'mt5_history',
            'reconciled_at': datetime.utcnow().isoformat(),
            'original_ticket': ticket,
        })

        await conn.execute(
            insert_query,
            trace_id, ticket, symbol, magic_number, direction, 'MARKET',
            entry_price, exit_price, sl, tp, volume,
            commission, swap, profit, filled_at, closed_at, payload
        )

        logger.info(f"[RECONCILIATION] Inserted missing trade: ticket={ticket}, symbol={symbol}, profit={profit}")

        # Log discrepancy for audit trail
        log_query = """
            INSERT INTO aureus_reconciliation_log (run_at, action, ticket, symbol, source, status, details)
            VALUES (NOW(), 'INSERT_MISSING_TRADE', $1, $2, 'mt5_history', 'RECONCILED', $3)
        """

        details = {
            'ticket': ticket,
            'symbol': symbol,
            'magic_number': magic_number,
            'direction': direction,
            'profit': profit,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'filled_at': filled_at.isoformat() if filled_at else None,
            'closed_at': closed_at.isoformat() if closed_at else None,
        }

        await conn.execute(log_query, ticket, symbol, json.dumps(details))

    async def run(self):
        await self.connect_redis()
        await self.connect_postgres()

        # Phase 38: Clear stale order streams before processing
        await self.cleanup_stale_order_streams()

        # Phase 31: Check XPENDING on startup (recover unacked messages)
        await self.check_xpending()

        # Phase 31: Start reconciliation loop as background task
        asyncio.create_task(self.reconciliation_loop())

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
                            elif ":positions" in stream_name: self.position_buffer.append((stream_name, msg_id, payload))
                            elif ":account" in stream_name: self.account_buffer.append((stream_name, msg_id, payload))
                            elif ":orders" in stream_name: self.order_buffer.append((stream_name, msg_id, payload))
            except Exception as e:
                logger.error(f"[GLOBAL] [run] Error: Read error: {e}"); await asyncio.sleep(1)

            buffer_size = (
                len(self.tick_buffer)
                + len(self.candle_buffer)
                + len(self.swing_point_buffer)
                + len(self.execution_buffer)
                + len(self.position_buffer)
                + len(self.account_buffer)
                + len(self.order_buffer)
            )
            if buffer_size >= BATCH_SIZE or (buffer_size > 0 and (time.time() - self.last_flush_time) * 1000 >= BATCH_TIMEOUT_MS):
                await self.process_batch(); self.last_flush_time = time.time()

if __name__ == "__main__":
    try: asyncio.run(DBWriter().run())
    except KeyboardInterrupt: pass
