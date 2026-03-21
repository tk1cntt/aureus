import logging
from engine.logging_common import get_logger
import pandas as pd
from datetime import datetime, timezone, timedelta
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = get_logger(__name__)
class SessionSignal(BaseSignal):
    """
    Identifies trading sessions based on Broker Server Time (Dynamic DST).
    Winter: GMT+2 | Summer: GMT+3
    Updates state_obj.current_session for Hybrid Judges.
    """
    def __init__(self, gmt_user: int = 7):
        super().__init__(f"Broker Session Monitor")
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

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df.empty:
            return None
            
        # 1. Get current candle timestamp (Unix Epoch)
        ts_unix = int(df['t'].iloc[-1])
        dt_utc = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
        
        # 2. Determine Broker Offset (Winter GMT+2, Summer GMT+3)
        # Broker time is the reference for the candle 't'
        is_dst = self.is_broker_dst(dt_utc)
        broker_offset = 3 if is_dst else 2
        
        # 3. Calculate Broker Time & User Time (GMT+7)
        dt_broker = dt_utc + timedelta(hours=broker_offset)
        dt_user = dt_utc + timedelta(hours=self.gmt_user)
        
        hour_user = dt_user.hour
        min_user = dt_user.minute
        time_user = hour_user + (min_user / 60.0)
        
        # 4. Define Session Windows based on User GMT+7 Benchmarks
        # ASIA: 7h-11h
        # LONDON: 14h-17h
        # NEWYORK: 19h-23h
        # Rest: LUNCH_TIME
        
        session = "LUNCH_TIME"
        high = float(df['h'].iloc[-1])
        low = float(df['l'].iloc[-1])
        
        if 7.0 <= time_user < 11.0:
            session = "ASIA"
        elif 14.0 <= time_user < 17.0:
            session = "LONDON"
        elif 19.0 <= time_user < 23.0:
            session = "NEW_YORK"
        elif 15.0 <= time_user < 19.0: # Explicitly overlap if needed, but user gave 14-17 and 19-23
            # If there's a specific overlap window desired, we'd add it here.
            # For now, following user's specific blocks.
            session = "LUNCH_TIME" # 17h-19h is gap per user
            
        if session != state_obj.current_session:
            logger.info(f"[{state_obj.symbol}] [calculate] 1... Session Shift: {state_obj.current_session} -> {session}")
            # Reset session H/L tracking
            state_obj.tracking_vars['session_hlo'] = {
                "session": session,
                "high": high,
                "low": low,
                "open": float(df['o'].iloc[-1])
            }
        else:
            # Update existing tracking
            hlo = state_obj.tracking_vars.setdefault('session_hlo', {"session": session, "high": high, "low": low})
            hlo['high'] = max(hlo.get('high', high), high)
            hlo['low'] = min(hlo.get('low', low), low)

        # Enrich state object
        state_obj.current_session = session
        
        return {
            "tag": "market_session",
            "session": session,
            "broker_time": dt_broker.strftime("%H:%M"),
            "broker_offset": f"GMT+{broker_offset}",
            "user_time": dt_user.strftime("%H:%M"),
            "is_dst": is_dst
        }
