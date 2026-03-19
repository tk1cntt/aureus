import asyncio
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import Bar
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.data import BarType
from nautilus_trader.core.datetime import dt_to_unix_nanos
import pandas as pd

class AureusMarketDataClient(LiveMarketDataClient):
    def __init__(self, redis_client, stream_name: str, instrument_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.instrument_id = InstrumentId.from_str(instrument_id)
        self._last_id = "0-0"
        self._running = False

    async def connect(self):
        self._running = True
        asyncio.create_task(self._poll_loop())

    async def disconnect(self):
        self._running = False

    async def _poll_loop(self):
        while self._running:
            await self._poll_market_data_once()
            await asyncio.sleep(0.1)

    async def _poll_market_data_once(self):
        try:
            streams = {self.stream_name: self._last_id}
            # xread block for 1s
            result = await self.redis_client.xread(streams, count=100, block=1000)
            if not result:
                return
            for stream, messages in result:
                for idx, message in messages:
                    self._last_id = idx
                    self._handle_message(message)
        except Exception as e:
            self.log.error(f"Error polling market data: {e}")

    def _handle_message(self, message: dict):
        try:
            # Parse dict
            open_price = float(message[b"open"])
            high_price = float(message[b"high"])
            low_price = float(message[b"low"])
            close_price = float(message[b"close"])
            volume = float(message[b"volume"])
            ts_ms = int(message[b"timestamp"])

            bar_type = BarType.from_str(f"{self.instrument_id.value}-1-MINUTE-LAST-EXTERNAL")
            
            bar = Bar(
                bar_type=bar_type,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                ts_event=ts_ms * 1_000_000,
                ts_init=ts_ms * 1_000_000,
            )
            self.msg_bus.publish(bar)
        except (KeyError, ValueError) as e:
            self.log.error(f"Malformed bar data: {message}, error: {e}")
