import json
from .base import BaseStrategy
import pandas as pd
from typing import Dict, Any, Optional

class TrendContinuationStrategy(BaseStrategy):
    """
    High-probability SMC Trend Continuation Strategy.
    Conditions: 
    1. Macro Trend (EMA 200) is Aligned.
    2. Recent BOS/CHOCH in trend direction.
    3. Session is High-Liquidity (London/NY).
    4. Price sweeps an internal level (Pullback) before continuation.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            config.get('name', 'TREND_CONT'), 
            strategy_id=config.get('id', 0), 
            weight=config.get('weight', 8.5)
        )
        self.min_aci = config.get('min_score_threshold', 60)
        # Dynamic Configuration from DB 'config' column
        self.config = config
        self.allowed_sessions = config.get('allowed_sessions', ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"])
        self.session_bonus = config.get('session_bonus', 1.5)
        self.lookback_candles = config.get('lookback_candles', 20)
        self.ema_alignment_bonus = config.get('ema_alignment_bonus', 0.5)

    def evaluate(self, df: pd.DataFrame, signals: Dict[str, Any], state_obj: Any) -> Optional[Dict[str, Any]]:
        # 1. Trend Filter
        trend = getattr(state_obj, 'htf_trend', "NEUTRAL")
        if trend == "NEUTRAL":
            return None
            
        is_bullish = trend == "BULLISH"
        
        # 2. Session Filter (Dynamic from config)
        session = getattr(state_obj, 'current_session', 'LUNCH_TIME')
        session_bonus = 0.0
        if session in self.allowed_sessions:
            session_bonus = self.session_bonus
        if session == "LONDON_NY_OVERLAP":
            session_bonus += 0.5 # Extra boost for overlap
            
        # 3. Look for Recent Structural Break (Dynamic lookback)
        history = state_obj.signal_history[-self.lookback_candles:]
        break_tag = "CHOCH_UP" if is_bullish else "CHOCH_DN"
        has_recent_break = any(s['tag'] == break_tag for s in history)
        
        if not has_recent_break:
            return None
            
        # 4. Look for Pullback Sweep (THE TRIGGER)
        sweep_tag = "SWEEP_BULL" if is_bullish else "SWEEP_BEAR"
        sweep_signal = signals.get(sweep_tag)
        
        if not sweep_signal:
            return None
            
        # 5. Calculate Strategy-Specific Score
        base_score = 7.0 
        total_score = base_score + session_bonus
        
        # Add bonus for EMA alignment (Dynamic from config)
        emas = getattr(state_obj, 'emas', {})
        ema_21 = emas.get(21)
        if ema_21 and self.ema_alignment_bonus > 0:
            slope = ema_21['slope']
            if (is_bullish and slope > 0) or (not is_bullish and slope < 0):
                total_score += self.ema_alignment_bonus

        # Log progress for Dashboard Monitoring
        if not hasattr(state_obj, 'strategy_progress'):
            state_obj.strategy_progress = {}
            
        progress_data = {
            "strategy": self.name,
            "progress_pct": 100,
            "status": "MATCHED",
            "reason": f"Trend {trend} + Session {session} + Sweep",
            "t": int(df.iloc[-1]['t'])
        }
        state_obj.strategy_progress[self.name] = progress_data

        if total_score >= self.min_aci / 10.0:
            return {
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "direction": "BUY" if is_bullish else "SELL",
                "score": total_score,
                "reason": f"Trend Continuation: {trend} Trend + {break_tag} + {sweep_tag} @ {session}",
                "t": int(df.iloc[-1]['t']),
                "details": json.dumps({
                    "trend": trend,
                    "session": session,
                    "session_bonus": session_bonus,
                    "has_break": has_recent_break,
                    "sweep_data": sweep_signal
                })
            }
            
        return None
