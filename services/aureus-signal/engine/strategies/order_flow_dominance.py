import json
from .base import BaseStrategy
import pandas as pd
from typing import Dict, Any, Optional

class OrderFlowDominanceStrategy(BaseStrategy):
    """
    High-probability Order Flow Dominance Strategy.
    Targets market states where one side clearly dominates (e.g. many Bearish OBs, no Bullish).
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            config.get('name', 'ORDER_FLOW_DOM'), 
            strategy_id=config.get('id', 0), 
            weight=config.get('weight', 9.0)
        )
        self.min_aci = config.get('min_score_threshold', 65)
        self.min_ob_ratio = config.get('min_ob_ratio', 3.0) # 3:1 dominance
        self.lookback_obs = config.get('lookback_obs', 10) # Look at last 10 OBs
        self.config = config

    def calculate_ob_imbalance(self, obs: list) -> Dict[str, Any]:
        """Calculates the ratio of Bullish vs Bearish OBs."""
        recent_obs = obs[-self.lookback_obs:]
        bull_count = sum(1 for ob in recent_obs if ob.get('ob_type') == 'BULLISH')
        bear_count = sum(1 for ob in recent_obs if ob.get('ob_type') == 'BEARISH')
        
        ratio = 0.0
        dominant_type = "NEUTRAL"
        
        if bear_count == 0 and bull_count > 0:
            ratio = float(bull_count)
            dominant_type = "BULLISH"
        elif bull_count == 0 and bear_count > 0:
            ratio = float(bear_count)
            dominant_type = "BEARISH"
        elif bear_count > 0 and bull_count > 0:
            if bull_count >= bear_count:
                ratio = bull_count / bear_count
                dominant_type = "BULLISH"
            else:
                ratio = bear_count / bull_count
                dominant_type = "BEARISH"
                
        return {
            "ratio": round(ratio, 2),
            "dominant_type": dominant_type,
            "counts": {"bull": bull_count, "bear": bear_count}
        }

    def evaluate(self, df: pd.DataFrame, signals: Dict[str, Any], state_obj: Any) -> Optional[Dict[str, Any]]:
        # 1. Macro Trend Filter
        trend = getattr(state_obj, 'htf_trend', "NEUTRAL")
        if trend == "NEUTRAL":
            return None
            
        # 2. Order Flow Imbalance Calculation
        obs = getattr(state_obj, 'obs', [])
        if not obs:
            return None
            
        imbalance = self.calculate_ob_imbalance(obs)
        if imbalance['ratio'] < self.min_ob_ratio:
            return None
            
        # 3. Alignment Check (Dominance must match Trend)
        is_bullish_dom = imbalance['dominant_type'] == "BULLISH"
        if (is_bullish_dom and trend != "BULLISH") or (not is_bullish_dom and trend != "BEARISH"):
            return None
            
        # 4. Trigger: Pullback Sweep to Dominant OB
        sweep_tag = "SWEEP_BULL" if is_bullish_dom else "SWEEP_BEAR"
        sweep_signal = signals.get(sweep_tag)
        
        if not sweep_signal:
            return None
            
        # 5. Final Scoring
        base_score = 7.5
        ratio_bonus = min((imbalance['ratio'] / self.min_ob_ratio) * 0.5, 1.5) # Max 1.5 bonus for extreme ratio
        total_score = base_score + ratio_bonus
        
        # Session bonus (Optional, but good for ACI 90+)
        session = getattr(state_obj, 'current_session', 'LUNCH_TIME')
        if session in ("LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"):
            total_score += 1.0

        if total_score >= self.min_aci / 10.0:
            return {
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "direction": "BUY" if is_bullish_dom else "SELL",
                "score": round(total_score, 2),
                "reason": f"Order Flow Dominance ({imbalance['ratio']}:1 {imbalance['dominant_type']}) + {sweep_tag} @ {session}",
                "t": int(df.iloc[-1]['t']),
                "details": json.dumps({
                    "imbalance": imbalance,
                    "trend": trend,
                    "session": session,
                    "sweep": sweep_signal
                })
            }
            
        return None
