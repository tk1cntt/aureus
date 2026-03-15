from typing import Dict, Any
import logging
from .base import BaseJudge, JudgeResult

logger = logging.getLogger("aureus-signal.judges.structure")

class CHOCHJudge(BaseJudge):
    """
    Judge that evaluates Market Structure Breakouts (CHOCH).
    Focuses on Body Strength and Displacement over levels.
    """
    def __init__(self, weight: float = 1.0):
        super().__init__("CHOCHJudge", weight, can_veto=True, veto_threshold=0.35)

    def supports_tag(self, tag: str) -> bool:
        tag = tag.lower()
        return "choch" in tag or "breakout" in tag

    def evaluate(self, state_obj: Any, trigger: Dict[str, Any]) -> JudgeResult:
        tag = trigger.get('tag', '').lower()
        
        # 1. Access Candle Data & Pivot Levels
        candle = state_obj.last_candle
        open_p = float(candle['o'])
        high_p = float(candle['h'])
        low_p = float(candle['l'])
        close_p = float(candle['c'])
        vol = float(candle.get('v', 1.0))
        
        pivot_level = trigger.get('pivot_price') or trigger.get('level_price')
        if not pivot_level: pivot_level = close_p 

        # 2. Match: Body-to-Wick Ratio (S_break)
        body = abs(close_p - open_p)
        total_range = high_p - low_p
        s_break = body / total_range if total_range > 0 else 0.5
        
        # 3. Match: Displacement over level (S_disp)
        displacement = abs(close_p - pivot_level)
        s_disp = min(displacement / total_range, 1.0) if total_range > 0 else 0.5

        # 4. Match: Volume Ratio vs 20 SMA (S_vol)
        avg_vol = getattr(state_obj, 'vol_sma_20', vol) 
        s_vol = min(vol / avg_vol, 2.0) / 2.0 if avg_vol > 0 else 0.5

        # 5. Match: HTF Alignment (S_trend)
        htf_trend = getattr(state_obj, 'htf_trend', "NEUTRAL")
        is_bullish = "up" in tag or "bull" in tag
        aligned = (htf_trend == "BULLISH" and is_bullish) or (htf_trend == "BEARISH" and not is_bullish)
        s_trend = 1.0 if aligned else 0.5
        if htf_trend == "NEUTRAL": s_trend = 0.75

        # Formula: Balanced for breakout
        score = (s_break * 0.3) + (s_disp * 0.3) + (s_vol * 0.2) + (s_trend * 0.2)
        
        # 6. Session Multiplier
        session = getattr(state_obj, 'current_session', 'OTHER')
        session_mult = 1.0
        if session == "LONDON_NY_OVERLAP": session_mult = 1.2
        elif session in ("LONDON", "NEW_YORK"): session_mult = 1.1
        elif session == "ASIA": session_mult = 0.9
        elif session == "LUNCH_TIME": session_mult = 0.7 # Penalize breakouts in lunch
        else: session_mult = 0.6
        
        final_score = score * session_mult
        
        return JudgeResult(
            score=max(0.0, min(1.0, final_score)),
            reason=f"CHOCH Quality: {final_score:.2f} ({tag} @ {session})",
            evidence={
                "S_break": round(s_break, 3),
                "S_disp": round(s_disp, 3),
                "S_vol": round(s_vol, 3),
                "S_trend": round(s_trend, 3),
                "session_mult": session_mult
            }
        )

class SweepJudge(BaseJudge):
    """
    Judge that evaluates Liquidity Hunts (Stop Hunts / Sweeps).
    Focuses on Rejection wicks and Institutional OB context.
    """
    def __init__(self, weight: float = 1.0):
        super().__init__("SweepJudge", weight)

    def supports_tag(self, tag: str) -> bool:
        tag = tag.lower()
        return "stophunt" in tag or "sweep" in tag

    def evaluate(self, state_obj: Any, trigger: Dict[str, Any]) -> JudgeResult:
        tag = trigger.get('tag', '').lower()
        
        # 1. Access Data
        candle = state_obj.last_candle
        open_p = float(candle['o'])
        high_p = float(candle['h'])
        low_p = float(candle['l'])
        close_p = float(candle['c'])
        
        # 2. Rejection Strength (S_rej)
        # For Sweep Bullish: Price went down and closed back up (Long lower wick relative to candle)
        is_bull_sweep = "bull" in tag or "up" in tag
        total_range = high_p - low_p
        if is_bull_sweep:
            rejection_wick = abs(close_p - low_p) if close_p > open_p else abs(open_p - low_p)
        else:
            rejection_wick = abs(high_p - close_p) if close_p < open_p else abs(high_p - open_p)
            
        s_rej = min(rejection_wick / total_range, 1.0) if total_range > 0 else 0.5

        # 3. Context Fidelity (S_fid)
        # High fidelity (1.0) for FVG-gapped pairs, 0.7 for Overlap.
        s_fid = trigger.get('fidelity', 0.5)

        # 4. Trend Context (S_trend)
        # Sweeps are often valid counter-trend in Sideways/Distribution
        htf_trend = getattr(state_obj, 'htf_trend', "NEUTRAL")
        s_trend = 1.0 if htf_trend == "NEUTRAL" else 0.8
        
        # 5. Base Score
        if trigger.get('source_type') == "ST_FVG_PAIR":
            score = 1.0 # Force absolute top quality per user rule
        else:
            score = (s_rej * 0.4) + (s_fid * 0.4) + (s_trend * 0.2)

        # 6. Session Multiplier
        session = getattr(state_obj, 'current_session', 'OTHER')
        session_mult = 1.0
        if session == "LUNCH_TIME": session_mult = 1.0 # No penalty for sweeps in lunch
        elif session == "ASIA": session_mult = 0.9
        elif session in ("LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"): session_mult = 1.1
        else: session_mult = 0.6
        
        final_score = score * session_mult
        
        return JudgeResult(
            score=max(0.0, min(1.0, final_score)),
            reason=f"Sweep Quality: {final_score:.2f} ({trigger.get('source_type')} @ {session})",
            evidence={
                "S_rejection": round(s_rej, 3),
                "S_fidelity": s_fid,
                "S_trend": s_trend,
                "session_mult": session_mult,
                "source_type": trigger.get('source_type')
            }
        )
