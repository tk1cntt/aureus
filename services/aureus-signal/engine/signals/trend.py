import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal, SignalType
from typing import Dict, Any, Optional

logger = get_logger(__name__)
class TrendSignal(BaseSignal):
    """
    Detects macro trend alignment (HTF Trend).
    Updates state_obj.htf_trend for Hybrid Judges.
    """
    signal_type = SignalType.INDICATOR
    def __init__(self, ema_period: int = 200):
        super().__init__(f"HTF Trend ({ema_period})")
        self.ema_period = ema_period

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if df.empty or "c" not in df.columns:
            state_obj.htf_trend = "NEUTRAL"
            return None

        current_price = float(df["c"].iloc[-1])
        current_t = int(df.iloc[-1]["t"]) if "t" in df.columns else len(df)
        current_ema = self._ema_value(df, state_obj, self.ema_period)
        ema21 = self._ema_value(df, state_obj, 21)
        ema55 = self._ema_value(df, state_obj, 55)

        obs = getattr(state_obj, "obs", [])
        recent_obs = obs[-20:] if isinstance(obs, list) else []
        green_count = sum(
            1 for ob in recent_obs
            if isinstance(ob, dict) and not ob.get("mitigated", False) and ob.get("ob_type") == "BULLISH"
        )
        red_count = sum(
            1 for ob in recent_obs
            if isinstance(ob, dict) and not ob.get("mitigated", False) and ob.get("ob_type") == "BEARISH"
        )

        structure_score = self._structure_score(state_obj, kwargs)
        ema_score = self._ema_score(df, ema21, ema55)
        ob_score = self._ob_score(recent_obs, current_t)
        sweep_score = self._sweep_score(recent_obs, kwargs)
        raw_score = structure_score + ema_score + ob_score + sweep_score
        ema200_penalty = self._ema200_penalty(current_price, current_ema, raw_score)
        score = raw_score + ema200_penalty
        has_directional_source = structure_score != 0 or ema_score != 0 or ob_score != 0 or sweep_score != 0
        if not has_directional_source and len(df) < self.ema_period:
            state_obj.htf_trend = "NEUTRAL"
            return None

        if score >= 3.0 and (structure_score > 0 or green_count >= 2) and (ema_score >= 0 or green_count >= 2):
            regime = "TREND_UP"
            htf_trend = "BULLISH"
        elif score <= -3.0 and (structure_score < 0 or red_count >= 2) and (ema_score <= 0 or red_count >= 2):
            regime = "TREND_DN"
            htf_trend = "BEARISH"
        else:
            regime = "SIDEWAYS"
            htf_trend = "NEUTRAL"

        state_obj.htf_trend = htf_trend

        return {
            "tag": "htf_trend",
            "value": htf_trend,
            "t": current_t,
            "data": {
                "regime": regime,
                "ema_ref": round(current_ema, 5) if current_ema is not None else None,
                "green_ob_count": green_count,
                "red_ob_count": red_count,
                "delta": green_count - red_count,
                "score": round(score, 4),
                "structure_score": round(structure_score, 4),
                "ema_score": round(ema_score, 4),
                "ob_score": round(ob_score, 4),
                "sweep_score": round(sweep_score, 4),
                "ema200_penalty": round(ema200_penalty, 4),
            }
        }

    def _ema_value(self, df: pd.DataFrame, state_obj: Any, period: int) -> Optional[float]:
        emas = getattr(state_obj, "emas", {})
        if isinstance(emas, dict):
            ema_state = emas.get(period) or emas.get(str(period))
            if isinstance(ema_state, dict) and ema_state.get("current") is not None:
                return float(ema_state["current"])
        col_name = f"ema_{period}"
        if col_name in df.columns and pd.notna(df[col_name].iloc[-1]):
            return float(df[col_name].iloc[-1])
        if len(df) >= min(period, 2):
            return float(df["c"].ewm(span=period, adjust=False).mean().iloc[-1])
        return None

    def _structure_score(self, state_obj: Any, kwargs: Dict[str, Any]) -> float:
        score = 0.0
        if kwargs.get("choch_up"):
            score += 1.5
        if kwargs.get("choch_down"):
            score -= 1.5

        swings = getattr(state_obj, "swing_points", [])
        if isinstance(swings, list):
            labels = [p.get("label") for p in swings[-4:] if isinstance(p, dict)]
            if "HH" in labels and "HL" in labels:
                score += 1.5
            if "LH" in labels and "LL" in labels:
                score -= 1.5
        return score

    def _ema_score(self, df: pd.DataFrame, ema21: Optional[float], ema55: Optional[float]) -> float:
        if ema21 is None or ema55 is None:
            return 0.0
        close = float(df["c"].iloc[-1])
        prev_close = float(df["c"].iloc[-2]) if len(df) > 1 else close
        price_slope = close - prev_close
        score = 0.0
        if close > ema21 > ema55 and price_slope >= 0:
            score += 1.5
        elif close < ema21 < ema55 and price_slope <= 0:
            score -= 1.5
        return score

    def _ob_score(self, obs: list, current_t: int) -> float:
        score = 0.0
        for ob in obs[-10:]:
            if not isinstance(ob, dict) or ob.get("mitigated", False):
                continue
            direction = 1 if ob.get("ob_type") == "BULLISH" else -1 if ob.get("ob_type") == "BEARISH" else 0
            if direction == 0:
                continue
            quality = float(ob.get("quality") or 0.5)
            body_ratio = float(ob.get("body_ratio") or 0.5)
            t_ref = ob.get("t_breakout", ob.get("t_start", current_t))
            recent = 1.0 if not isinstance(t_ref, (int, float)) or current_t - t_ref <= 20 else 0.5
            status = ob.get("status")
            weight = 0.5 + min(max(quality, 0.0), 1.0) + 0.25 * min(max(body_ratio, 0.0), 1.0)
            if status == "CLEAN_BREAKOUT":
                weight += 0.5
            elif status in {"SWEEP", "STOP_HUNT"}:
                weight -= 0.5
            score += direction * weight * recent
        return max(min(score, 2.0), -2.0)

    def _sweep_score(self, obs: list, kwargs: Dict[str, Any]) -> float:
        score = 0.0
        if kwargs.get("clean_breakout_bull"):
            score += 0.75
        if kwargs.get("clean_breakout_bear"):
            score -= 0.75
        if kwargs.get("stop_hunt_bear") or kwargs.get("sweep_bear"):
            score -= 1.5
        if kwargs.get("stop_hunt_bull") or kwargs.get("sweep_bull"):
            score += 1.5
        for ob in obs[-5:]:
            if not isinstance(ob, dict):
                continue
            status = ob.get("status")
            direction = 1 if ob.get("ob_type") == "BULLISH" else -1 if ob.get("ob_type") == "BEARISH" else 0
            if status == "CLEAN_BREAKOUT":
                score += direction * 0.5
            elif status in {"SWEEP", "STOP_HUNT"}:
                score += direction * 0.5
        return max(min(score, 1.5), -1.5)

    def _ema200_penalty(self, current_price: float, current_ema: Optional[float], raw_score: float) -> float:
        if current_ema is None or raw_score == 0:
            return 0.0
        if raw_score > 0 and current_price < current_ema:
            return -1.0
        if raw_score < 0 and current_price > current_ema:
            return 1.0
        return 0.0
