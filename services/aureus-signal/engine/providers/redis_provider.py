"""Redis stream-backed market data provider.

Wraps existing Redis consumer group pattern into MarketDataProvider interface.
"""

import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from engine.logging_common import get_logger
from .base import MarketDataProvider

logger = get_logger(__name__)


class RedisMarketDataProvider(MarketDataProvider):
    """Reads OHLCV candles from Redis streams (existing Aureus pipeline).

    This is the default provider — wraps the same consumption pattern
    used by run_signal_engine() since v1.0.
    """

    def __init__(
        self,
        redis_client: Any,
        db_pool: Any,
        group_name: str = "aureus-signal-group",
        consumer_name: Optional[str] = None,
    ):
        self._redis = redis_client
        self._db_pool = db_pool
        self._group_name = group_name
        self._consumer_name = consumer_name or f"consumer-{os.getenv('HOSTNAME', 'local')}"

    async def setup(self) -> None:
        """No-op — consumer groups created per-symbol in subscribe()."""
        pass

    async def _ensure_group(self, stream_key: str) -> None:
        """Creates consumer group if it doesn't exist."""
        try:
            await self._redis.xgroup_create(stream_key, self._group_name, id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"[RedisMarketDataProvider] Failed to create group on {stream_key}: {e}")

    async def subscribe(self, symbol: str) -> AsyncIterator[Dict[str, Any]]:
        """Yield candle dicts from Redis stream for a symbol.

        Reads from aureus:stream:{symbol}:candle using xreadgroup.
        Yields dicts with keys: {t, o, h, l, c, v, symbol}.
        ACKs each message after yielding.
        """
        stream_key = f"aureus:stream:{symbol}:candle"
        await self._ensure_group(stream_key)

        while True:
            try:
                messages = await self._redis.xreadgroup(
                    self._group_name,
                    self._consumer_name,
                    {stream_key: ">"},
                    count=500,
                    block=5000,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for entry_id, data in entries:
                        msg_type = data.get("type")
                        if not msg_type:
                            msg_type = "CANDLE" if ":candle" in stream_key else "UNKNOWN"

                        if msg_type != "CANDLE":
                            await self._redis.xack(stream_key, self._group_name, entry_id)
                            continue

                        # Normalize timestamp
                        ts_ms = int(data.get("t", 0))
                        ts_unix = ts_ms // 1000 if ts_ms > 1e12 else ts_ms

                        candle = {
                            "t": str(ts_unix),
                            "o": data.get("o", "0"),
                            "h": data.get("h", "0"),
                            "l": data.get("l", "0"),
                            "c": data.get("c", "0"),
                            "v": data.get("v", data.get("vol", "0")),
                            "symbol": data.get("symbol", symbol),
                        }

                        yield candle
                        await self._redis.xack(stream_key, self._group_name, entry_id)

            except Exception as e:
                if "NOGROUP" in str(e):
                    await self._ensure_group(stream_key)
                    continue
                logger.error(f"[RedisMarketDataProvider] subscribe error for {symbol}: {e}")
                import asyncio
                await asyncio.sleep(1)

    async def get_historical(self, symbol: str, limit: int = 1500) -> List[Dict[str, Any]]:
        """Fetch historical candles from TimescaleDB, oldest-first.

        Returns list of dicts with keys: {t, o, h, l, c, v, symbol}.
        """
        rows = await self._db_pool.fetch(
            """
            SELECT time, open, high, low, close, volume
            FROM aureus_candles
            WHERE symbol = $1
            ORDER BY time DESC
            LIMIT $2
            """,
            symbol,
            limit,
        )

        # Return oldest-first
        candles = []
        for row in reversed(rows):
            candles.append({
                "t": str(int(row["time"].timestamp())),
                "o": str(row["open"]),
                "h": str(row["high"]),
                "l": str(row["low"]),
                "c": str(row["close"]),
                "v": str(row["volume"]),
                "symbol": symbol,
            })

        return candles

    async def teardown(self) -> None:
        """No-op — Redis/DB lifecycle managed by caller."""
        pass
