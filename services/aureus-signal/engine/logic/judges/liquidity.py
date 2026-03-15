from typing import Dict, Any
from .base import BaseJudge, JudgeResult

class LiquidityJudge(BaseJudge):
    """
    Judge that evaluates Liquidity Sweep quality.
    """
    def __init__(self, weight: float = 1.2): # Liquidity is high priority
        super().__init__("LiquidityJudge", weight)

    def evaluate(self, state_obj: Any, trigger: Dict[str, Any]) -> JudgeResult:
        """
        Evaluates Macro Liquidity context: Equal H/L and Session Extremes.
        """
        tag = trigger.get('tag', '').lower()
        is_bullish = "bull" in tag or "up" in tag
        last_price = float(state_obj.last_candle['c'])
        
        score = 0.5 # Neutral base
        evidence = {}
        reasons = []

        # ATR-Normalized Thresholds
        atr = getattr(state_obj, 'atr', 0.1) or 0.1 # Fallback to 0.1 if not calculated
        session_thresh = 0.2 * atr
        eq_thresh = 0.05 * atr

        # 1. Session Liquidity (Asian/London/NY extremes)
        session_hlo = state_obj.tracking_vars.get('session_hlo', {})
        if session_hlo:
            target_level = session_hlo['low'] if is_bullish else session_hlo['high']
            distance = abs(last_price - target_level)
            
            # Use ATR-normalized distance
            if distance < session_thresh:
                score += 0.2
                reasons.append(f"Proximity to {session_hlo['session']} extreme (+0.2)")
                evidence['session_dist_atr'] = round(distance / atr, 2)

        # 2. Equal Highs/Lows (EQH/EQL)
        swings = state_obj.swing_points[-10:] # Last 10 swings
        if len(swings) >= 2:
            relevant_swings = [s for s in swings if (s['is_high'] != is_bullish)] 
            if len(relevant_swings) >= 2:
                p1 = relevant_swings[-1]['price']
                p2 = relevant_swings[-2]['price']
                if abs(p1 - p2) < eq_thresh: # Normalized threshold
                    score += 0.3
                    reasons.append("Equal Highs/Lows detected (+0.3)")
                    evidence['eq_dist_atr'] = round(abs(p1 - p2) / atr, 3)

        # 3. Liquidity Runway (FVG check)
        # If there are unmitigated FVGs in the direction of the trade, it's a "runway"
        fvgs = [f for f in state_obj.fvgs if f['state'] != 'BROKEN']
        runway_count = 0
        for f in fvgs:
            if is_bullish and f['bottom'] > last_price: runway_count += 1
            if not is_bullish and f['top'] < last_price: runway_count += 1
            
        if runway_count > 0:
            score += 0.1
            reasons.append("Liquidity runway detected (FVGs) (+0.1)")
            evidence['runway_fvgs'] = runway_count

        reason = " | ".join(reasons) if reasons else "Neutral liquidity landscape"
        
        return JudgeResult(
            score=max(0.0, min(1.0, score)),
            reason=reason,
            evidence=evidence
        )
