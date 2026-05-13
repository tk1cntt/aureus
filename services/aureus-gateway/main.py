import asyncio
import zmq
import zmq.asyncio
import redis.asyncio as redis
import json
import logging
import os
from pydantic import BaseModel, ValidationError, Field
from typing import Literal, List, Optional

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
logger = logging.getLogger("aureus-gateway.main")

# ── Global Connection Registry ────────────────────────────────────────────────
# Maps symbol -> [writer1, writer2, ...]
active_connections = {}

# ── Message Models ────────────────────────────────────────────────────────────

class BaseMessage(BaseModel):
    type: Literal['TICK', 'CANDLE']
    symbol: str
    t: int = Field(..., description="Unix Timestamp in milliseconds")

class TickMessage(BaseMessage):
    type: Literal['TICK']
    bid: float
    ask: float
    vol: float

class CandleMessage(BaseMessage):
    type: Literal['CANDLE']
    o: float
    h: float
    l: float
    c: float
    v: float
    tf: str

class BackfillCandle(BaseModel):
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float
    tf: str

class BackfillMessage(BaseModel):
    type: Literal['BACKFILL']
    symbol: str
    candles: List[BackfillCandle]

# ── Order Event Models ────────────────────────────────────────────────
class OrderOpenedEvent(BaseModel):
    type: Literal['ORDER_OPENED']
    cmd_id: str
    symbol: str
    ticket: int
    direction: str
    order_type: str
    volume: float
    open_price: float
    sl: float
    tp: float
    magic: int
    strategy_name: Optional[str] = None
    trace_id: Optional[str] = None
    open_time: Optional[int] = None
    t: int

class OrderClosedEvent(BaseModel):
    type: Literal['ORDER_CLOSED']
    symbol: str
    ticket: int
    direction: str
    volume: float
    open_price: float
    close_price: float
    exit_price: Optional[float] = None
    profit: float
    commission: float
    swap: float
    magic: int
    strategy_name: Optional[str] = None
    trace_id: Optional[str] = None
    exit_reason: Optional[str] = None
    close_reason: Optional[str] = None
    reason: Optional[str] = None
    exit_time: Optional[int] = None
    t: int

class OrderFailedEvent(BaseModel):
    type: Literal['ORDER_FAILED']
    cmd_id: str
    symbol: str
    reason: str
    retcode: int
    t: int

class AckEvent(BaseModel):
    type: Literal['ACK']
    cmd_id: str
    t: int

class NackEvent(BaseModel):
    type: Literal['NACK']
    cmd_id: str
    reason: str
    t: int

class OrderFilledEvent(BaseModel):
    type: Literal['ORDER_FILLED']
    cmd_id: Optional[str] = None
    symbol: str
    deal_ticket: int
    position_ticket: int
    pending_order_id: int
    direction: str
    volume: float
    open_price: float
    sl: float
    tp: float
    magic: int
    strategy_name: Optional[str] = None
    trace_id: Optional[str] = None
    comment: Optional[str] = None
    time: Optional[int] = None
    t: int

# ── Position Report Models ────────────────────────────────────────────
class PositionInfo(BaseModel):
    ticket: int
    symbol: str
    magic: int
    direction: str
    volume: float
    open_price: float
    current_price: float
    profit: float
    swap: float
    sl: float
    tp: float
    pips: float
    open_time: int

class PositionReportEvent(BaseModel):
    type: Literal['POSITION_REPORT']
    positions: List[PositionInfo]
    total: int
    total_profit: float
    t: int

# ── Trade History Models ──────────────────────────────────────────────
class TradeInfo(BaseModel):
    ticket: int
    symbol: str
    magic_number: int
    direction: str
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    volume: float
    commission: float
    swap: float
    profit: float
    open_time: int
    close_time: int
    digits: Optional[int] = None
    pips: Optional[float] = None

