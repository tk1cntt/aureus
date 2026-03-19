import asyncio
import json
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model.identifiers import InstrumentId, ClientOrderId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.model.orders.creation import StopLossOrder, TakeProfitOrder
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.objects import Price
from nautilus_trader.model.identifiers import Venue

class AureusExecutionClient(LiveExecutionClient):
    def __init__(self, redis_client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_client = redis_client
        self._running = False
        self._last_ids = {}

    async def connect(self):
        self._running = True
        asyncio.create_task(self._poll_loop())

    async def disconnect(self):
        self._running = False

    async def _poll_loop(self):
        # We will listen to all order streams
        self.log.info("AureusExecutionClient started polling orders...")
        # Simplification: hardcoded pattern or polling a specific stream
        streams = {"aureus:stream:XAUUSD:orders": self._last_ids.get("aureus:stream:XAUUSD:orders", "0-0")}
        while self._running:
            await self._poll_orders_once(streams)
            await asyncio.sleep(0.1)

    async def _poll_orders_once(self, streams=None):
        if not streams:
            streams = {"aureus:stream:XAUUSD:orders": self._last_ids.get("aureus:stream:XAUUSD:orders", "0-0")}
        try:
            result = await self.redis_client.xread(streams, count=10, block=1000)
            if not result:
                return
            for stream, messages in result:
                stream_str = stream.decode() if isinstance(stream, bytes) else stream
                for idx, message in messages:
                    self._last_ids[stream_str] = idx
                    self._handle_message(message)
        except Exception as e:
            self.log.error(f"Error polling execution data: {e}")

    def _handle_message(self, message: dict):
        try:
            msg_type = message.get(b"type", b"").decode()
            if msg_type != "ORDER_OPEN":
                return

            data = json.loads(message[b"data"].decode())
            trace_id = data["trace_id"]
            symbol = data["symbol"]
            side_str = data["side"].upper()
            qty = float(data["qty"])
            
            instrument_id = InstrumentId.from_str(f"{symbol}.AUREUS_VIRTUAL")
            
            # Simple Market Order implementation
            side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL
            
            # Create master order
            order = MarketOrder(
                instrument_id=instrument_id,
                client_order_id=ClientOrderId(trace_id),
                side=side,
                quantity=Quantity.from_double(qty),
                time_in_force=None,
            )
            self.generate_order(order)
            self.log.info(f"Generated Nautilus MarketOrder for {trace_id}")
            
            # Note: Proper Bracket Order (SL/TP) requires ContingentOrder logic in Nautilus.
            # For this Slice 2 prototype, we just generate the master order first.
            
        except Exception as e:
            self.log.error(f"Failed to handle execution message: {e}")
