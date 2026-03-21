import logging
from engine.logging_common import get_logger
import pandas as pd
from .base import BaseSignal
from typing import Dict, Any, Optional

logger = get_logger(__name__)


class SweepSignal(BaseSignal):
    """
    Monitors identified liquidity levels (Sweep Targets) for stop hunts.
    Implements Regime-based filtering (Trend vs Sideways).
    """

    TAG_BULL = "sweep_bull"  # Price swept BELOW a target (Bullish setup)
    TAG_BEAR = "sweep_bear"  # Price swept ABOVE a target (Bearish setup)

    def __init__(self):
        super().__init__("Stop Hunt / Sweep Monitor")

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def calculate(self, df: pd.DataFrame, state_obj: Any, **kwargs) -> Optional[Dict[str, Any]]:
        if state_obj is None or df is None or len(df) == 0:
            return None

        active_targets = getattr(state_obj, "sweep_targets", None)
        if not isinstance(active_targets, list) or not active_targets:
            return None

        try:
            candle = df.iloc[-1]
            c_h = float(candle["h"])
            c_l = float(candle["l"])
            c_t = int(candle["t"])
        except (KeyError, TypeError, ValueError):
            return None

        symbol = getattr(state_obj, "symbol", "UNKNOWN")
        logger.debug(f"[t={c_t}] [{symbol}] [calculate] 1... SWEEP Signal Start")

        regime = str(getattr(state_obj, "market_regime", "SIDEWAYS") or "SIDEWAYS")
        history = getattr(state_obj, "signal_history", [])
        history = history if isinstance(history, list) else []

        logger.debug(f"[t={c_t}] [{symbol}] [calculate] 2... SWEEP Signal Active Targets: {active_targets}")
        triggered_sweep = None

        updated_targets = []
        for target in active_targets:
            if triggered_sweep:
                updated_targets.append(target)
                continue

            if not isinstance(target, dict):
                updated_targets.append(target)
                continue

            side = target.get("side")
            target_price = self._to_float(target.get("price"))
            if side not in ("BULLISH", "BEARISH") or target_price is None:
                updated_targets.append(target)
                continue

            is_swept = False
            tag = None

            # BULLISH Sweep: Price swept BELOW a target (Expect reversal UP)
            if side == "BULLISH":
                if c_l < target_price and regime in ["TREND_UP", "SIDEWAYS"]:
                    is_swept = True
                    tag = self.TAG_BULL

            # BEARISH Sweep: Price swept ABOVE a target (Expect reversal DOWN)
            elif side == "BEARISH":
                if c_h > target_price and regime in ["TREND_DN", "SIDEWAYS"]:
                    is_swept = True
                    tag = self.TAG_BEAR

            if is_swept:
                already_swept = any(
                    isinstance(s, dict)
                    and s.get("tag") == tag
                    and self._to_float(s.get("price_swept")) == target_price
                    and int(s.get("t", -1)) == c_t
                    for s in history
                )
                logger.info(f"[t={c_t}] [{symbol}] [calculate] 3... SWEEP Signal Already Swept: {already_swept}")

                if not already_swept:
                    triggered_sweep = {
                        "tag": tag,
                        "t": c_t,
                        "price_swept": target_price,
                        "source_type": target.get("type"),
                        "source_t": target.get("t_source"),
                        "fidelity": target.get("fidelity", 0.5),
                        "market_regime": regime,
                    }
                    logger.info(
                        f"[t={c_t}] [{symbol}] [calculate] 4... SWEEP DETECTED (Candle Close): {tag} @ {target_price} ({target.get('type')})"
                    )

                    transient = getattr(state_obj, "transient_signals", None)
                    if isinstance(transient, dict):
                        transient[tag] = triggered_sweep

                    request_ai_update = getattr(state_obj, "request_ai_update", None)
                    if callable(request_ai_update):
                        request_ai_update("STOP_HUNT")
                else:
                    updated_targets.append(target)
            else:
                updated_targets.append(target)

        state_obj.sweep_targets = updated_targets
        return triggered_sweep