class TradeHistoryEvent(BaseModel):
    type: Literal['TRADE_HISTORY']
    trades: List[TradeInfo]
    count: Optional[int] = None
    from_time: Optional[int] = None
    to_time: Optional[int] = None
    error: Optional[str] = None

# ── Open Orders Response (from EA REQUEST_ORDERS) ────────────────────
class OpenOrderInfo(BaseModel):
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    sl: float
    tp: float
    magic: int
    profit: float
    swap: float
    commission: float
    time: int
    comment: str

class OrdersEvent(BaseModel):
    type: Literal['ORDERS']
    positions: List[OpenOrderInfo]
    count: int

# ── Shared Message Processor ─────────────────────────────────────────────────

# Global counter to track cumulative backfill candles since startup
cumulative_backfill_counters = {}


_ATOMIC_PUBLISH_SCRIPT = """
local latest_key = KEYS[1]
local stream_key = KEYS[2]
local incoming_ts = tonumber(ARGV[1])
local maxlen = tonumber(ARGV[2])
local prev_t = redis.call('HGET', latest_key, 't')
if prev_t and incoming_ts <= tonumber(prev_t) then
  return 0
end
for i = 3, #ARGV, 2 do
  redis.call('HSET', latest_key, ARGV[i], ARGV[i + 1])
end
redis.call('XADD', stream_key, 'MAXLEN', '~', maxlen, '*', unpack(ARGV, 3))
return 1
"""

_BACKFILL_DEDUPE_TTL_SECONDS = 86400

async def process_message(r: redis.Redis, data: dict, source: str = "ZMQ") -> bool:
    """Process a single TICK or CANDLE message. Returns True if processed."""
    msg_type = data.get('type')

    if msg_type == 'BACKFILL':
        return await process_backfill(r, data, source)

    # Order events from EA — validate and publish to Redis channel
    ORDER_EVENT_TYPES = {
        'ORDER_OPENED': OrderOpenedEvent,
        'ORDER_CLOSED': OrderClosedEvent,
        'ORDER_FAILED': OrderFailedEvent,
        'ORDER_FILLED': OrderFilledEvent,
        'ACK': AckEvent,
        'NACK': NackEvent,
        'POSITION_REPORT': PositionReportEvent,
        'TRADE_HISTORY': TradeHistoryEvent,
        'ORDERS': OrdersEvent,
    }

    if msg_type in ORDER_EVENT_TYPES:
        try:
            if msg_type == 'ORDER_OPENED' and data.get('open_time') is None and data.get('t') is not None:
                data = dict(data)
                data['open_time'] = data.get('t')
            if msg_type == 'ORDER_CLOSED' and data.get('exit_time') is None and data.get('t') is not None:
                data = dict(data)
                data['exit_time'] = data.get('t')
            if msg_type == 'ORDER_FILLED' and data.get('time') is None and data.get('t') is not None:
                data = dict(data)
                data['time'] = data.get('t')

            model_class = ORDER_EVENT_TYPES[msg_type]
            valid_event = model_class(**data)
            event_json = valid_event.model_dump_json()
            await r.publish("aureus:mt5:events", event_json)
            symbol = data.get('symbol', 'GLOBAL')
            cmd_id = data.get('cmd_id', '')
            logger.info(
                f"[{symbol}] [process_message] Order event {msg_type} cmd_id={cmd_id} "
                f"ticket={data.get('ticket') or data.get('position_ticket') or data.get('pending_order_id') or ''} "
                "published to aureus:mt5:events"
            )
            return True
        except ValidationError as e:
            logger.warning(f"[{source}] Order event validation error: {e}")
            return False

    # Validate
    try:
        if msg_type == 'TICK':
            valid_msg = TickMessage(**data)
        elif msg_type == 'CANDLE':
            valid_msg = CandleMessage(**data)
        else:
            logger.warning(f"[{source}] [process_message] Error: Unknown message type: {msg_type}")
            return False
    except ValidationError as e:
        logger.warning(f"[{source}] [process_message] Error: Validation error: {e}")
        return False

    symbol, incoming_ts = valid_msg.symbol, valid_msg.t
    if msg_type == 'CANDLE':
        logger.info(f"[{symbol}] [process_message] 1... Receive from Gateway {symbol} t={incoming_ts} o={valid_msg.o} h={valid_msg.h} l={valid_msg.l} c={valid_msg.c} v={valid_msg.v}")

    latest_key = f"aureus:latest:{symbol}:{msg_type.lower()}"
    stream_key = f"aureus:stream:{symbol}:{msg_type.lower()}"

    update_data = valid_msg.model_dump()
    if msg_type == 'TICK':
        update_data['v'] = update_data.pop('vol')
    hash_update = {k: str(v) for k, v in update_data.items() if k != 'type'}

    argv = [str(incoming_ts), "5000"]
    for k, v in hash_update.items():
        argv.extend([k, v])

    published = await r.eval(_ATOMIC_PUBLISH_SCRIPT, 2, latest_key, stream_key, *argv)
    if int(published) == 0:
        logger.debug(f"[{symbol if msg_type in ('TICK', 'CANDLE') else 'GLOBAL'}] [process_message] Rejecting DUP/OLD {msg_type}: {incoming_ts}")
        return False

    if msg_type == 'CANDLE':
        logger.info(f"[{symbol}] [process_message] 2... Receive from Gateway {hash_update}")
    else:
        logger.info(f"[{symbol}] [process_message] 3... Processed {msg_type} {symbol} TS:{incoming_ts}")

    # Register connection for this symbol if TCP
    if source == "TCP" and "writer" in data:
        writer = data["writer"]
        if symbol not in active_connections:
            active_connections[symbol] = set()
        active_connections[symbol].add(writer)

    return True


