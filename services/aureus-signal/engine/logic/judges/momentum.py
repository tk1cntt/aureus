from typing import Dict, Any
from .base import BaseJudge, JudgeResult

class MomentumJudge(BaseJudge):
    """
    Judge that evaluates Market Momentum (RSI, EMA, ATR).
    """
    def __init__(self, weight: float = 0.8):
        super().__init__("MomentumJudge", weight)

    def evaluate(self, state_obj: Any, trigger: Dict[str, Any]) -> JudgeResult:
        """
        Evaluates quantitative price momentum and velocity.
        """
        candle = state_obj.last_candle
        open_p = float(candle['o'])
        high_p = float(candle['h'])
        low_p = float(candle['l'])
        close_p = float(candle['c'])
        vol = float(candle.get('v', 0))
        
        tag = trigger.get('tag', '').lower()
        is_bullish = "bull" in tag or "up" in tag
        
        score = 0.5 # Neutral base
        evidence = {}
        reasons = []

        # 1. EMA Slope (Standardized velocity)
        emas = getattr(state_obj, 'emas', {})
        ema_data = emas.get(21) or emas.get(50)
        atr = getattr(state_obj, 'atr', 0.1) or 0.1
        
        if ema_data:
            raw_slope = ema_data['slope']
            # Normalize slope by ATR: (Price change / Price) / (ATR / Price) = Price change / ATR
            # This makes the slope "number of ATRs per candle"
            normalized_slope = raw_slope / (atr / close_p)
            
            # Align slope with trade direction
            aligned_slope = normalized_slope if is_bullish else -normalized_slope
            
            if aligned_slope > 0.05: # 0.05 ATR per candle is strong
                slope_bonus = min(aligned_slope * 2, 0.3) # Max 0.3 bonus
                score += slope_bonus
                reasons.append(f"Strong normalized velocity (+{slope_bonus:.2f} ATR/c)")
                evidence['normalized_velocity'] = round(aligned_slope, 4)
            elif aligned_slope < -0.02:
                score -= 0.2
                reasons.append("Momentum fading (Deceleration) (-0.2)")

        # 2. Body-to-Range Ratio (Candle Expansion)
        body = abs(close_p - open_p)
        total_range = high_p - low_p
        expansion_ratio = body / total_range if total_range > 0 else 0.5
        if expansion_ratio > 0.7:
            score += 0.1
            reasons.append("Strong candle body expansion (+0.1)")
            evidence['expansion'] = round(expansion_ratio, 2)

        # 3. Volume Intensity
        avg_vol = getattr(state_obj, 'vol_sma_20', vol)
        vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0
        if vol_ratio > 1.5:
            score += 0.1
            reasons.append(f"High volume intensity {vol_ratio:.1f}x (+0.1)")
            evidence['vol_ratio'] = round(vol_ratio, 2)

        reason = " | ".join(reasons) if reasons else "Neutral momentum context"
        
        return JudgeResult(
            score=max(0.0, min(1.0, score)),
            reason=reason,
            evidence=evidence
        )
