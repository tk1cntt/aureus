from typing import Dict, Any
import logging
from .base import BaseJudge, JudgeResult

logger = logging.getLogger("aureus-signal.judges.patterns")

class MultiPatternJudge(BaseJudge):
    """
    Judge that recognizes complex Price Action patterns beyond simple wicks.
    Handles: Engulfing, Accumulation (Tightness), and Volume Confirmation.
    """
    def __init__(self, weight: float = 1.0):
        super().__init__("MultiPatternJudge", weight, can_veto=True, veto_threshold=0.35)

    def supports_tag(self, tag: str) -> bool:
        # This judge supports all technical setups for pattern confirmation
        return True

    def evaluate(self, state_obj: Any, trigger: Dict[str, Any]) -> JudgeResult:
        tag = trigger.get('tag', '').lower()
        is_bullish_trigger = "up" in tag or "bull" in tag or "long" in tag
        
        # 1. Access Data
        candle = state_obj.last_candle
        open_p = float(candle['o'])
        high_p = float(candle['h'])
        low_p = float(candle['l'])
        close_p = float(candle['c'])
        vol = float(candle.get('v', 1.0))
        
        is_bull_candle = close_p > open_p
        body = abs(close_p - open_p)
        
        # 2. Engulfing Pattern Logic
        s_engulfing = 0.0
        engulfing_type = "None"
        
        prev_candle = getattr(state_obj, 'prev_candle', None)
        if prev_candle:
            p_open = float(prev_candle['o'])
            p_close = float(prev_candle['c'])
            p_body = abs(p_close - p_open)
            p_is_bull = p_close > p_open
            
            # Engulfing: Current body covers previous body AND direction is opposite
            if is_bull_candle != p_is_bull:
                coverage = body / p_body if p_body > 0 else 2.0
                if coverage >= 1.5:
                    s_engulfing = min(coverage / 2.0, 1.0)
                    engulfing_type = "BULLISH_ENGULFING" if is_bull_candle else "BEARISH_ENGULFING"
                elif coverage >= 1.1:
                    s_engulfing = 0.6
                    engulfing_type = "BULLISH_ENGULFING" if is_bull_candle else "BEARISH_ENGULFING"
        
        # 3. Directional Alignment & Fakeout Detection
        # Scenario: Trigger is UP (CHOCH_UP/BOS_UP) but we get a BEARISH pattern -> FAILEDBREAKOUT
        is_pattern_aligned = (is_bull_candle == is_bullish_trigger)
        is_fakeout = (s_engulfing >= 0.6) and not is_pattern_aligned
        
        # 4. Accumulation (Coiling) Logic
        s_coiling = 0.5
        atr = getattr(state_obj, 'atr', 0.0)
        if atr > 0:
            avg_atr = getattr(state_obj, 'atr_sma_20', atr)
            tightness = atr / avg_atr if avg_atr > 0 else 1.0
            if tightness < 0.8: s_coiling = 0.9
        
        # 5. Volume Surge
        avg_vol = getattr(state_obj, 'vol_sma_20', vol)
        s_vol = min(vol / avg_vol, 2.0) / 2.0 if avg_vol > 0 else 0.5
        
        # 6. Composite Ranking & Veto Decision
        score = (s_coiling * 0.4) + (s_vol * 0.6) # Default base
        
        if s_engulfing > 0:
            if is_pattern_aligned:
                # Positive confirmation: Strong Engulfing in trigger direction
                score = max(score, s_engulfing * 0.9 + 0.1)
            else:
                # Fakeout/Failed Breakout: Engulfing against trigger direction
                score = 0.1 # Force rejection
        
        # Determine Verdict
        decision_reason = f"Pattern: {engulfing_type if engulfing_type != 'None' else 'Standard'}"
        if is_fakeout:
            decision_reason = f"VETO: Failed Breakout detected ({engulfing_type} against trigger)"

        return JudgeResult(
            score=round(score, 2),
            reason=decision_reason,
            evidence={
                "S_engulfing": round(s_engulfing, 2),
                "engulfing_type": engulfing_type,
                "is_aligned": is_pattern_aligned,
                "is_fakeout": is_fakeout,
                "S_coiling": round(s_coiling, 2),
                "S_vol": round(s_vol, 2)
            },
            can_override=(s_engulfing >= 0.7 and is_pattern_aligned) # Only aligned strong patterns can override
        )