async def process_backfill(r: redis.Redis, data: dict, source: str = "TCP") -> bool:
    """Process a BACKFILL message — insert candles without strict dedup (DB handles ON CONFLICT)."""
    try:
        backfill = BackfillMessage(**data)
    except ValidationError as e:
        logger.warning(f"[{source}] Backfill validation error: {e}")
        return False

    symbol = backfill.symbol
    stream_key = f"aureus:stream:{symbol}:candle"
    latest_key = f"aureus:latest:{symbol}:candle"

    # ── Signal downstream to RECALCULATE ──
    # [DEPRECATED] Signal Engine now monitors its own integrity and triggers its own recalc.
    # await r.xadd(stream_key, {"type": "COMMAND", "cmd": "RECALCULATE", "symbol": symbol})
    # logger.info(f"[{symbol}] [process_backfill] 1... BACKFILL {symbol}: Sent RECALCULATE command to stream")

    processed = 0
    for i, candle in enumerate(backfill.candles):
        candle_data = candle.model_dump()
        hash_update = {k: str(v) for k, v in candle_data.items()}
        hash_update['symbol'] = symbol

        # Detailed logging for audit (human readable TS)
        from datetime import datetime
        dt_str = datetime.fromtimestamp(candle.t / 1000).strftime('%Y-%m-%d %H:%M:%S')
        logger.debug(f"[{symbol}] [process_backfill] 1... BACKFILL candle {i+1}: {dt_str} @ {candle.c}")

        dedupe_key = f"aureus:dedupe:backfill:{symbol}:{candle.tf}:{candle.t}"
        inserted = await r.set(dedupe_key, "1", ex=_BACKFILL_DEDUPE_TTL_SECONDS, nx=True)
        if not inserted:
            logger.debug(f"[{symbol}] [process_backfill] Skip duplicate candle t={candle.t} tf={candle.tf}")
            continue

        # Add to stream (DB writer handles dedup via ON CONFLICT)
        await r.xadd(stream_key, hash_update, maxlen=5000, approximate=True)
        processed += 1

    # Update cumulative counter
    cumulative_backfill_counters[symbol] = cumulative_backfill_counters.get(symbol, 0) + processed

    # Update latest key to the most recent candle in backfill
    if backfill.candles:
        latest = max(backfill.candles, key=lambda c: c.t)
        latest_data = latest.model_dump()
        latest_hash = {k: str(v) for k, v in latest_data.items()}
        latest_hash['symbol'] = symbol

        # Only update if newer than current
        prev_t = await r.hget(latest_key, "t")
        if not prev_t or latest.t > int(prev_t):
            await r.hset(latest_key, mapping=latest_hash)

    logger.info(f"[{symbol}] [process_backfill] 2... BACKFILL {symbol}: {processed} candles in chunk. Total so far: {cumulative_backfill_counters[symbol]}")
    return True

