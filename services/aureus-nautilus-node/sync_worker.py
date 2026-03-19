import asyncio
import json
from nautilus_trader.core.message import Event
from nautilus_trader.model.events import OrderEvent, PositionEvent
import logging

class SyncWorker:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self._running = False
        self._queue = asyncio.Queue()
        self.log = logging.getLogger(self.__class__.__name__)

    def start(self):
        self._running = True
        asyncio.create_task(self._process_loop())

    def stop(self):
        self._running = False

    def on_order_event(self, event: OrderEvent):
        # Called by msg_bus synchronously
        self._queue.put_nowait(("order", event))
        
    def on_position_event(self, event: PositionEvent):
        # Called by msg_bus synchronously
        self._queue.put_nowait(("position", event))

    async def _process_loop(self):
        while self._running:
            await self._process_queue_once()
            await asyncio.sleep(0.01)
            
    async def _process_queue_once(self):
        while not self._queue.empty():
            try:
                evt_type, event = self._queue.get_nowait()
                if evt_type == "order":
                    await self._handle_order_event(event)
                elif evt_type == "position":
                    await self._handle_position_event(event)
            except Exception as e:
                self.log.error(f"Error processing sync event: {e}")

    async def _handle_order_event(self, event):
        # Extract fields to match Aureus execution contract
        # Standardize Nautilus OrderEvent -> dict
        try:
            # Here we extract properties from Nautilus OrderEvent dynamically
            # For brevity, assuming we extract standard trace_id and status
            trace_id = getattr(event, "client_order_id", getattr(event, "order_id", "unknown")).value if hasattr(event, "client_order_id") else "unknown"
            
            payload = {
                "trace_id": str(trace_id),
                "status": event.__class__.__name__.upper(),  # e.g., ORDERACCEPTED -> ORDER_ACCEPTED
                "event_time": getattr(event, "ts_event", 0),
                "nautilus_event": True
            }
            
            # Use XADD to push back to Aureus
            # Stream key could be dynamic based on instrument
            symbol = getattr(event, "instrument_id", "UNKNOWN").value.split(".")[0] if hasattr(event, "instrument_id") else "UNKNOWN"
            
            stream_key = f"aureus:stream:{symbol}:execution"
            await self.redis_client.xadd(stream_key, {"type": "EXECUTION_REPORT", "data": json.dumps(payload)})
            self.log.debug(f"Pushed execution report for {trace_id} to {stream_key}")
            
        except Exception as e:
            self.log.error(f"Failed to map order event to execution report: {e}")

    async def _handle_position_event(self, event):
        # Extract fields to match Aureus position contract
        try:
            symbol = getattr(event, "instrument_id", "UNKNOWN").value.split(".")[0] if hasattr(event, "instrument_id") else "UNKNOWN"
            payload = {
                "position_id": str(getattr(event, "position_id", "unknown")),
                "symbol": symbol,
                "unrealized_pnl": float(getattr(event, "unrealized_pnl", 0.0)),
                "realized_pnl": float(getattr(event, "realized_pnl", 0.0))
            }
            stream_key = f"aureus:stream:{symbol}:positions"
            await self.redis_client.xadd(stream_key, {"type": "POSITION_REPORT", "data": json.dumps(payload)})
            self.log.debug(f"Pushed position report to {stream_key}")
        except Exception as e:
            self.log.error(f"Failed to map position event to stream report: {e}")
