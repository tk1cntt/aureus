import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from engine.logging_common import get_logger
from engine.time_normalization import (
    broker_datetime_from_utc_seconds,
    is_eu_dst_utc,
    parse_epoch_seconds,
)
from .base import BaseSignal

logger = get_logger(__name__)


class SessionSignal(BaseSignal):
    """
    Identifies trading sessions based on canonical UTC candle timestamp.
    Broker display time uses dynamic broker DST:
    Winter: GMT+3 | Summer: GMT+4
    Updates state_obj.current_session for Hybrid Judges.
    """

    def __init__(self, gmt_user: int = 4):
        super().__init__("Broker Session Monitor")
        self.gmt_user = gmt_user

    def is_broker_dst(self, dt: datetime) -> bool:
        """Backward-compatible wrapper for broker DST detection in UTC."""
        return is_eu_dst_utc(dt)

    def _classify_user_session(self, time_user: float) -> str:
        """Classifies New York local time into trading session windows."""
        if 7.0 <= time_user <= 11.0:
            return "ASIA"
        if 14.0 <= time_user <= 17.0:
            return "LONDON"
        if 19.0 <= time_user <= 23.0:
            return "NEW_YORK"
        return "LUNCH_TIME"

    def _extract_last_float(self, df: pd.DataFrame, column: str) -> Optional[float]:
        try:
            return float(df[column].iloc[-1])
        except Exception:
            logger.warning(f"[SessionSignal] Missing or invalid `{column}` value; skipping session update")
            return None

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df is None or df.empty:
            return None

        required_columns = {"t", "o", "h", "l"}
        if not required_columns.issubset(set(df.columns)):
            logger.warning("[SessionSignal] Missing required candle columns; skipping session update")
            return None

        try:
            ts_unix = df["t"].iloc[-1]
        except Exception:
            logger.warning("[SessionSignal] Invalid candle timestamp; skipping session update")
            return None

        dt_utc = datetime.fromtimestamp(ts_unix, tz=timezone.utc)

        # Calculate broker/server time dynamically from canonical UTC.
        dt_broker, broker_offset = broker_datetime_from_utc_seconds(ts_unix)
        is_dst = broker_offset == 4

        # Calculate user-local informational time and New York classification time.
        dt_user = dt_utc + timedelta(hours=self.gmt_user)

        time_user = dt_user.hour + (dt_user.minute / 60.0)
        session = self._classify_user_session(time_user)

        high = self._extract_last_float(df, "h")
        low = self._extract_last_float(df, "l")
        open_px = self._extract_last_float(df, "o")
        if high is None or low is None or open_px is None:
            return None

        if not hasattr(state_obj, "tracking_vars") or not isinstance(getattr(state_obj, "tracking_vars", None), dict):
            state_obj.tracking_vars = {}

        previous_session = str(getattr(state_obj, "current_session", "OFF_MARKET"))
        if session != previous_session:
            logger.info(f"[{state_obj.symbol}][{ts_unix}][{dt_user}] Session Shift {previous_session} -> {session}")
            # Reset session H/L tracking
            state_obj.tracking_vars["session_hlo"] = {
                "session": session,
                "high": high,
                "low": low,
                "open": open_px,
            }
        else:
            # Update existing tracking
            hlo = state_obj.tracking_vars.setdefault(
                "session_hlo",
                {"session": session, "high": high, "low": low, "open": open_px},
            )
            hlo["session"] = session
            hlo["high"] = max(float(hlo.get("high", high)), high)
            hlo["low"] = min(float(hlo.get("low", low)), low)
            hlo.setdefault("open", open_px)

        # Enrich state object
        state_obj.current_session = session

        return {
            "tag": "market_session",
            "session": session,
            "broker_time": dt_broker.strftime("%H:%M"),
            "broker_offset": f"GMT+{broker_offset}",
            "user_time": dt_user.strftime("%H:%M"),
            "is_dst": is_dst,
        }