# ── ZMQ Listener ──────────────────────────────────────────────────────────────

async def run_zmq_listener(r: redis.Redis):
    """ZMQ PULL listener on port 5555 (for tests and ZMQ-based clients)."""
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PULL)
    sock.setsockopt(zmq.LINGER, 0)
    bind_addr = "tcp://0.0.0.0:5555"
    sock.bind(bind_addr)
    logger.info(f"[GLOBAL] [run_zmq_listener] 1... ZMQ PULL socket bound to {bind_addr}")

    while True:
        try:
            msg_bytes = await sock.recv()
            data = json.loads(msg_bytes.decode('utf-8'))
            await process_message(r, data, source="ZMQ")
        except Exception as e:
            logger.error(f"[GLOBAL] [run_zmq_listener] Error: ZMQ Error: {e}")
            await asyncio.sleep(0.1)

# ── TCP Listener ──────────────────────────────────────────────────────────────

async def handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                             r: redis.Redis):
    """Handle a single TCP client — reads newline-delimited JSON."""
    addr = writer.get_extra_info('peername')
    logger.info(f"[GLOBAL] [handle_tcp_client] 1... TCP Client connected: {addr}")
    msg_count = 0
    client_symbols = set()

    try:
        while True:
            line = await reader.readline()
            if not line:
                break  # Client disconnected

            try:
                text = line.decode('utf-8').strip()
                if not text:
                    continue
                if text[0] not in "[{":
                    logger.debug(f"[GLOBAL] [handle_tcp_client] Non-JSON TCP probe/ignored from {addr}: first_char={text[0]!r} length={len(text)}")
                    continue
                data = json.loads(text)

                # Inject writer into data for process_message to register it
                data["writer"] = writer
                symbol = data.get("symbol")
                if symbol:
                    if symbol not in active_connections:
                        active_connections[symbol] = set()
                    active_connections[symbol].add(writer)
                    client_symbols.add(symbol)

                if await process_message(r, data, source="TCP"):
                    msg_count += 1
            except json.JSONDecodeError as e:
                logger.warning(f"[GLOBAL] [handle_tcp_client] Error: Invalid JSON from {addr}: {e}")
            except Exception as e:
                logger.error(f"[GLOBAL] [handle_tcp_client] Error: Processing error from {addr}: {e}")
    except asyncio.IncompleteReadError:
        pass
    except ConnectionResetError:
        pass
    finally:
        # Cleanup connection registry
        for sym in client_symbols:
            if sym in active_connections and writer in active_connections[sym]:
                active_connections[sym].remove(writer)
                if not active_connections[sym]:
                    del active_connections[sym]

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        except Exception:
            pass
        logger.info(f"[GLOBAL] [handle_tcp_client] 2... Client disconnected: {addr} (Total cumulative messages: {msg_count})")
        # Log backfill state if any
        if 'symbol' in locals() and symbol in cumulative_backfill_counters:
            logger.info(f"[{symbol}] [handle_tcp_client] 3... Final backfill count: {cumulative_backfill_counters[symbol]}")


