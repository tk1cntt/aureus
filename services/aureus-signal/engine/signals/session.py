import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import pandas as pd

from engine.logging_common import get_logger
from .base import BaseSignal

logger = get_logger(__name__)


class SessionSignal(BaseSignal):
    """
    Identifies trading sessions based on Broker Server Time (Dynamic DST).
    Winter: GMT+2 | Summer: GMT+3
    Updates state_obj.current_session for Hybrid Judges.
    """

    def __init__(self, gmt_user: int = 7):
        super().__init__("Broker Session Monitor")
        self.gmt_user = gmt_user

    def is_broker_dst(self, dt: datetime) -> bool:
        """
        Detects if a date is in European DST (Last Sunday of March to Last Sunday of Oct).
        Most Forex brokers follow this schedule (EET/EEST).
        """
        year = dt.year
        # Last Sunday of March
        dst_start = datetime(year, 3, 31, 1, tzinfo=timezone.utc)
        dst_start -= timedelta(days=(dst_start.weekday() + 1) % 7)

        # Last Sunday of October
        dst_end = datetime(year, 10, 31, 1, tzinfo=timezone.utc)
        dst_end -= timedelta(days=(dst_end.weekday() + 1) % 7)

        return dst_start <= dt < dst_end

    def _classify_user_session(self, time_user: float) -> str:
        """Classifies user-local time (GMT offset based) into session windows."""
        if 7.0 <= time_user < 11.0:
            return "ASIA"
        if 14.0 <= time_user < 17.0:
            return "LONDON"
        if 19.0 <= time_user < 23.0:
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
            ts_unix = int(float(df["t"].iloc[-1]))
        except Exception:
            logger.warning("[SessionSignal] Invalid candle timestamp; skipping session update")
            return None

        dt_utc = datetime.fromtimestamp(ts_unix, tz=timezone.utc)

        # Determine Broker Offset (Winter GMT+2, Summer GMT+3)
        is_dst = self.is_broker_dst(dt_utc)
        broker_offset = 3 if is_dst else 2

        # Calculate Broker Time & User Time (GMT+7 by default)
        dt_broker = dt_utc + timedelta(hours=broker_offset)
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
            logger.info(f"[{state_obj.symbol}] [calculate] 1... Session Shift: {previous_session} -> {session}")
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
