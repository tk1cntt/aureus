import hashlib
import logging
from engine.logging_common import get_logger
from collections import defaultdict

import pandas as pd

from .state import SymbolState

logger = get_logger(__name__)
class WindowManager:
    """Manages a sliding window of candles and persistent state for each symbol."""

    _TIMEFRAME_SECONDS = {
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
        "D1": 86400,
    }

    def __init__(self, max_window=3000):
        self.max_window = max_window
        self.windows = defaultdict(list)
        self.window_dicts = defaultdict(dict)  # O(1) lookup: t -> candle reference
        self.dfs = {}
        self.states = {}
        self.backfill_status = {}  # symbol -> {'status': str, 'reason': str, 'updated_at': int}
        self.window_integrity = {}  # symbol -> {'is_contiguous_window': bool, ...}

    def reset(self, symbol):
        """Clears memory state for a specific symbol."""
        if symbol in self.windows:
            del self.windows[symbol]
        if symbol in self.window_dicts:
            del self.window_dicts[symbol]
        if symbol in self.dfs:
            del self.dfs[symbol]
        if symbol in self.states:
            del self.states[symbol]
        if symbol in self.backfill_status:
            del self.backfill_status[symbol]
        if symbol in self.window_integrity:
            del self.window_integrity[symbol]

    def _timeframe_to_seconds(self, tf):
        return self._TIMEFRAME_SECONDS.get(str(tf).strip().upper(), 60)

    def _build_integrity_metadata(self, window):
        if not window:
            return {
                "is_contiguous_window": False,
                "window_start": None,
                "window_end": None,
                "window_hash": None,
                "reason": "UNINITIALIZED",
            }

        timestamps = [int(c["t"]) for c in window]
        window_start = timestamps[0]
        window_end = timestamps[-1]
        tf_seconds = self._timeframe_to_seconds(window[-1].get("tf", "M1"))

        if len(timestamps) <= 1:
            is_contiguous = True
            reason = "OK"
        else:
            deltas = [curr - prev for prev, curr in zip(timestamps, timestamps[1:])]
            is_contiguous = all(delta == tf_seconds for delta in deltas)
            reason = "OK" if is_contiguous else "GAP_OR_OUT_OF_ORDER"

        hash_payload = "|".join(str(ts) for ts in timestamps)
        window_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

        return {
            "is_contiguous_window": is_contiguous,
            "window_start": window_start,
            "window_end": window_end,
            "window_hash": window_hash,
            "reason": reason,
        }

    def update(self, symbol, data):
        """Append a new candle, update state, and return symbols context."""
        if symbol not in self.states:
            self.states[symbol] = SymbolState(symbol)

        state = self.states[symbol]
        candle = {
            "t": int(data["t"]),
            "o": float(data["o"]),
            "h": float(data["h"]),
            "l": float(data["l"]),
            "c": float(data["c"]),
            "v": float(data["v"]),
            "tf": data.get("tf", "M1"),
        }

        window = self.windows[symbol]
        window_dict = self.window_dicts[symbol]

        if window and window[-1]["t"] == candle["t"]:
            window[-1] = candle
            window_dict[candle["t"]] = candle
        elif candle["t"] in window_dict:
            for idx, existing in enumerate(window):
                if existing["t"] == candle["t"]:
                    window[idx] = candle
                    break
            window_dict[candle["t"]] = candle
        else:
            window.append(candle)
            window_dict[candle["t"]] = candle
            if len(window) > 1 and candle["t"] < window[-2]["t"]:
                window.sort(key=lambda x: x["t"])

        if len(window) > self.max_window:
            removed_candles = window[:-self.max_window]
            self.windows[symbol] = window[-self.max_window:]
            window = self.windows[symbol]
            for removed in removed_candles:
                window_dict.pop(removed["t"], None)

        df = pd.DataFrame(window)
        self.dfs[symbol] = df

        integrity = self._build_integrity_metadata(window)
        self.set_window_integrity(
            symbol,
            is_contiguous_window=integrity["is_contiguous_window"],
            window_start=integrity["window_start"],
            window_end=integrity["window_end"],
            window_hash=integrity["window_hash"],
            reason=integrity["reason"],
            updated_at=candle["t"],
        )

        state.update_with_candle(candle)

        return df, state

    def get_df(self, symbol):
        return self.dfs.get(symbol)

    def set_backfill_status(self, symbol, status, reason=None, updated_at=None):
        """Sets explicit backfill readiness metadata for a symbol."""
        self.backfill_status[symbol] = {
            "status": str(status).strip().upper() if status is not None else "NOT_READY",
            "reason": reason or "UNSPECIFIED",
            "updated_at": int(updated_at) if updated_at is not None else None,
        }

    def get_backfill_status(self, symbol):
        """Returns explicit backfill readiness metadata. Defaults to NOT_READY."""
        return self.backfill_status.get(
            symbol,
            {
                "status": "NOT_READY",
                "reason": "UNINITIALIZED",
                "updated_at": None,
            },
        )

    def set_window_integrity(
        self,
        symbol,
        is_contiguous_window,
        window_start=None,
        window_end=None,
        window_hash=None,
        reason=None,
        updated_at=None,
    ):
        """Sets explicit contiguous-window integrity metadata for a symbol."""
        self.window_integrity[symbol] = {
            "is_contiguous_window": bool(is_contiguous_window),
            "window_start": int(window_start) if window_start is not None else None,
            "window_end": int(window_end) if window_end is not None else None,
            "window_hash": window_hash,
            "reason": reason or "UNSPECIFIED",
            "updated_at": int(updated_at) if updated_at is not None else None,
        }

    def get_window_integrity(self, symbol):
        """Returns contiguous-window integrity metadata. Defaults to fail-closed."""
        return self.window_integrity.get(
            symbol,
            {
                "is_contiguous_window": False,
                "window_start": None,
                "window_end": None,
                "window_hash": None,
                "reason": "UNINITIALIZED",
                "updated_at": None,
            },
        )