async def run_tcp_listener(r: redis.Redis):
    """TCP listener on port 5556 for native MQL5 socket connections."""
    tcp_port = int(os.environ.get("TCP_PORT", 5556))

    async def client_handler(reader, writer):
        await handle_tcp_client(reader, writer, r)

    server = await asyncio.start_server(client_handler, "0.0.0.0", tcp_port)
    logger.info(f"[GLOBAL] [run_tcp_listener] 1... TCP listener started on 0.0.0.0:{tcp_port}")

    async with server:
        await server.serve_forever()

# ── Command Subscriber ────────────────────────────────────────────────────────

async def run_command_subscriber(r: redis.Redis):
    """Listen for commands from Signal Engine and forward to EA via TCP."""
    pubsub = r.pubsub()
    await pubsub.subscribe("aureus:mt5:commands")
    logger.info("[GLOBAL] [run_command_subscriber] 1... Subscribed to Redis channel: aureus:mt5:commands")

    async for message in pubsub.listen():
        if message['type'] != 'message':
            continue

        try:
            cmd_data = json.loads(message['data'])
            symbol = cmd_data.get("symbol")

            # Global commands (no symbol) — send once to any active EA connection
            if not symbol:
                global_commands = {"REQUEST_POSITIONS", "REQUEST_TRADE_HISTORY", "REQUEST_ORDERS"}
                cmd_type = cmd_data.get("type", "")
                if cmd_type in global_commands:
                    payload = message['data'] + "\n"
                    sent = False
                    # Send to first available active connection (EA handles all symbols)
                    for sym, writers in list(active_connections.items()):
                        for writer in writers:
                            try:
                                writer.write(payload.encode('utf-8'))
                                await writer.drain()
                                sent = True
                                logger.info(f"[GLOBAL] [run_command_subscriber] Sent {cmd_type} via {sym} connection")
                                break
                            except Exception as e:
                                logger.error(f"Failed to send global command to EA for {sym}: {e}")
                        if sent:
                            break

                    if not sent:
                        logger.warning(f"[GLOBAL] [run_command_subscriber] No active EA connection to send {cmd_type}")
                else:
                    logger.warning(f"Received command without symbol: {cmd_data}")
                continue

            if symbol in active_connections:
                payload = message['data'] + "\n"
                cmd_id = cmd_data.get("cmd_id", "unknown")
                cmd_type = cmd_data.get("type", "unknown")
                loop = asyncio.get_running_loop()
                dead_writers = []
                writer_count = len(active_connections[symbol])
                for writer_index, writer in enumerate(active_connections[symbol], start=1):
                    try:
                        start = loop.time()
                        writer.write(payload.encode('utf-8'))
                        await writer.drain()
                        drain_ms = (loop.time() - start) * 1000
                        peer = writer.get_extra_info('peername')
                        logger.info(
                            f"[{symbol}] [run_command_subscriber] 2... Forwarded command to EA "
                            f"cmd_id={cmd_id} type={cmd_type} writer={writer_index}/{writer_count} "
                            f"peer={peer} drain_ms={drain_ms:.2f}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send command to EA for {symbol}: cmd_id={cmd_id} type={cmd_type} error={e}")
                        dead_writers.append(writer)

                for dw in dead_writers:
                    active_connections[symbol].remove(dw)
            else:
                logger.warning(f"[GLOBAL] [run_command_subscriber] Error: Received command for {symbol} but no active EA connection found.")
        except Exception as e:
            logger.error(f"[GLOBAL] [run_command_subscriber] Error: Command subscriber error: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

async def run_gateway():
    redis_host = os.environ.get("REDIS_HOST", "aureus-redis")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    logger.info(f"[GLOBAL] [run_gateway] 1... Connecting to Redis at {redis_host}:{redis_port}...")
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    # Run all listeners concurrently
    await asyncio.gather(
        run_zmq_listener(r),
        run_tcp_listener(r),
        run_command_subscriber(r),
    )

if __name__ == "__main__":
    try:
        asyncio.run(run_gateway())
    except KeyboardInterrupt:
        pass
