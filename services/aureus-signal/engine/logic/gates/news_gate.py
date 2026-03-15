from .base import BaseGate, GateResult
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

class NewsGate(BaseGate):
    """
    Prevents trading during High Impact news events.
    Applies 'Holiday' mode for sweep-only setups.
    """
    
    def __init__(self, halt_window_mins: int = 15):
        super().__init__("NewsGate")
        self.halt_window = halt_window_mins

    def check(self, state_obj: Any, context: Dict[str, Any]) -> GateResult:
        current_time_ts = int(datetime.now(timezone(timedelta(hours=7))).timestamp())
        
        # 1. Check for High Impact News
        news_events = getattr(state_obj, 'news_events', [])
        symbol_currs = [state_obj.symbol[:3], state_obj.symbol[3:6], state_obj.symbol] # e.g. XAU, USD, XAUUSD
        
        for event in news_events:
            event_ts = event['timestamp']
            impact = event['impact']
            country = event['country']
            
            # Match currency
            if country not in symbol_currs:
                continue
                
            # A. High Impact Halt
            if impact == "High":
                diff_secs = abs(current_time_ts - event_ts)
                if diff_secs <= self.halt_window * 60:
                    return GateResult(
                        is_passed=False, 
                        reason=f"🚨 High Impact News: {event['title']} ({country}) at {event['date_gmt7']}"
                    )
            
            # B. Holiday Detection
            if impact == "Holiday":
                # Only care if it's TODAY
                context['is_holiday_mode'] = True
                context['holiday_title'] = event['title']

        return GateResult(is_passed=True, reason="Normal market conditions", metadata={"impact": "None/Low"})
